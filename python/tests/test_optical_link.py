"""Drive run_link against a fake backend whose peer is another CsmaLink; no GPIO."""

import random
import unittest

from faronet.dispositivo_luz_adaptador.medium import CsmaLink, Delivered, SendResult, Transmit
from faronet.dispositivo_luz_adaptador.simulation import ACK_GAP_UNITS, FRAME_UNITS
from faronet.faro.commands import test_payload
from faronet.faro.link import run_link

A, B, SESSION = b"\x01" * 8, b"\x02" * 8, b"S" * 8
HALF = 0.002


class PeerIO:
    """Sequential optical path: each side's light ends before the other decides."""

    frame_seconds = FRAME_UNITS * HALF

    def __init__(self, peer, lose_first_ack=False):
        self.now = 0.0
        self.peer = peer
        self.lose_first_ack = lose_first_ack
        self.incoming = []  # (arrival, frame) from the peer
        self.peer_busy_until = self.peer_light_end = self.my_light_end = 0.0
        self.guards = 0
        self.sent = []
        self.peer_results = []

    def channel(self):
        return self.peer_light_end, False

    def guard(self):
        self.guards += 1
        self.now += ACK_GAP_UNITS * HALF

    def transmit(self, frame):
        self.now += FRAME_UNITS * HALF
        self.my_light_end = self.now
        self.sent.append(frame)
        self.peer_results += self.peer.on_frame(frame, self.now)

    def _step_peer(self):
        if self.now < self.peer_busy_until:
            return
        for action in self.peer.poll(self.now, self.my_light_end, False):
            if isinstance(action, Transmit):
                end = self.now + (ACK_GAP_UNITS + FRAME_UNITS) * HALF
                self.peer_busy_until = self.peer_light_end = end
                if self.lose_first_ack and action.frame.kind == 2:
                    self.lose_first_ack = False
                else:
                    self.incoming.append((end, action.frame))
            else:
                self.peer_results.append(action)

    def receive(self, timeout):
        end = self.now + timeout
        while self.now < end:
            self._step_peer()
            if self.incoming and self.incoming[0][0] <= end:
                arrival, frame = self.incoming.pop(0)
                self.now = max(self.now, arrival)
                return frame
            later = [t for t in (self.peer.wake_at, self.peer_busy_until) if self.now < t < end]
            self.now = min(later, default=end)
        return None


class OpticalLinkDriverTests(unittest.TestCase):
    def run_pair(self, **io_options):
        mine = CsmaLink(A, B, SESSION, HALF, random.Random(1))
        peer = CsmaLink(B, A, SESSION, HALF, random.Random(2))
        for index in range(3):
            mine.offer(test_payload(index))
            peer.offer(test_payload(index))
        io = PeerIO(peer, **io_options)
        events = []
        stats = run_link(io, mine, test_payload, 3, 600, events.append, clock=lambda: io.now)
        return mine, peer, io, events, stats

    def test_both_directions_complete_without_roles_then_linger_ends(self):
        mine, peer, io, events, stats = self.run_pair()
        self.assertEqual((stats["sent_acknowledged"], stats["received_unique"],
                          stats["payload_bit_errors"], stats["send_failed"]), (3, 3, 0, 0))
        self.assertEqual([r.acknowledged for r in io.peer_results if isinstance(r, SendResult)],
                         [True] * 3)
        self.assertEqual(len([r for r in io.peer_results if isinstance(r, Delivered)]), 3)
        self.assertEqual(io.guards, len(io.sent))  # Every frame gets the dark guard first.
        self.assertLess(stats["elapsed_seconds"], 600)
        self.assertIn({"received_unique": 3, "payload_bit_errors": 0}, events)

    def test_lost_ack_is_retried_and_reacked_once(self):
        mine, peer, io, events, stats = self.run_pair(lose_first_ack=True)
        self.assertEqual((stats["sent_acknowledged"], stats["received_unique"]), (3, 3))
        self.assertEqual(mine.ack_timeouts, 1)
        self.assertEqual(peer.duplicates, 1)
        self.assertEqual(len([r for r in io.peer_results if isinstance(r, Delivered)]), 3)


if __name__ == "__main__":
    unittest.main()
