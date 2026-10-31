"""CSMA/CA link rules on a simulated two-Faro medium; no GPIO or wall-clock time."""

import random
import unittest

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameType
from faronet.dispositivo_luz_adaptador.medium import (
    DIFS_UNITS, CsmaLink, Delivered, SendResult, SimulatedMedium, Transmit,
)
from faronet.dispositivo_luz_adaptador.simulation import ACK_DEADLINE_UNITS, ACK_GAP_UNITS, FRAME_UNITS

A, B, SESSION = b"\x01" * 8, b"\x02" * 8, b"S" * 8


class Zero(random.Random):
    def randrange(self, *_):
        return 0


def pair(seed, rng_b=None):
    a = CsmaLink(A, B, SESSION, 1.0, random.Random(seed))
    b = CsmaLink(B, A, SESSION, 1.0, rng_b or random.Random(seed + 1000))
    return a, b


def results(medium, index, kind):
    return [action for _, i, action in medium.events if i == index and isinstance(action, kind)]


class MediumTests(unittest.TestCase):
    def test_both_faros_send_at_once_and_deliver_everything_once_in_order(self):
        collided = 0
        for seed in range(30):
            with self.subTest(seed=seed):
                a, b = pair(seed)
                medium = SimulatedMedium(a, b)
                for index in range(3):
                    medium.offer(0, 0, b"a%d" % index)
                    medium.offer(0, 1, b"b%d" % index)
                medium.run(10**6)
                for me, peer in ((0, b"b"), (1, b"a")):
                    self.assertEqual([d.payload for d in results(medium, me, Delivered)],
                                     [peer + b"%d" % i for i in range(3)])
                    self.assertEqual([r.acknowledged for r in results(medium, me, SendResult)],
                                     [True] * 3)
                collided += a.ack_timeouts > 0
        self.assertGreater(collided, 0)

    def test_carrier_sense_defers_data_until_the_peer_is_dark(self):
        a, b = pair(1, Zero())
        medium = SimulatedMedium(a, b)
        medium.offer(0, 0, b"first")
        # A decides at DIFS at the latest; its light then lasts a whole frame.
        medium.offer(DIFS_UNITS + 8 * 32 + ACK_GAP_UNITS + 100, 1, b"while A shines")
        medium.run(10**6)
        light = sorted((start, end, i) for i, sent in enumerate(medium.sent)
                       for _, start, end, _ in sent)
        for (_, end, _), (start, _, _) in zip(light, light[1:]):
            self.assertLessEqual(end, start)
        self.assertEqual(a.ack_timeouts + b.ack_timeouts, 0)
        # B's ACK for A goes out before B's own DATA.
        kinds = [frame.kind for _, _, _, frame in medium.sent[1]]
        self.assertEqual(kinds, [FrameType.ACK, FrameType.DATA])

    def test_lost_ack_retries_and_receiver_reacks_without_redelivery(self):
        lost = []

        def lose(sender, frame):
            if sender == 1 and frame.kind == FrameType.ACK and not lost:
                lost.append(frame)
                return True
            return False

        a, b = pair(3)
        medium = SimulatedMedium(a, b, lose=lose)
        medium.offer(0, 0, b"once")
        medium.run(10**6)
        self.assertEqual(results(medium, 0, SendResult), [SendResult(0, True, 2)])
        self.assertEqual(len(results(medium, 1, Delivered)), 1)
        self.assertEqual((b.duplicates, a.ack_timeouts), (1, 1))

    def test_retry_exhaustion_fails_sending_but_the_link_still_receives(self):
        a, b = pair(4)
        medium = SimulatedMedium(
            a, b, lose=lambda sender, frame: sender == 0 and frame.kind == FrameType.DATA)
        medium.offer(0, 0, b"never arrives")
        medium.offer(0, 0, b"dropped with the session")
        medium.offer(0, 1, b"from B")
        medium.run(10**6)
        self.assertEqual(results(medium, 0, SendResult), [SendResult(0, False, 3)])
        self.assertTrue(a.failed and a.idle)
        self.assertEqual([d.payload for d in results(medium, 0, Delivered)], [b"from B"])
        self.assertEqual([r.acknowledged for r in results(medium, 1, SendResult)], [True])
        with self.assertRaises(ValueError):
            a.offer(b"after failure")

    def test_poll_waits_for_difs_backoff_and_ack_deadline_in_seconds(self):
        half = 0.01
        link = CsmaLink(A, B, SESSION, half, Zero())
        link.offer(b"x")
        self.assertEqual(link.poll(1.0, 1.0 - 10 * half, False), [])
        self.assertAlmostEqual(link.wake_at, 1.0 + (DIFS_UNITS - 10) * half)
        self.assertEqual(link.poll(5.0, 0.0, True), [])
        [action] = link.poll(5.0, 0.0, False)
        self.assertIsInstance(action, Transmit)
        self.assertAlmostEqual(link.wake_at, 5.0 + ACK_DEADLINE_UNITS * half)
        self.assertEqual(link.poll(5.0 + FRAME_UNITS * half, 0.0, False), [])

    def test_stale_foreign_and_out_of_order_frames_are_ignored(self):
        link = CsmaLink(A, B, SESSION, 1.0, Zero())
        link.offer(b"x")
        [action] = link.poll(100.0, 0.0, False)
        data = action.frame
        wrong_ack = Frame(FrameType.ACK, B, A, SESSION, 7)
        other_session = Frame(FrameType.DATA, B, A, b"T" * 8, 0, b"y")
        skipped = Frame(FrameType.DATA, B, A, SESSION, 1, b"y")
        for frame in (wrong_ack, other_session, skipped):
            self.assertEqual(link.on_frame(frame, 101.0), [])
        self.assertEqual(link.ignored, 3)
        first = Frame(FrameType.DATA, B, A, SESSION, 0, b"y")
        self.assertEqual(link.on_frame(first, 102.0), [Delivered(b"y", 0)])
        changed_retry = Frame(FrameType.DATA, B, A, SESSION, 0, b"z")
        self.assertEqual(link.on_frame(changed_retry, 103.0), [])
        self.assertEqual(link.on_frame(data.acknowledgment(), 104.0), [SendResult(0, True, 1)])
        self.assertEqual(link.poll(104.0, 0.0, False), [Transmit(first.acknowledgment())])

    def test_invalid_construction_and_payloads_fail_explicitly(self):
        with self.assertRaises(ValueError):
            CsmaLink(A, A, SESSION, 1.0)
        with self.assertRaises(ValueError):
            CsmaLink(A, B, SESSION, 0)
        with self.assertRaises(ValueError):
            CsmaLink(A, B, SESSION, 1.0).offer(b"x" * 87)


if __name__ == "__main__":
    unittest.main()
