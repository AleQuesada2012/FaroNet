"""CLI for synthetic optical bring-up; never accepts or logs private chat text."""

import hashlib
import json
import math
import secrets
import signal
import socket
import sys
import threading
import time

from faronet.dispositivo_luz_adaptador.frame import FRAME_SIZE, Frame, FrameType
from faronet.dispositivo_luz_adaptador.manchester import encode
from faronet.dispositivo_luz_adaptador.physical import PhysicalDispositivoLuzAdaptador
from faronet.dispositivo_luz_adaptador.medium import CsmaLink
from faronet.faro.address import ROTATE_SECONDS, AddressStore, link_id
from faronet.faro.calibrate import rx_telemetry
from faronet.faro.gpio import PANIC_EXIT, PanicStop
from faronet.faro.link import run_link
from faronet.faro.profile import PINS, inspect_chip
from faronet.faro.timing import TxTiming, system_timing


def test_payload(index: int) -> bytes:
    return hashlib.shake_256(b"FaroNet optical test v1" + index.to_bytes(4, "big")).digest(86)


def add_commands(commands):
    commands.add_parser("optical-session", help="Generate a fresh synthetic link session ID.")
    address = commands.add_parser("optical-address",
                                  help="Show this Faro's stored link address (rotates every 24 h).")
    address.add_argument("--rotate", action="store_true", help="Replace it with a new random address now.")
    preflight = commands.add_parser("gpio-preflight", help="Inspect metadata without requesting GPIO.")
    preflight.add_argument("--chip", default="/dev/gpiochip0")
    preflight.add_argument("--profile-only", action="store_true", help="Show pins without importing gpiod.")
    for name in ("gpio-monitor", "gpio-calibrate", "optical-loopback", "optical-link",
                 "optical-send", "optical-listen", "optical-bridge", "optical-inject"):
        text = {"optical-bridge": "Carry one mesh LAN link over the peer Faro (chat --faro-peer starts it).",
                "optical-inject": "Transmit a 128-byte frame built outside the Faro (for example with Scapy)."
                }.get(name, "Physical optical bring-up (requires prepared circuit).")
        parser = commands.add_parser(name, help=text)
        parser.add_argument("--chip", default="/dev/gpiochip0")
        parser.add_argument("--hardware-ready", action="store_true", required=True,
                            help="Confirm circuit continuity and 0–3.3 V receiver levels first.")
        parser.add_argument("--half-bit-ms", type=float, default=5)
        parser.add_argument("--rx-inverted", action="store_true", help="Invert measured RX light polarity.")
        if name == "gpio-monitor":
            parser.add_argument("--seconds", type=float, default=15)
        elif name == "gpio-calibrate":
            parser.add_argument("--seconds", type=float, default=120)
            parser.add_argument("--blink", action="store_true",
                                help="Toggle IR; hold a reflector over D1 and Q2.")
            parser.add_argument("--blink-ms", type=float, default=1000,
                                help="IR on/off period half (ms) with --blink; 10 matches a 10 ms half-bit.")
        elif name == "optical-inject":
            parser.add_argument("--frame", required=True, metavar="HEX",
                                help="The serialized frame as 256 hex characters, or - to read them from stdin.")
            parser.add_argument("--count", type=int, default=1, help="Times to transmit it (1-1000).")
        elif name == "optical-loopback":
            parser.add_argument("--count", type=int, default=3)
            parser.add_argument("--timing-report", action="store_true",
                                help="Report each frame's TX lateness and its sources instead of "
                                     "stopping at the timing budget.")
        else:
            parser.add_argument("--local", type=link_id,
                                help="Override this Faro's stored link address (see optical-address).")
            parser.add_argument("--peer", type=link_id, required=True)
            parser.add_argument("--session", type=link_id, required=True)
            if name == "optical-bridge":
                parser.add_argument("--listen", type=_listen_address, default=("127.0.0.1", 7500),
                                    help="HOST:PORT for the local Node's connection (default 127.0.0.1:7500).")
                continue
            parser.add_argument("--count", type=int, default=3)
            if name == "optical-listen":
                parser.add_argument("--timeout", type=float, default=300,
                                    help="Total initial receive window; retry linger is additional.")
            elif name == "optical-link":
                parser.add_argument("--timeout", type=float, default=900,
                                    help="Total run time limit, including the final re-ACK linger.")


