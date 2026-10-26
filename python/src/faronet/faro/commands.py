"""CLI for synthetic optical bring-up; never accepts or logs private chat text."""

import hashlib
import json
import math
import secrets
import sys
import time

from faronet.dispositivo_luz_adaptador.physical import PhysicalDispositivoLuzAdaptador
from faronet.faro.profile import PINS, inspect_chip


def test_payload(index: int) -> bytes:
    return hashlib.shake_256(b"FaroNet optical test v1" + index.to_bytes(4, "big")).digest(86)


def link_id(value: str) -> bytes:
    if len(value) != 16 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("IDs must be 16 lowercase hex characters (eight bytes)")
    return bytes.fromhex(value)


def add_commands(commands):
    commands.add_parser("optical-session", help="Generate a fresh synthetic link session ID.")
    preflight = commands.add_parser("gpio-preflight", help="Inspect metadata without requesting GPIO.")
    preflight.add_argument("--chip", default="/dev/gpiochip0")
    preflight.add_argument("--profile-only", action="store_true", help="Show pins without importing gpiod.")
    for name in ("gpio-monitor", "optical-send", "optical-listen"):
        parser = commands.add_parser(name, help="Physical optical bring-up (requires prepared circuit).")
        parser.add_argument("--chip", default="/dev/gpiochip0")
        parser.add_argument("--hardware-ready", action="store_true", required=True,
                            help="Confirm circuit continuity and 0–3.3 V receiver levels first.")
        parser.add_argument("--half-bit-ms", type=float, default=5)
        parser.add_argument("--rgb", action="store_true", help="Enable revision-6 common-cathode RGB.")
        parser.add_argument("--rx-inverted", action="store_true", help="Invert measured RX light polarity.")
        if name == "gpio-monitor":
            parser.add_argument("--seconds", type=float, default=15)
        else:
            parser.add_argument("--local", type=link_id, required=True)
            parser.add_argument("--peer", type=link_id, required=True)
            parser.add_argument("--session", type=link_id, required=True)
            parser.add_argument("--count", type=int, default=3)
            if name == "optical-listen":
                parser.add_argument("--timeout", type=float, default=300,
                                    help="Total initial receive window; retry linger is additional.")


def _print(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def run(args) -> int:
    if args.command == "optical-session":
        print(secrets.token_hex(8))
        return 0
    if args.command == "gpio-preflight" and args.profile_only:
        _print({"pins": [vars(pin) for pin in PINS]})
        return 0
    try:
        if args.command == "gpio-preflight":
            report = inspect_chip(args.chip)
            _print(report)
            return int(not report["controller_matches"] or any(p["used"] for p in report["lines"]))
        from faronet.faro.gpio import GpioFrameIO

        for field in ("half_bit_ms", "seconds", "timeout"):
            value = getattr(args, field, 1)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field} must be finite and positive")
        if args.command != "gpio-monitor" and not 1 <= args.count <= 1000:
            raise ValueError("Count must be 1–1000")
        # Validate IDs before requesting lines.
        if args.command != "gpio-monitor" and args.local == args.peer:
            raise ValueError("Local and peer addresses must differ")
        with GpioFrameIO(args.chip, args.half_bit_ms, args.rgb, args.rx_inverted) as io:
            if args.command == "gpio-monitor":
                end, previous = time.monotonic() + args.seconds, None
                while time.monotonic() < end:
                    levels = io.input_levels()
                    if levels != previous:
                        _print(levels)
                        previous = levels
                    time.sleep(0.02)
                return 0
            adapter = PhysicalDispositivoLuzAdaptador(io, args.local, args.peer, args.session)
            try:
                _print({"ready": args.command, "frame_seconds": io.frame_seconds,
                        "test_frames": args.count, "synthetic_only": True})
                start = time.monotonic()
                delivered = bit_errors = attempts = 0
                if args.command == "optical-send":
                    for index in range(args.count):
                        result = adapter.send(test_payload(index))
                        attempts += result.attempts
                        _print({"frame": index, "acknowledged": result.acknowledged,
                                "attempts": result.attempts})
                        if not result.acknowledged:
                            break
                        delivered += 1
                else:
                    deadline = start + args.timeout
                    while delivered < args.count and (remaining := deadline - time.monotonic()) > 0:
                        payload = adapter.receive(remaining)
                        if payload is None:
                            break
                        expected = test_payload(delivered)
                        bit_errors += sum((a ^ b).bit_count() for a, b in zip(payload, expected))
                        bit_errors += abs(len(payload) - len(expected)) * 8
                        delivered += 1
                        _print({"received_unique": delivered, "payload_bit_errors": bit_errors})
                elapsed = time.monotonic() - start
                _print({"delivered": delivered, "attempts": attempts,
                        "elapsed_seconds": round(elapsed, 3),
                        "payload_bytes_per_second": round(delivered * 86 / elapsed, 3),
                        "payload_bit_errors_in_crc_valid_frames": bit_errors,
                        "rejected_waveforms": io.rejected, "event_overruns": io.overruns,
                        "tx_max_lateness_ms": round(io.max_lateness_ns / 1e6, 3)})
                if args.command == "optical-listen" and delivered == args.count:
                    # Stay available for two retransmissions if the final ACK was lost.
                    _print({"retry_linger_seconds": round(7 * io.frame_seconds + 1, 3)})
                    adapter.receive(7 * io.frame_seconds + 1)
                    _print({"duplicates_reacked": adapter.duplicates})
                return int(delivered != args.count or bit_errors != 0)
            finally:
                adapter.clear()
    except KeyboardInterrupt:
        print("Stopped; GPIO outputs released.", file=sys.stderr)
        return 130
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"Optical command failed: {exc}", file=sys.stderr)
        return 2
