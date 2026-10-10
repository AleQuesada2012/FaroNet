"""Contract and failure tests using synthetic neighbor traffic only."""

from dataclasses import replace
import json
from pathlib import Path
import random
import unittest
import zlib

from faronet.dispositivo_luz_adaptador import DispositivoLuzAdaptador, Frame, FrameError, FrameType
from faronet.dispositivo_luz_adaptador import manchester
from faronet.dispositivo_luz_adaptador.simulation import (
    ACK_DEADLINE_UNITS, ACK_GAP_UNITS, FRAME_UNITS,
    Fault, FaultPlan, LinkError, SimulatedLink,
)

A, B, SESSION = b'FAKE0001', b'FAKE0002', b'SESSION1'


def data(payload: bytes = b'synthetic') -> Frame:
    return Frame(FrameType.DATA, A, B, SESSION, 0, payload)


def repair_crc(raw: bytearray) -> bytes:
    raw[124:] = zlib.crc32(raw[6:124]).to_bytes(4, 'big')
    return bytes(raw)


class FrameTests(unittest.TestCase):
    def test_published_golden_frames(self):
        vectors = json.loads((Path(__file__).parents[2] / 'fixtures/optical-v1.json').read_text())
        for vector in vectors['vectors']:
            with self.subTest(vector=vector['name']):
                frame = Frame(
                    FrameType(vector['kind']), bytes.fromhex(vector['source_hex']),
                    bytes.fromhex(vector['destination_hex']), bytes.fromhex(vector['session_hex']),
                    vector['sequence'], bytes.fromhex(vector['payload_hex']),
                )
                raw = bytes.fromhex(vector['frame_hex'])
                self.assertEqual(frame.encode(), raw)
                self.assertEqual(Frame.decode(raw), frame)

    def test_crc_known_answer(self):
        self.assertEqual(zlib.crc32(b'123456789'), 0xCBF43926)

    def test_empty_and_max_payload(self):
        for payload in (b'', bytes(range(86))):
            frame = data(payload)
            self.assertEqual(len(frame.encode()), 128)
            self.assertEqual(Frame.decode(frame.encode()), frame)

    def test_constructor_rejects_bounds_and_nonempty_ack(self):
        changes = [
            dict(payload=b'x' * 87), dict(payload='text'), dict(source=b'short'),
            dict(destination=bytearray(B)), dict(session=b'x' * 9),
            dict(sequence=-1), dict(sequence=1 << 32), dict(sequence=True),
            dict(kind=1), dict(kind=FrameType.ACK),
        ]
        for change in changes:
            with self.subTest(change=tuple(change)):
                with self.assertRaises(FrameError):
                    replace(data(), **change)

    def test_exact_length_and_preamble_sync(self):
        raw = data().encode()
        for malformed in (b'', raw[:-1], raw + b'\0', b'\0' + raw[1:], raw[:4] + b'\0' + raw[5:]):
            with self.subTest(size=len(malformed)):
                with self.assertRaises(FrameError):
                    Frame.decode(malformed)

    def test_header_payload_padding_and_crc_damage(self):
        for offset in (8, 24, 32, 38, 120, 127):
            raw = bytearray(data().encode())
            raw[offset] ^= 1
            with self.subTest(offset=offset):
                with self.assertRaises(FrameError):
                    Frame.decode(bytes(raw))

    def test_invalid_semantics_even_with_valid_crc(self):
        for offset, value in ((6, 2), (7, 3), (37, 87), (123, 1)):
            raw = bytearray(data().encode())
            raw[offset] = value
            with self.subTest(offset=offset):
                with self.assertRaises(FrameError):
                    Frame.decode(repair_crc(raw))
        raw = bytearray(data().encode())
        raw[7] = FrameType.ACK
        with self.assertRaises(FrameError):
            Frame.decode(repair_crc(raw))

    def test_ack_is_bound_to_both_neighbors_session_sequence(self):
        frame = data()
        ack = frame.acknowledgment()
        self.assertTrue(ack.is_ack_for(frame))
        self.assertEqual(ack.payload, b'')
        for changed in (
            replace(ack, source=A), replace(ack, destination=B),
            replace(ack, session=b'SESSION2'), replace(ack, sequence=1),
        ):
            self.assertFalse(changed.is_ack_for(frame))
        with self.assertRaises(FrameError):
            ack.acknowledgment()


