"""Physical-link behavior without pretending software tests measure an optical link."""

from collections import deque
import json
from pathlib import Path
import unittest

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameType
from faronet.dispositivo_luz_adaptador.manchester import encode
from faronet.dispositivo_luz_adaptador.physical import (
    PhysicalDispositivoLuzAdaptador, PhysicalLinkError,
)
from faronet.faro.commands import link_id, test_payload as payload_for
from faronet.faro.profile import PINS, pins_for
from faronet.faro.waveform import EdgeDecoder

A, B, SESSION = b"aaaaaaaa", b"bbbbbbbb", b"session1"
HALF = 5_000_000


def data(sequence=0, payload=b"test", session=SESSION):
    return Frame(FrameType.DATA, A, B, session, sequence, payload)


def edges(raw, start, jitter=0):
    previous = 0
    result = []
    for index, level in enumerate(encode(raw)):
        if level != previous:
            # Bounded edge delay/advance, no cumulative drift.
            adjustment = int(jitter * HALF) * (1 if index % 3 else -1)
            result.append((start + index * HALF + adjustment, level))
            previous = level
    if previous:
        result.append((start + 2048 * HALF, 0))
    return result


class DecoderTests(unittest.TestCase):
    def capture(self, raw, jitter=0):
        decoder = EdgeDecoder(HALF, 0)
        start = 20 * HALF
        observed = []
        for timestamp, level in edges(raw, start, jitter):
            frame = decoder.feed(timestamp, level)
            if frame is not None:
                observed.append(frame)
        frame = decoder.advance(start + 2049 * HALF)
        if frame is not None:
            observed.append(frame)
        return decoder, observed

    def test_full_frame_after_arbitrary_idle_and_bounded_jitter(self):
        frame = data(payload=bytes(range(86)))
        for jitter in (0, 0.1, 0.2):
            with self.subTest(jitter=jitter):
                _, observed = self.capture(frame.encode(), jitter)
                self.assertEqual(observed, [frame])

    def test_crc_corruption_is_not_a_delivery(self):
        raw = bytearray(data().encode())
        raw[50] ^= 1
        decoder, observed = self.capture(bytes(raw))
        self.assertEqual(observed, [])
        self.assertGreater(decoder.rejected, 0)

    def test_noise_then_guarded_frame_resynchronizes(self):
        decoder = EdgeDecoder(HALF, 0)
        decoder.feed(20 * HALF, 1)
        decoder.feed(21 * HALF, 0)
        decoder.advance(130 * HALF)
        self.assertGreater(decoder.rejected, 0)
        frame = data()
        for timestamp, level in edges(frame.encode(), 200 * HALF):
            decoder.feed(timestamp, level)
        self.assertEqual(decoder.advance(2249 * HALF), frame)

    def test_missing_edges_and_mid_frame_start_do_not_decode(self):
        decoder = EdgeDecoder(HALF, 0)
        for timestamp, level in edges(data().encode(), 20 * HALF)[5:]:
            self.assertIsNone(decoder.feed(timestamp, level))
        self.assertIsNone(decoder.advance(2100 * HALF))

    def test_event_overflow_abandons_frame(self):
        decoder = EdgeDecoder(HALF, 0)
        for index, (timestamp, level) in enumerate(edges(data().encode(), 20 * HALF)):
            if index == 30:
                decoder.lose_sync()
            decoder.feed(timestamp, level)
        self.assertIsNone(decoder.advance(2100 * HALF))

    def test_bad_manchester_is_rejected(self):
        decoder = EdgeDecoder(HALF, 0)
        decoder.feed(20 * HALF, 1)
        decoder.feed(500 * HALF, 0)
        self.assertIsNone(decoder.advance(2100 * HALF))


class ScriptedIO:
    frame_seconds = 0.01

    def __init__(self, incoming=(), ack_attempt=1):
        self.incoming = deque(incoming)
        self.sent = []
        self.ack_attempt = ack_attempt
        self.guards = 0
        self.cleared = False

    def transmit(self, frame):
        self.sent.append(frame)
        if frame.kind == FrameType.DATA and len(self.sent) >= self.ack_attempt:
            self.incoming.append(frame.acknowledgment())

    def receive(self, timeout):
        return self.incoming.popleft() if self.incoming else None

    def guard(self):
        self.guards += 1

    def clear(self):
        self.cleared = True


