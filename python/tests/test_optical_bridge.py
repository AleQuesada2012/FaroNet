"""A mesh hop over light: two optical bridges on a fake light path, real LanNodes over TCP."""

import argparse
import asyncio
import queue
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from faronet.node import chat
from faronet.faro.bridge import WireDecoder, encode_wire, epoch_session, serve_bridge
from faronet.node.fragment import ENVELOPE_SIZE
from faronet.node.identity import Identity
from faronet.node.lan import RECORD_SIZE, LanError, LanNode, RecordType, encode_record
from tests.test_node_lan import wait_for

A, B, SESSION = b"\x01" * 8, b"\x02" * 8, b"S" * 8
HALF = 0.0002  # DIFS 12.8 ms and an ACK deadline of 1.2 s keep the tests short.


class Light:
    """Both directions of one optical path; `blocked` drops every frame in flight."""

    def __init__(self):
        self.blocked = False
        self.ends = (LightEnd(self, 0), LightEnd(self, 1))


class LightEnd:
    frame_seconds = 2048 * HALF
    half_ns = int(HALF * 1e9)

    def __init__(self, light, index):
        self.light, self.index = light, index
        self.incoming: queue.Queue = queue.Queue()
        self.peer_light_end = 0.0
        self.transmitted = []

    def guard(self):
        pass

    def transmit(self, frame):
        self.transmitted.append(frame)
        peer = self.light.ends[1 - self.index]
        peer.peer_light_end = time.monotonic()
        if not self.light.blocked:
            peer.incoming.put(frame)

    def receive(self, timeout):
        try:
            return self.incoming.get(timeout=timeout)
        except queue.Empty:
            return None

    def channel(self):
        return self.peer_light_end, False

    def clear(self):
        pass


class WireTests(unittest.TestCase):
    def test_control_records_travel_without_padding_and_envelopes_stay_fixed(self):
        envelope = encode_record(RecordType.ENVELOPE, (bytes(range(256)) * 2)[:ENVELOPE_SIZE])
        entry = encode_record(RecordType.ENTRY, b"public entry")
        self.assertEqual(len(encode_wire(envelope)), RECORD_SIZE)
        self.assertEqual(encode_wire(entry), entry[:3 + len(b"public entry")])
        decoder = WireDecoder()
        stream = encode_wire(entry) + encode_wire(envelope) + encode_wire(entry)
        records = []
        for start in range(0, len(stream), 86):  # As Faro payloads arrive.
            records += decoder.feed(stream[start:start + 86])
        self.assertEqual(records, [entry, envelope, entry])

    def test_garbage_on_the_light_stream_is_rejected(self):
        for bad in (b"\x09", b"\x03" + (ENVELOPE_SIZE).to_bytes(2, "big")):
            with self.assertRaises(LanError):
                WireDecoder().feed(bad)

    def test_epoch_sessions_are_distinct_and_derived_from_the_base(self):
        sessions = {epoch_session(SESSION, epoch) for epoch in range(100)}
        self.assertEqual(len(sessions), 100)
        self.assertTrue(all(len(s) == 8 for s in sessions))
        self.assertNotEqual(epoch_session(SESSION, 0), epoch_session(b"T" * 8, 0))


class Bridge:
    """serve_bridge in a thread, as the optical-bridge process runs it on a Pi."""

    def __init__(self, test, io, local, peer):
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.stop = threading.Event()
        self.events = []
        self.stats = None
        self.thread = threading.Thread(target=self._run, args=(io, local, peer), daemon=True)
        self.thread.start()
        test.addCleanup(self.close)

    def _run(self, io, local, peer):
        self.stats = serve_bridge(io, local, peer, SESSION, self.listener, self.events.append,
                                  self.stop)

    def close(self):
        self.stop.set()
        self.thread.join(5)
        self.listener.close()


class OpticalHopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """n0 - n1 =light= n2 - n3 - n4: the optical hop is in the middle of every route."""
        self.light = Light()
        self.bridges = (Bridge(self, self.light.ends[0], A, B),
                        Bridge(self, self.light.ends[1], B, A))
        self.nodes = [LanNode(Identity.generate(), f"n{i}", forward_delay_ms=0) for i in range(5)]
        ports = [await node.listen("127.0.0.1", 0) for node in self.nodes]
        for node in self.nodes:
            self.addAsyncCleanup(node.close)
        self.nodes[0].dial("127.0.0.1", ports[1])
        self.nodes[1].dial("127.0.0.1", self.bridges[0].port, handshake_seconds=30)
        self.nodes[2].dial("127.0.0.1", self.bridges[1].port, handshake_seconds=30)
        self.nodes[2].dial("127.0.0.1", ports[3])
        self.nodes[3].dial("127.0.0.1", ports[4])
        await self.converged()

    async def converged(self):
        first, last = self.nodes[0], self.nodes[-1]
        await wait_for(lambda: first.routes_to(last.node_id) and last.routes_to(first.node_id)
                       and all(len(node.directory) == 5 for node in self.nodes), 30)

    async def exchange(self, text):
        inbox = {0: [], 4: []}
        self.nodes[0].on_delivery = inbox[0].append
        self.nodes[4].on_delivery = inbox[4].append
        self.nodes[0].send_text(self.nodes[4].node_id, text, 300)
        await wait_for(lambda: inbox[4], 30)
        self.nodes[4].send_text(self.nodes[0].node_id, "recibido", 300)
        await wait_for(lambda: inbox[0], 30)
        return inbox[4][0].message.text, inbox[0][0].message.text

    async def test_message_and_reply_cross_the_light(self):
        self.assertEqual(await self.exchange("hola por la luz"), ("hola por la luz", "recibido"))
        self.assertEqual(sum(n.counters["rejected"] for n in self.nodes), 0)
        self.assertIn(self.nodes[2].node_id, self.nodes[1].neighbors())
        sizes = [len(f.payload) for f in self.light.ends[0].transmitted if f.kind == 1]
        self.assertTrue(sizes and max(sizes) <= 86)

    async def test_failed_send_moves_both_sides_to_a_new_session(self):
        self.light.blocked = True
        self.nodes[1]._publish_links()  # Traffic that cannot cross; three attempts fail.
        await wait_for(lambda: any(e.get("epoch") == 1 for e in self.bridges[0].events), 15)
        self.light.blocked = False
        await wait_for(lambda: any(e.get("epoch", 0) >= 1 for e in self.bridges[1].events), 15)
        await wait_for(lambda: self.nodes[2].node_id in self.nodes[1].neighbors(), 30)
        await self.converged()
        self.assertEqual(await self.exchange("de nuevo"), ("de nuevo", "recibido"))


class ChatBridgeProcessTests(unittest.TestCase):
    """The chat starts optical-bridge as a process; its panic exit must become the Node's panic."""

    def fake_bridge(self, exit_code):
        script = ("import json, sys; print(json.dumps({'ready': 'optical-bridge', 'port': 7999, "
                  "'frame_seconds': 4.1}), flush=True); print(json.dumps({'epoch': 1, "
                  f"'reason': 'peer'}}), flush=True); sys.exit({exit_code})")
        real = subprocess.Popen

        def popen(command, **options):
            self.command = command
            return real([sys.executable, "-c", script], **options)
        return mock.patch.object(chat.subprocess, "Popen", popen)

    def args(self, **changes):
        values = dict(faro_peer=B, faro_session=SESSION, panic_gpio=None, chip="/dev/gpiochip0",
                      half_bit_ms=2.0, rx_inverted=False)
        return argparse.Namespace(**values | changes)

    def test_bridge_panic_exit_triggers_the_node_panic(self):
        lines = []
        with self.fake_bridge(chat.PANIC_EXIT), mock.patch.object(chat, "_print", lines.append):
            process, port = chat._start_bridge(self.args())
            panics = []
            chat._watch_bridge(process, lambda: panics.append(True))
        self.assertEqual(port, 7999)
        self.assertEqual(panics, [True])
        self.assertTrue(any("época 1" in line for line in lines))
        self.assertIn("optical-bridge", self.command)
        self.assertEqual(self.command[self.command.index("--peer") + 1], B.hex())

    def test_bridge_failure_is_reported_without_panic(self):
        lines = []
        with self.fake_bridge(2), mock.patch.object(chat, "_print", lines.append):
            process, _ = chat._start_bridge(self.args())
            panics = []
            chat._watch_bridge(process, lambda: panics.append(True))
        self.assertEqual(panics, [])
        self.assertIn("código 2", lines[-1])

    def test_bridge_options_are_checked_before_starting(self):
        for changes in ({"faro_session": None}, {"panic_gpio": "/dev/gpiochip0"}):
            with self.assertRaises(ValueError):
                chat._start_bridge(self.args(**changes))
