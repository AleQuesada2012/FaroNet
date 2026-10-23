"""Fixed-size onion envelopes: sizes, layering, tampering and impersonation."""

import unittest

from nacl.public import Box, PrivateKey, SealedBox

from faronet.node.envelope import (
    BOX_OVERHEAD, ENVELOPE_SIZE, LENGTH_PREFIX, MAX_TEXT_BYTES, MESSAGE_SIZE, NONCE_SIZE,
    RELAY_HOPS, SEAL_OVERHEAD, Delivery, EnvelopeError, PrivateMessage, Relay, Route,
    build_envelope, peel,
)
from faronet.node.identity import Directory, DirectoryError, Identity

NOW = 1791561600


def mesh(count: int = 6) -> tuple[list[Identity], Directory]:
    identities = [Identity.generate() for _ in range(count)]
    directory = Directory()
    for identity in identities:
        directory.add(identity.directory_entry(NOW, NOW + 3600), NOW)
    return identities, directory


class SizeTests(unittest.TestCase):
    def test_constants_match_pynacl_and_the_link_budget(self):
        key = PrivateKey.generate()
        self.assertEqual(len(SealedBox(key.public_key).encrypt(b'')), SEAL_OVERHEAD)
        self.assertEqual(len(Box(key, key.public_key).encrypt(b'')), BOX_OVERHEAD)
        self.assertEqual(ENVELOPE_SIZE, 492)
        self.assertEqual(MESSAGE_SIZE, 190)
        self.assertEqual(MAX_TEXT_BYTES, 178)
        self.assertEqual(RELAY_HOPS, 3)