class ManchesterTests(unittest.TestCase):
    def test_mapping_and_msb_order(self):
        self.assertEqual(manchester.encode(b'\0'), (0, 1) * 8)
        self.assertEqual(manchester.encode(b'\xff'), (1, 0) * 8)
        self.assertEqual(manchester.encode(b'\x80'), (1, 0) + (0, 1) * 7)

    def test_all_byte_values_and_repeated_patterns(self):
        for payload in (bytes(range(256)), b'\0\xff\x55\xaa' * 128, b''):
            self.assertEqual(manchester.decode(manchester.encode(payload)), payload)

    def test_complete_frame_symbol_budget(self):
        waveform = manchester.encode(data().encode())
        self.assertEqual(len(waveform), 2048)
        self.assertEqual(Frame.decode(manchester.decode(waveform)), data())

    def test_invalid_pairs_levels_and_truncation(self):
        for waveform in ((0, 0) * 8, (1, 1) * 8, (0, 2) * 8, (0.0, 1) * 8, (0, 1) * 7):
            with self.assertRaises(manchester.ManchesterError):
                manchester.decode(waveform)

    def test_seeded_signal_damage_rejected_by_crc(self):
        rng = random.Random(20261009)
        for _ in range(20):
            waveform = list(manchester.encode(data().encode()))
            index = 2 * rng.randrange(len(waveform) // 2)
            waveform[index] ^= 1
            waveform[index + 1] ^= 1
            with self.assertRaises(FrameError):
                Frame.decode(manchester.decode(waveform))


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.link = SimulatedLink(A, B, SESSION)
        self.a = DispositivoLuzAdaptador(self.link, A)
        self.b = DispositivoLuzAdaptador(self.link, B)

    def test_external_frames_and_two_scripted_turns(self):
        first = self.a.send_frame(data().encode())
        self.assertTrue(first.acknowledged)
        self.assertEqual(first.deliveries, (b'synthetic',))
        self.assertEqual(first.elapsed_half_bits, 2 * FRAME_UNITS + ACK_GAP_UNITS)
        with self.assertRaises(LinkError):
            self.b.send(b'reply')
        self.link.grant_turn(B)
        reply = self.b.send(b'reply')
        self.assertTrue(reply.acknowledged)
        self.assertEqual(reply.deliveries, (b'reply',))

    def test_lost_or_corrupt_data_is_retried(self):
        for fault in (Fault.DROP, Fault.CORRUPT, Fault.STALE_SESSION, Fault.WRONG_SEQUENCE):
            with self.subTest(fault=fault):
                self.setUp()
                result = self.a.send(b'message', FaultPlan(data=(fault,)))
                self.assertTrue(result.acknowledged)
                self.assertEqual(result.attempts, 2)
                self.assertEqual(result.deliveries, (b'message',))
                self.assertEqual(result.duplicate_observations, 0)
                self.assertEqual(result.elapsed_half_bits, ACK_DEADLINE_UNITS + 2 * FRAME_UNITS + ACK_GAP_UNITS)

    def test_lost_corrupt_or_stale_ack_reack_without_redelivery(self):
        for fault in (Fault.DROP, Fault.CORRUPT, Fault.STALE_SESSION, Fault.WRONG_SEQUENCE):
            with self.subTest(fault=fault):
                self.setUp()
                result = self.a.send(b'message', FaultPlan(ack=(fault,)))
                self.assertTrue(result.acknowledged)
                self.assertEqual(result.attempts, 2)
                self.assertEqual(result.deliveries, (b'message',))
                self.assertEqual(result.duplicate_observations, 1)

    def test_duplicate_waveform_observation_delivers_once(self):
        result = self.a.send(b'message', FaultPlan(data=(Fault.DUPLICATE,)))
        self.assertTrue(result.acknowledged)
        self.assertEqual(result.deliveries, (b'message',))
        self.assertEqual(result.duplicate_observations, 1)

    def test_duplicate_ack_does_not_skip_next_sequence(self):
        self.a.send(b'first', FaultPlan(ack=(Fault.DUPLICATE,)))
        self.assertEqual(self.link.make_data(A, b'next').sequence, 1)
        self.assertEqual(self.a.send(b'next').deliveries, (b'next',))

    def test_all_data_lost_exhausts_three_attempts(self):
        result = self.a.send(b'message', FaultPlan(data=(Fault.DROP,) * 3))
        self.assertFalse(result.acknowledged)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.deliveries, ())
        self.assertEqual(result.elapsed_half_bits, 3 * ACK_DEADLINE_UNITS)

    def test_final_ack_loss_is_not_a_delivery_failure_claim(self):
        result = self.a.send(b'message', FaultPlan(ack=(Fault.DROP,) * 3))
        self.assertFalse(result.acknowledged)
        self.assertEqual(result.deliveries, (b'message',))
        self.assertEqual(result.duplicate_observations, 2)
        with self.assertRaises(LinkError):
            self.a.send(b'next')
        with self.assertRaises(LinkError):
            self.link.grant_turn(B)

    def test_reset_discards_old_session_and_restarts_sequences(self):
        self.a.send(b'message', FaultPlan(ack=(Fault.DROP,) * 3))
        with self.assertRaises(LinkError):
            self.link.reset_session(SESSION)
        self.link.reset_session(b'SESSION2')
        with self.assertRaises(LinkError):
            self.a.send_frame(data().encode())
        result = self.a.send(b'new', FaultPlan(ack=(Fault.STALE_SESSION,)))
        self.assertTrue(result.acknowledged)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.deliveries, (b'new',))

    def test_sequence_progress_and_old_external_frame_rejection(self):
        self.a.send(b'first')
        with self.assertRaises(LinkError):
            self.a.send_frame(data().encode())
        self.assertEqual(self.link.make_data(A, b'second').sequence, 1)
        self.assertEqual(self.a.send(b'second').deliveries, (b'second',))

    def test_reset_cannot_reuse_an_earlier_session(self):
        self.link.reset_session(b'SESSION2')
        self.link.reset_session(b'SESSION3')
        with self.assertRaises(LinkError):
            self.link.reset_session(SESSION)

    def test_adapter_rejects_wrong_source_and_ack_submission(self):
        with self.assertRaises(LinkError):
            self.b.send_frame(data().encode())
        with self.assertRaises(LinkError):
            self.b.send_frame(data().acknowledgment().encode())

    def test_empty_payload_is_still_one_delivery(self):
        self.assertEqual(self.a.send(b'').deliveries, (b'',))

    def test_limits_reject_before_transmission(self):
        with self.assertRaises(FrameError):
            self.a.send(b'x' * 87)
        with self.assertRaises(LinkError):
            FaultPlan(data=(Fault.DROP,) * 4)
        self.assertEqual(self.link.clock_units, 0)


if __name__ == '__main__':
    unittest.main()
