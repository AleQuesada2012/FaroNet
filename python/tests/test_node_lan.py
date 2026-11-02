"""LAN mesh links over real localhost TCP: records, proofs, gossip, routing and chat."""

import asyncio
import unittest

from faronet.node.chat import ChatSession, address
from faronet.node.fragment import ENVELOPE_SIZE
from faronet.node.identity import Identity
from faronet.node.lan import (
    ENTRY_LIFETIME, ENTRY_REISSUE, RECORD_SIZE, LanError, LanNode, LinksRecord, RecordType,
    decode_record, encode_record,
)


class RecordTests(unittest.TestCase):
    def test_every_record_has_one_fixed_size(self):
        envelope = bytes(range(256)) * 2
        raw = encode_record(RecordType.ENVELOPE, envelope[:ENVELOPE_SIZE])
        self.assertEqual(len(raw), RECORD_SIZE)
        self.assertEqual(decode_record(raw), (RecordType.ENVELOPE, envelope[:ENVELOPE_SIZE]))
        for body in (b"", b"entry", bytes(ENVELOPE_SIZE - 2)):
            raw = encode_record(RecordType.ENTRY, body)
            self.assertEqual(len(raw), RECORD_SIZE)
            self.assertEqual(decode_record(raw), (RecordType.ENTRY, body))

    def test_malformed_records_are_rejected(self):
        raw = encode_record(RecordType.LINKS, b"abc")
        for bad in (raw[:-1], b"\x09" + raw[1:], raw[:-1] + b"\x01",
                    raw[:1] + (ENVELOPE_SIZE).to_bytes(2, "big") + raw[3:]):
            with self.assertRaises(LanError):
                decode_record(bad)
        with self.assertRaises(LanError):
            encode_record(RecordType.ENVELOPE, b"short")
        with self.assertRaises(LanError):
            encode_record(RecordType.ENTRY, bytes(ENVELOPE_SIZE - 1))

    def test_links_record_is_signed_bounded_and_canonical(self):
        lan = LanNode(Identity.generate(), "a")
        others = [Identity.generate().node_id for _ in range(17)]
        record = LinksRecord.sign(lan.identity, 5, others[:3])
        decoded = LinksRecord.decode(record.encode())
        self.assertEqual(decoded, record)
        self.assertEqual(list(decoded.neighbors), sorted(others[:3]))
        decoded.verify(lan.directory)
        forged = bytearray(record.encode())
        forged[-70] ^= 1  # A neighbor ID byte; the signature no longer matches.
        with self.assertRaises(LanError):
            LinksRecord.decode(bytes(forged)).verify(lan.directory)
        for neighbors in (others, [others[0]] * 2, [lan.node_id]):
            with self.assertRaises(LanError):
                LinksRecord.sign(lan.identity, 5, neighbors)
        unsorted = bytearray(record.encode())
        first = len(b"FARONET-LINKS-V1") + 16 + 8 + 1
        unsorted[first:first + 32] = unsorted[first + 16:first + 32] + unsorted[first:first + 16]
        with self.assertRaises(LanError):  # The RFC requires ascending order.
            LinksRecord.decode(bytes(unsorted))

    def test_addresses_parse_with_default_port(self):
        self.assertEqual(address("10.0.0.5"), ("10.0.0.5", 7400))
        self.assertEqual(address("pi-a.local:7401"), ("pi-a.local", 7401))
        self.assertEqual(address("[fe80::1]:9"), ("fe80::1", 9))
        for bad in ("host:port", "host:70000", ":7400"):
            with self.assertRaises(ValueError):
                address(bad)


async def wait_for(condition, seconds=5.0):
    deadline = asyncio.get_running_loop().time() + seconds
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Condition not reached in time")
        await asyncio.sleep(0.01)