class PhysicalAdapterTests(unittest.TestCase):
    def test_six_mesh_fragments_cross_timestamped_wire_with_lost_ack_and_reply(self):
        from faronet.node.fragment import fragment, Reassembler

        class TimestampedWire(ScriptedIO):
            # Virtual waveform durations; no wall-clock scheduling assertion.
            frame_seconds = 10

            def __init__(self):
                super().__init__()
                self.peer = None
                self.on_data = None
                self.drop_ack = False

            def transmit(self, frame):
                self.sent.append(frame)
                if frame.kind == FrameType.ACK and self.drop_ack:
                    self.drop_ack = False
                    return
                decoder = EdgeDecoder(HALF, 0)
                decoded = None
                for timestamp, level in edges(frame.encode(), 20 * HALF, 0.1):
                    decoded = decoder.feed(timestamp, level) or decoded
                decoded = decoder.advance(2069 * HALF) or decoded
                if decoded is not None:
                    self.peer.incoming.append(decoded)
                    if decoded.kind == FrameType.DATA:
                        self.peer.on_data()

        left, right = TimestampedWire(), TimestampedWire()
        left.peer, right.peer = right, left
        right.drop_ack = True
        sender = PhysicalDispositivoLuzAdaptador(left, A, B, SESSION)
        receiver = PhysicalDispositivoLuzAdaptador(right, B, A, SESSION)
        reassembler, envelopes = Reassembler(), []

        def accept_fragment():
            payload = receiver.receive(1)
            if payload is not None:
                envelope = reassembler.accept(payload)
                if envelope is not None:
                    envelopes.append(envelope)

        right.on_data = accept_fragment
        envelope = bytes(range(246)) * 2
        results = [sender.send(payload) for payload in fragment(envelope, 1)]
        self.assertTrue(all(result.acknowledged for result in results))
        self.assertEqual(results[0].attempts, 2)
        self.assertEqual(receiver.duplicates, 1)
        self.assertEqual(envelopes, [envelope])
        reply = []
        left.on_data = lambda: reply.append(sender.receive(1))
        self.assertTrue(receiver.send(b"synthetic reply").acknowledged)
        self.assertEqual(reply, [b"synthetic reply"])

    def test_lost_ack_retries_identical_frame(self):
        io = ScriptedIO(ack_attempt=2)
        adapter = PhysicalDispositivoLuzAdaptador(io, A, B, SESSION)
        result = adapter.send(b"test")
        self.assertTrue(result.acknowledged)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(io.sent[0], io.sent[1])
        self.assertEqual(adapter.next_send, 1)

    def test_stale_wrong_neighbor_or_session_ack_does_not_advance(self):
        unrelated = [
            Frame(FrameType.ACK, B, A, b"session2", 0),
            Frame(FrameType.ACK, B, A, SESSION, 1),
            Frame(FrameType.ACK, A, B, SESSION, 0),
        ]
        io = ScriptedIO(unrelated, ack_attempt=5)
        adapter = PhysicalDispositivoLuzAdaptador(io, A, B, SESSION)
        result = adapter.send(b"test")
        self.assertFalse(result.acknowledged)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(adapter.ignored, 3)
        self.assertTrue(adapter.failed)
        with self.assertRaises(PhysicalLinkError):
            adapter.send(b"later")

    def test_receiver_reacks_retry_without_redelivery(self):
        io = ScriptedIO([data(), data(), data(1, b"next")])
        adapter = PhysicalDispositivoLuzAdaptador(io, B, A, SESSION)
        self.assertEqual(adapter.receive(1), b"test")
        self.assertEqual(adapter.receive(1), b"next")
        self.assertEqual(adapter.duplicates, 1)
        self.assertEqual([f.sequence for f in io.sent], [0, 0, 1])

    def test_changed_retry_skipped_sequence_and_old_session_not_acked(self):
        io = ScriptedIO([data(), data(payload=b"changed"), data(2), data(1, session=b"session0")])
        adapter = PhysicalDispositivoLuzAdaptador(io, B, A, SESSION)
        self.assertEqual(adapter.receive(1), b"test")
        self.assertIsNone(adapter.receive(1))
        self.assertEqual(len(io.sent), 1)
        self.assertEqual(adapter.ignored, 3)

    def test_external_frame_validation_and_clear(self):
        io = ScriptedIO()
        adapter = PhysicalDispositivoLuzAdaptador(io, A, B, SESSION)
        with self.assertRaises(PhysicalLinkError):
            adapter.send_frame(data(2).encode())
        self.assertFalse(io.sent)
        adapter.clear()
        self.assertTrue(io.cleared)
        with self.assertRaises(PhysicalLinkError):
            adapter.send(b"no")

    def test_synthetic_test_payload_and_id_validation(self):
        self.assertEqual(len(payload_for(0)), 86)
        self.assertNotEqual(payload_for(0), payload_for(1))
        self.assertEqual(link_id("01" * 8), b"\x01" * 8)
        for invalid in ("01", "A1" * 8, "gg" * 8, " 1" * 8):
            with self.assertRaises(ValueError):
                link_id(invalid)

    def test_pin_profile_matches_current_hardware_authority(self):
        root = Path(__file__).resolve().parents[2]
        reference = json.loads((root / "hardware/breadboard/circuit-reference.json").read_text())
        assigned = {row[3]: (int(row[2][4:]), row[1])
                    for row in reference["pins"] if row[2].startswith("GPIO")}
        self.assertEqual({p.role: (p.bcm, p.physical) for p in PINS}, assigned)
        layouts = json.loads((root / "hardware/breadboard/layout-data.json").read_text())
        for variant, rgb in (("basic", False), ("rgb", True)):
            with self.subTest(variant=variant):
                wired = {wire["net"]: int(wire["a"][3:])
                         for wire in layouts[variant]["wires"]
                         if wire["a"].startswith("PI:") and wire["net"] in assigned}
                self.assertEqual({p.role: p.physical for p in pins_for(rgb)}, wired)


if __name__ == "__main__":
    unittest.main()