class PrivateMessageTests(unittest.TestCase):
    def test_round_trip_and_fixed_size(self):
        for text in ('', 'hola', 'a' * MAX_TEXT_BYTES, 'ñ' * (MAX_TEXT_BYTES // 2)):
            message = PrivateMessage(text, NOW)
            padded = message.encode()
            self.assertEqual(len(padded), MESSAGE_SIZE)
            self.assertEqual(PrivateMessage.decode(padded), message)

    def test_oversized_and_invalid_messages_fail_explicitly(self):
        with self.assertRaises(EnvelopeError):
            PrivateMessage('a' * (MAX_TEXT_BYTES + 1), NOW)
        with self.assertRaises(EnvelopeError):
            PrivateMessage('ñ' * (MAX_TEXT_BYTES // 2 + 1), NOW)
        for expires in (-1, 1 << 64, 1.0, '1'):
            with self.assertRaises(EnvelopeError):
                PrivateMessage('x', expires)
        with self.assertRaises(EnvelopeError):
            PrivateMessage(b'bytes', NOW)

    def test_decode_rejects_bad_version_kind_length_padding_and_utf8(self):
        good = bytearray(PrivateMessage('ok', NOW).encode())
        variants = []
        for position, value in ((0, 2), (1, 2), (11, 0xff), (MESSAGE_SIZE - 1, 1), (12, 0xff)):
            damaged = bytearray(good)
            damaged[position] = value
            variants.append(bytes(damaged))
        variants += [bytes(good[:-1]), bytes(good) + b'\0']
        for raw in variants:
            with self.assertRaises(EnvelopeError):
                PrivateMessage.decode(raw)


class RouteTests(unittest.TestCase):
    def test_route_shape(self):
        ids = [bytes([i]) * 16 for i in range(5)]
        Route(tuple(ids[:3]), ids[3])
        for relays, destination in (
            (tuple(ids[:2]), ids[3]), (tuple(ids[:4]), ids[4]), ((ids[0], ids[0], ids[1]), ids[3]),
            (tuple(ids[:3]), ids[2]), ((b'short', ids[1], ids[2]), ids[3]),
        ):
            with self.assertRaises(EnvelopeError):
                Route(relays, destination)


class OnionTests(unittest.TestCase):
    def setUp(self):
        self.identities, self.directory = mesh()
        self.sender, *self.relays, self.destination, self.outsider = self.identities
        self.route = Route(tuple(r.node_id for r in self.relays), self.destination.node_id)
        self.message = PrivateMessage('synthetic', NOW + 60)

    def test_three_relays_then_destination(self):
        envelope = build_envelope(self.sender, self.directory, self.route, self.message)
        hops = []
        for relay in self.relays:
            self.assertEqual(len(envelope), ENVELOPE_SIZE)
            result = peel(relay, self.directory, envelope)
            self.assertIsInstance(result, Relay)
            hops.append(result.next_hop)
            self.assertNotEqual(result.envelope, envelope)
            envelope = result.envelope
        self.assertEqual(hops, [self.relays[1].node_id, self.relays[2].node_id, self.destination.node_id])
        delivery = peel(self.destination, self.directory, envelope)
        self.assertIsInstance(delivery, Delivery)
        self.assertEqual(delivery.sender_id, self.sender.node_id)
        self.assertEqual(delivery.message, self.message)
        self.assertEqual(len(delivery.nonce), NONCE_SIZE)

    def test_same_message_twice_produces_unrelated_envelopes(self):
        first = build_envelope(self.sender, self.directory, self.route, self.message)
        second = build_envelope(self.sender, self.directory, self.route, self.message)
        self.assertNotEqual(first, second)
        self.assertEqual(first[:LENGTH_PREFIX], second[:LENGTH_PREFIX])

    def test_only_the_addressed_node_can_peel_each_layer(self):
        envelope = build_envelope(self.sender, self.directory, self.route, self.message)
        for wrong in (self.relays[1], self.relays[2], self.destination, self.outsider, self.sender):
            with self.assertRaises(EnvelopeError):
                peel(wrong, self.directory, envelope)
        second = peel(self.relays[0], self.directory, envelope).envelope
        with self.assertRaises(EnvelopeError):
            peel(self.relays[0], self.directory, second)

    def test_tampering_and_bad_shapes_are_rejected(self):
        envelope = build_envelope(self.sender, self.directory, self.route, self.message)
        for position in (0, 1, LENGTH_PREFIX, LENGTH_PREFIX + 100):
            damaged = bytearray(envelope)
            damaged[position] ^= 0x01
            with self.assertRaises(EnvelopeError):
                peel(self.relays[0], self.directory, bytes(damaged))
        for bad in (envelope[:-1], envelope + b'\0', b'', bytes(ENVELOPE_SIZE), 'text'):
            with self.assertRaises(EnvelopeError):
                peel(self.relays[0], self.directory, bad)
        # The outer layer fills the envelope; later layers carry random padding
        # that no relay authenticates, so changing it must not break forwarding.
        second = bytearray(peel(self.relays[0], self.directory, envelope).envelope)
        second[-1] ^= 0xff
        self.assertIsInstance(peel(self.relays[1], self.directory, bytes(second)), Relay)

    def test_sender_cannot_be_in_route_and_unknown_hops_fail(self):
        with self.assertRaises(EnvelopeError):
            build_envelope(self.sender, self.directory, Route(
                (self.sender.node_id, *self.route.relays[1:]), self.destination.node_id,
            ), self.message)
        with self.assertRaises(DirectoryError):
            build_envelope(self.sender, self.directory, Route(self.route.relays, bytes(16)), self.message)

    def test_impersonating_a_sender_fails_authentication(self):
        attacker = self.outsider
        nonce = bytes(NONCE_SIZE)
        forged = Box(attacker.box_key, self.destination.public_key).encrypt(self.message.encode(), nonce).ciphertext
        inner = bytes([2]) + self.sender.node_id + nonce + forged
        layer = SealedBox(self.destination.public_key).encrypt(inner)
        envelope = len(layer).to_bytes(2, 'big') + layer
        envelope += bytes(ENVELOPE_SIZE - len(envelope))
        with self.assertRaises(EnvelopeError):
            peel(self.destination, self.directory, envelope)

    def test_unknown_sender_cannot_be_delivered(self):
        stranger = Identity.generate()
        directory = Directory()
        for identity in (*self.relays, self.destination):
            directory.add(identity.directory_entry(NOW, NOW + 60), NOW)
        envelope = build_envelope(stranger, directory, self.route, self.message)
        for relay in self.relays:
            envelope = peel(relay, directory, envelope).envelope
        with self.assertRaises(DirectoryError):
            peel(self.destination, directory, envelope)

    def test_errors_do_not_leak_ids_or_text(self):
        envelope = build_envelope(self.sender, self.directory, self.route, self.message)
        with self.assertRaises(EnvelopeError) as error:
            peel(self.outsider, self.directory, envelope)
        text = str(error.exception)
        for secret in (self.sender.node_id.hex(), self.destination.node_id.hex(), 'synthetic'):
            self.assertNotIn(secret, text)


if __name__ == '__main__':
    unittest.main()