class LanMeshTests(unittest.IsolatedAsyncioTestCase):
    async def start(self, count, alias="n"):
        nodes = [LanNode(Identity.generate(), f"{alias}{i}", forward_delay_ms=0) for i in range(count)]
        ports = [await node.listen("127.0.0.1", 0) for node in nodes]
        for node in nodes:
            self.addAsyncCleanup(node.close)
        return nodes, ports

    async def line(self, count):
        """n0 - n1 - ... - n(count-1); each link dialed by its left end."""
        nodes, ports = await self.start(count)
        for left, port in zip(nodes, ports[1:]):
            left.dial("127.0.0.1", port)
        await wait_for(lambda: all(node.routes_to(nodes[-1].node_id) or node is nodes[-1]
                                   for node in nodes[:1])
                       and all(len(node.directory) == count for node in nodes))
        return nodes

    async def test_message_and_reply_cross_three_relays(self):
        nodes = await self.line(5)
        inbox = {0: [], 4: []}
        nodes[0].on_delivery = inbox[0].append
        nodes[4].on_delivery = inbox[4].append
        route = nodes[0].send_text(nodes[4].node_id, "hola por la mesh", 300)
        self.assertEqual(route.relays, tuple(n.node_id for n in nodes[1:4]))
        await wait_for(lambda: inbox[4])
        self.assertEqual(inbox[4][0].message.text, "hola por la mesh")
        self.assertEqual(inbox[4][0].sender_id, nodes[0].node_id)
        self.assertEqual([n.counters["relayed"] for n in nodes[1:4]], [1, 1, 1])

        await wait_for(lambda: nodes[4].routes_to(nodes[0].node_id))
        nodes[4].send_text(nodes[0].node_id, "recibido", 300)
        await wait_for(lambda: inbox[0])
        self.assertEqual(inbox[0][0].message.text, "recibido")
        self.assertEqual([n.counters["relayed"] for n in nodes[1:4]], [2, 2, 2])
        self.assertEqual(sum(n.counters["rejected"] for n in nodes), 0)

    async def test_no_route_until_three_relays_exist_and_links_drop(self):
        nodes, ports = await self.start(4)
        for left, port in zip(nodes, ports[1:]):
            left.dial("127.0.0.1", port)
        await wait_for(lambda: all(len(node.directory) == 4 for node in nodes))
        with self.assertRaises(LanError):
            nodes[0].send_text(nodes[3].node_id, "x", 300)  # Only two relays in between.

        nodes, ports = await self.start(5, "m")
        for left, port in zip(nodes, ports[1:]):
            left.dial("127.0.0.1", port)
        await wait_for(lambda: nodes[0].routes_to(nodes[4].node_id))
        await nodes[2].close()  # The middle relay leaves; its neighbors stop listing it.
        await wait_for(lambda: not nodes[0].routes_to(nodes[4].node_id))

    async def test_entry_is_re_signed_every_12_hours_and_reaches_peers(self):
        now = [1_800_000_000]
        clock = lambda: now[0]
        a, b = (LanNode(Identity.generate(), alias, clock=clock, forward_delay_ms=0)
                for alias in ("a", "b"))
        for node in (a, b):
            self.addAsyncCleanup(node.close)
        port = await b.listen("127.0.0.1", 0)
        a.dial("127.0.0.1", port)
        await wait_for(lambda: a.node_id in b.directory)
        first = a.entry

        now[0] += ENTRY_REISSUE - 1
        self.assertFalse(a.reissue_entry())
        now[0] += 1
        self.assertTrue(a.reissue_entry())
        self.assertEqual(a.entry.issued_at, now[0])
        self.assertEqual(a.entry.expires_at, now[0] + ENTRY_LIFETIME)
        self.assertEqual(a.entry.alias, first.alias)
        self.assertIs(a.directory.get(a.node_id), a.entry)
        await wait_for(lambda: b.directory.get(a.node_id) == a.entry)

        # Past the first entry's expiry the peer still holds a usable entry.
        now[0] = first.expires_at + 1
        b.directory.get(a.node_id).check_valid_at(now[0])

    async def test_impostor_replaying_an_entry_is_never_linked(self):
        nodes, ports = await self.start(1)
        victim = LanNode(Identity.generate(), "victim")
        reader, writer = await asyncio.open_connection("127.0.0.1", ports[0])
        writer.write(encode_record(RecordType.HELLO, victim.entry.encode() + bytes(32)))
        kind, _ = decode_record(await reader.readexactly(RECORD_SIZE))
        self.assertEqual(kind, RecordType.HELLO)
        kind, _ = decode_record(await reader.readexactly(RECORD_SIZE))
        self.assertEqual(kind, RecordType.PROOF)
        writer.write(encode_record(RecordType.PROOF, bytes(64)))  # Cannot sign as the victim.
        self.assertEqual(await reader.read(), b"")  # Closed without a link.
        writer.close()
        self.assertEqual(nodes[0].neighbors(), ())
        self.assertNotIn(victim.node_id, nodes[0].directory)
        self.assertEqual(nodes[0].counters["link_errors"], 1)

    async def test_links_dialed_from_both_sides_settle_on_one(self):
        nodes, ports = await self.start(2)
        nodes[0].dial("127.0.0.1", ports[1])
        nodes[1].dial("127.0.0.1", ports[0])
        await wait_for(lambda: all(len(n.neighbors()) == 1 for n in nodes))
        await asyncio.sleep(0.3)
        self.assertEqual([len(n.neighbors()) for n in nodes], [1, 1])
        preferred = min(n.node_id for n in nodes)
        self.assertTrue(all(n._neighbors[other.node_id].dialer == preferred
                            for n, other in (nodes, nodes[::-1])))

    async def test_chat_commands_route_and_reply(self):
        nodes = await self.line(5)
        outputs = {0: [], 4: []}
        alice = ChatSession(nodes[0], outputs[0].append)
        bob = ChatSession(nodes[4], outputs[4].append)
        self.assertTrue(alice.handle("hola\n"))
        self.assertIn("Primero elige un destino", outputs[0][-1])
        alice.handle("/peers")
        self.assertTrue(any("n4#" in line and "con ruta" in line for line in outputs[0]))
        alice.handle("/to n4")
        alice.handle("/ttl 5")
        self.assertIn("El TTL debe", outputs[0][-1])
        alice.handle("/ttl 60")
        alice.handle("é" * 100)
        self.assertIn("excede", outputs[0][-1])
        alice.handle("hola bob")
        self.assertTrue(outputs[0][-1].startswith("· enviado por n1#"))
        await wait_for(lambda: any(line.endswith("] hola bob") for line in outputs[4]))
        self.assertIn("las respuestas van a n0#", outputs[4][-1])
        await wait_for(lambda: nodes[4].routes_to(nodes[0].node_id))
        bob.handle("hola alice")
        await wait_for(lambda: any(line.endswith("] hola alice") for line in outputs[0]))
        # Remote text cannot forge a line or send terminal escapes.
        bob.handle("hola\n[n9#00000000] falso \x1b[2J")
        await wait_for(lambda: any("falso" in line for line in outputs[0]))
        shown = next(line for line in outputs[0] if "falso" in line)
        self.assertTrue(shown.isprintable() and shown.startswith("[n4#"))
        self.assertFalse(alice.handle("/quit"))


if __name__ == "__main__":
    unittest.main()
