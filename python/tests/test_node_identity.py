"""Signed directory entries: shared vector, tampering, lifetime and clock rules."""

from dataclasses import replace
import json
from pathlib import Path
import unittest

from faronet.node.identity import (
    MAX_LIFETIME, Directory, DirectoryEntry, DirectoryError, Identity, node_id_for,
)

VECTOR = json.loads((Path(__file__).parents[2] / 'fixtures/directory-v1.json').read_text())['vectors'][0]


def fixture_identity() -> Identity:
    return Identity.from_seeds(bytes.fromhex(VECTOR['signing_seed_hex']), bytes.fromhex(VECTOR['box_seed_hex']))


class DirectoryEntryTests(unittest.TestCase):
    def setUp(self):
        self.identity = fixture_identity()
        self.entry = self.identity.directory_entry(VECTOR['issued_at'], VECTOR['expires_at'], VECTOR['alias'])

    def test_shared_vector_is_reproduced_exactly(self):
        self.assertEqual(self.entry.node_id.hex(), VECTOR['node_id_hex'])
        self.assertEqual(self.entry.verify_key.hex(), VECTOR['verify_key_hex'])
        self.assertEqual(self.entry.public_key.hex(), VECTOR['public_key_hex'])
        self.assertEqual(self.entry.signed_bytes().hex(), VECTOR['signed_hex'])
        self.assertEqual(self.entry.signature.hex(), VECTOR['signature_hex'])
        self.assertEqual(self.entry.encode().hex(), VECTOR['entry_hex'])
        self.assertEqual(DirectoryEntry.decode(bytes.fromhex(VECTOR['entry_hex'])), self.entry)

    def test_node_id_is_derived_from_the_verify_key(self):
        self.assertEqual(node_id_for(self.entry.verify_key), self.entry.node_id)
        with self.assertRaises(DirectoryError):
            replace(self.entry, node_id=bytes(16))
        with self.assertRaises(DirectoryError):
            node_id_for(b'short')

    def test_every_byte_of_the_entry_is_covered(self):
        raw = self.entry.encode()
        for position in range(len(raw)):
            damaged = bytearray(raw)
            damaged[position] ^= 0x01
            with self.subTest(position=position):
                with self.assertRaises(DirectoryError):
                    DirectoryEntry.decode(bytes(damaged))

    def test_wrong_lengths_and_prefix_are_rejected(self):
        raw = self.entry.encode()
        for bad in (raw[:-1], raw + b'\0', raw[1:], b'X' + raw[1:], b''):
            with self.assertRaises(DirectoryError):
                DirectoryEntry.decode(bad)

    def test_lifetime_and_alias_rules(self):
        issued = VECTOR['issued_at']
        for expires in (issued, issued - 1, issued + MAX_LIFETIME + 1):
            with self.assertRaises(DirectoryError):
                self.identity.directory_entry(issued, expires)
        self.identity.directory_entry(issued, issued + MAX_LIFETIME)
        for alias in ('a' * 17, 'café', 'two words', 'dot.name', 5):
            with self.assertRaises(DirectoryError):
                self.identity.directory_entry(issued, issued + 1, alias)
        self.assertEqual(self.identity.directory_entry(issued, issued + 1, '').alias, '')

    def test_clock_policy(self):
        issued, expires = self.entry.issued_at, self.entry.expires_at
        for now in (issued - 60, issued, expires):
            self.entry.check_valid_at(now)
        for now in (issued - 61, expires + 1):
            with self.assertRaises(DirectoryError):
                self.entry.check_valid_at(now)
        with self.assertRaises(DirectoryError):
            self.entry.check_valid_at(-1)

    def test_identity_never_prints_keys(self):
        text = repr(self.identity)
        self.assertNotIn(VECTOR['signing_seed_hex'], text)
        self.assertNotIn(VECTOR['verify_key_hex'], text)
        self.assertNotEqual(Identity.generate().node_id, Identity.generate().node_id)


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.identity = fixture_identity()
        self.now = VECTOR['issued_at']
        self.directory = Directory()

    def test_only_valid_entries_are_stored(self):
        entry = self.identity.directory_entry(self.now, self.now + 100, 'a')
        self.directory.add(entry, self.now)
        self.assertEqual(self.directory.get(entry.node_id), entry)
        self.assertIn(entry.node_id, self.directory)
        with self.assertRaises(DirectoryError):
            self.directory.add(entry, self.now + 101)
        with self.assertRaises(DirectoryError):
            self.directory.get(bytes(16))

    def test_newer_entries_replace_older_ones_only(self):
        older = self.identity.directory_entry(self.now, self.now + 100, 'old')
        newer = self.identity.directory_entry(self.now + 10, self.now + 100, 'new')
        self.directory.add(newer, self.now + 10)
        with self.assertRaises(DirectoryError):
            self.directory.add(older, self.now + 10)
        self.assertEqual(self.directory.get(self.identity.node_id).alias, 'new')
        self.assertEqual(len(self.directory), 1)
        self.assertEqual(self.directory.node_ids(), (self.identity.node_id,))


if __name__ == '__main__':
    unittest.main()
