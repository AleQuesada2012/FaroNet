"""Six Faro payloads per envelope; reassembly tolerates disorder and duplicates."""

import json
from pathlib import Path
import unittest

from faronet.dispositivo_luz_adaptador.frame import PAYLOAD_SIZE
from faronet.node.fragment import (
    ENVELOPE_SIZE, FRAGMENT_COUNT, FRAGMENT_DATA_SIZE, MAX_PENDING, FragmentError,
    Reassembler, fragment,
)

VECTOR = json.loads((Path(__file__).parents[2] / 'fixtures/mesh-fragment-v1.json').read_text())['vectors'][0]
ENVELOPE = bytes.fromhex(VECTOR['envelope_hex'])


class FragmentTests(unittest.TestCase):
    def test_budget_follows_the_accepted_frame(self):
        self.assertEqual(FRAGMENT_DATA_SIZE, PAYLOAD_SIZE - 4)
        self.assertEqual(ENVELOPE_SIZE, 492)
        self.assertEqual(FRAGMENT_COUNT, 6)

    def test_shared_vector(self):
        parts = fragment(ENVELOPE, VECTOR['tag'])
        self.assertEqual([p.hex() for p in parts], VECTOR['fragments_hex'])
        self.assertTrue(all(len(p) == PAYLOAD_SIZE for p in parts))

    def test_round_trip_in_any_order(self):
        parts = fragment(ENVELOPE, 7)
        reassembler = Reassembler()
        for payload in reversed(parts[:-1]):
            self.assertIsNone(reassembler.accept(payload))
        self.assertEqual(reassembler.pending, 1)
        self.assertEqual(reassembler.accept(parts[-1]), ENVELOPE)
        self.assertEqual((reassembler.completed, reassembler.pending), (1, 0))

    def test_duplicates_are_ignored_and_interleaved_tags_kept_apart(self):
        first, second = fragment(ENVELOPE, 1), fragment(bytes(ENVELOPE_SIZE), 2)
        reassembler = Reassembler()
        for a, b in zip(first, second):
            reassembler.accept(a)
            self.assertIsNone(reassembler.accept(a))
            reassembler.accept(b)
        self.assertEqual(reassembler.completed, 2)
        # A repeat of the final fragment arrives after completion and simply
        # starts a new incomplete tag; the other five repeats are ignored.
        self.assertEqual(reassembler.ignored_duplicates, FRAGMENT_COUNT - 1)
        self.assertEqual(reassembler.pending, 1)

    def test_oldest_incomplete_envelope_is_evicted(self):
        reassembler = Reassembler()
        starts = [fragment(ENVELOPE, tag)[0] for tag in range(MAX_PENDING + 1)]
        for payload in starts:
            reassembler.accept(payload)
        self.assertEqual((reassembler.pending, reassembler.evicted), (MAX_PENDING, 1))
        for payload in fragment(ENVELOPE, 0)[1:]:
            self.assertIsNone(reassembler.accept(payload))
        self.assertEqual(reassembler.completed, 0)

    def test_malformed_input_is_rejected(self):
        for bad_envelope in (ENVELOPE[:-1], ENVELOPE + b'\0', 'text'):
            with self.assertRaises(FragmentError):
                fragment(bad_envelope, 0)
        for bad_tag in (-1, 1 << 16, 1.0):
            with self.assertRaises(FragmentError):
                fragment(ENVELOPE, bad_tag)
        good = fragment(ENVELOPE, 3)[0]
        for bad in (good[:-1], good + b'\0', good[:2] + b'\x06\x06' + good[4:], good[:3] + b'\x05' + good[4:]):
            with self.assertRaises(FragmentError):
                Reassembler().accept(bad)


if __name__ == '__main__':
    unittest.main()