def _external_frame(text: str) -> Frame:
    """RFC FN-1 4.1: a frame built elsewhere is checked like a received one before it is sent."""
    text = (sys.stdin.read() if text == "-" else text).strip()
    try:
        raw = bytes.fromhex(text)
    except ValueError:
        raise ValueError("--frame must be hexadecimal") from None
    return Frame.decode(raw)


def _listen_address(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    if not host or not port.isdigit() or not 0 <= int(port) <= 65535:
        raise ValueError("Addresses must be HOST:PORT")
    return host, int(port)


def _bridge(io, args) -> int:
    """Serve one mesh link over the light until Ctrl+C or panic (RFC FN-1 5.9)."""
    from faronet.faro.bridge import serve_bridge

    with socket.create_server(args.listen) as listener:
        _print({"ready": "optical-bridge", "port": listener.getsockname()[1],
                "frame_seconds": io.frame_seconds})
        try:
            serve_bridge(io, args.local, args.peer, args.session, listener, _print, threading.Event())
        finally:
            io.clear()
    return 0


# Synthetic labels: a loopback frame never leaves this board.
LOOPBACK_SOURCE = bytes.fromhex("0101010101010101")
LOOPBACK_DESTINATION = bytes.fromhex("0202020202020202")


def _loopback(io, count: int, timing_report: bool = False) -> int:
    """Send DATA frames and decode each one's reflection on the same board."""
    session = secrets.token_bytes(8)
    ready = {"ready": "optical-loopback", "frame_seconds": io.frame_seconds,
             "test_frames": count, "synthetic_only": True}
    if timing_report:
        io.timing = TxTiming(io.half_ns)
        ready["system_timing"] = system_timing()
    _print(ready)
    start = time.monotonic()
    echoed = matched = bit_errors = 0
    raw_errors = raw_bits_seen = 0  # Over every complete capture, damaged ones included.
    for index in range(count):
        frame = Frame(FrameType.DATA, LOOPBACK_SOURCE, LOOPBACK_DESTINATION,
                      session, index, test_payload(index))
        io.guard()
        # Same work transmit() does before its first deadline.
        encoding_ns = time.monotonic_ns()
        encode(frame.encode())
        encoding_ns = time.monotonic_ns() - encoding_ns
        io.last_rejected_raw = None
        echo = io.transmit(frame, loopback=True)
        errors = None
        sent = frame.encode()
        if echo is not None:
            echoed += 1
            errors = sum((a ^ b).bit_count() for a, b in zip(echo.encode(), sent))
            bit_errors += errors
            matched += echo == frame
            raw_errors += errors
            raw_bits_seen += len(sent) * 8
        elif io.last_rejected_raw is not None:
            # A capture that failed its CRC still counts toward the raw bit error rate.
            raw = io.last_rejected_raw
            errors = sum((a ^ b).bit_count() for a, b in zip(raw, sent)) + abs(len(raw) - len(sent)) * 8
            raw_errors += errors
            raw_bits_seen += len(sent) * 8
        report = {"frame": index, "echoed": echo is not None, "matches": echo == frame,
                  "bit_errors": errors}
        if io.timing is not None:
            report["tx_timing"] = io.timing.summary() | {"encode_ms": round(encoding_ns / 1e6, 3)}
            io.timing.reset()
        _print(report)
    elapsed = time.monotonic() - start
    _print({"sent": count, "echoed": echoed, "matched": matched,
            "elapsed_seconds": round(elapsed, 3),
            "payload_bytes_per_second": round(matched * 86 / elapsed, 3),
            "bit_errors_in_crc_valid_frames": bit_errors,
            "raw_bit_errors": raw_errors, "raw_bits_compared": raw_bits_seen,
            "ber": round(raw_errors / raw_bits_seen, 6) if raw_bits_seen else None,
            "frames_without_capture": count - raw_bits_seen // (FRAME_SIZE * 8),
            "rejected_waveforms": io.rejected, "event_overruns": io.overruns,
            "tx_max_lateness_ms": round(io.max_lateness_ns / 1e6, 3)})
    return int(matched != count)


def _link(io, args) -> int:
    """Both Faros run this: contend for the medium, send and receive, no roles."""
    link = CsmaLink(args.local, args.peer, args.session, io.half_ns / 1e9)
    for index in range(args.count):
        link.offer(test_payload(index))
    _print({"ready": "optical-link", "frame_seconds": io.frame_seconds,
            "test_frames": args.count, "synthetic_only": True})
    try:
        stats = run_link(io, link, test_payload, args.count, args.timeout, _print)
    finally:
        io.clear()
    moved = stats["sent_acknowledged"] + stats["received_unique"]
    _print(stats | {
        "attempts_total": link.attempts_total, "ack_timeouts": link.ack_timeouts,
        "deferrals": link.deferrals, "duplicates_reacked": link.duplicates,
        "payload_bytes_per_second": round(moved * 86 / stats["elapsed_seconds"], 3),
        "rejected_waveforms": io.rejected, "event_overruns": io.overruns,
        "tx_max_lateness_ms": round(io.max_lateness_ns / 1e6, 3),
    })
    return int(stats["sent_acknowledged"] != args.count or stats["received_unique"] != args.count
               or stats["payload_bit_errors"] != 0)


def _print(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def run(args) -> int:
    if args.command == "optical-session":
        print(secrets.token_hex(8))
        return 0
    if args.command == "optical-address":
        store = AddressStore()
        try:
            local = store.rotate() if args.rotate else store.current()
            age = store.age_seconds() or 0
        except OSError as exc:
            print(f"No se pudo leer o guardar la dirección física en {store.path}: {exc.strerror or exc}",
                  file=sys.stderr)
            return 2
        _print({"local": local.hex(), "age_hours": round(age / 3600, 2),
                "rotates_in_hours": round((ROTATE_SECONDS - age) / 3600, 2)})
        return 0
    # SIGTERM (as chat --faro-peer stops its bridge) releases GPIO like Ctrl+C.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
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
        if not args.command.startswith("gpio-") and not 1 <= getattr(args, "count", 1) <= 1000:
            raise ValueError("Count must be 1–1000")
        # Validate IDs before requesting lines.
        if getattr(args, "local", "") is None:
            args.local = AddressStore().current()
        if getattr(args, "peer", None) is not None and args.local == args.peer:
            raise ValueError("Local and peer addresses must differ")
        injected = _external_frame(args.frame) if args.command == "optical-inject" else None
        with GpioFrameIO(args.chip, args.half_bit_ms, args.rx_inverted) as io:
            if injected is not None:
                for index in range(args.count):
                    io.guard()
                    io.transmit(injected)
                    _print({"injected": index, "type": injected.kind.name, "sequence": injected.sequence,
                            "payload_bytes": len(injected.payload)})
                return 0
            if args.command == "gpio-monitor":
                end, previous = time.monotonic() + args.seconds, None
                while time.monotonic() < end:
                    levels = io.input_levels()
                    if levels != previous:
                        _print(levels)
                        previous = levels
                    time.sleep(0.02)
                return 0
            if args.command == "gpio-calibrate":
                if not 2 <= args.blink_ms <= 10_000:
                    raise ValueError("--blink-ms must be between 2 and 10000")
                _print({"ready": "gpio-calibrate", "seconds": args.seconds, "blink": args.blink,
                        "blink_ms": args.blink_ms})
                return rx_telemetry(io, args.seconds, args.blink, _print,
                                    blink_seconds=args.blink_ms / 1000)
            if args.command == "optical-loopback":
                return _loopback(io, args.count, args.timing_report)
            if args.command == "optical-link":
                return _link(io, args)
            if args.command == "optical-bridge":
                return _bridge(io, args)
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
        print("Detenido; salidas del GPIO liberadas.", file=sys.stderr)
        return 130
    except PanicStop:
        # RFC FN-1 4.8: outputs are off and the lines released; also forget this address.
        try:
            AddressStore().rotate()
        except OSError:
            pass  # Exit 3 must still reach chat --faro-peer so the Node erases its state.
        print("Pánico: salidas apagadas, GPIO liberado, sesión descartada y dirección física rotada. "
              "Intercambia la nueva dirección (optical-address) y una sesión nueva antes de reiniciar.",
              file=sys.stderr)
        return PANIC_EXIT
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"Falló el comando óptico: {exc}", file=sys.stderr)
        return 2
