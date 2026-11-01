"""Gateway client: dead-drop format and signed requests against a local verifying stub."""

import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch

from faronet.gateway import commands
from faronet.gateway.auth import GatewayRequest, verify_and_admit, AuthError
from faronet.gateway.client import (
    DROP_BYTES, MAX_DROP_TEXT, EdgeClient, GatewayError, drop_slot_id, fetch_directory, open_drop,
    seal_drop, secret_from_hex,
)
from faronet.node.identity import DirectoryEntry, Identity
from faronet.gateway.testing import FakeNonceStore

GATEWAY_SECRET = bytes(range(32))     # synthetic test value only
SHARED = bytes(range(32, 64))


class DropFormatTests(unittest.TestCase):
    def test_blob_is_fixed_size_and_round_trips(self):
        for text in ("", "nos vemos en la biblioteca", "é" * (MAX_DROP_TEXT // 2)):
            blob = seal_drop(SHARED, text)
            self.assertEqual(len(blob), DROP_BYTES)
            self.assertEqual(open_drop(SHARED, blob), text)
        self.assertNotEqual(seal_drop(SHARED, "x"), seal_drop(SHARED, "x"))  # fresh nonce
        with self.assertRaises(GatewayError):
            seal_drop(SHARED, "a" * (MAX_DROP_TEXT + 1))

    def test_wrong_secret_tampering_and_size_are_rejected(self):
        blob = bytearray(seal_drop(SHARED, "secreto"))
        with self.assertRaises(GatewayError):
            open_drop(bytes(32), bytes(blob))
        blob[100] ^= 1
        with self.assertRaises(GatewayError):
            open_drop(SHARED, bytes(blob))
        with self.assertRaises(GatewayError):
            open_drop(SHARED, bytes(blob[:-1]))

    def test_slot_ids_follow_the_documented_derivation(self):
        expected = hashlib.sha256(b"FARONET-DEAD-DROP-ID-V1" + SHARED + (7).to_bytes(8, "big")).hexdigest()
        self.assertEqual(drop_slot_id(SHARED, 7), expected)
        self.assertNotEqual(drop_slot_id(SHARED, 7), drop_slot_id(SHARED, 8))
        self.assertNotIn(SHARED.hex(), expected)
        for bad in ((bytes(31), 1), (SHARED, -1), (SHARED, 1 << 64)):
            with self.assertRaises(GatewayError):
                drop_slot_id(*bad)

    def test_secrets_must_be_hex_and_long_enough(self):
        self.assertEqual(secret_from_hex("ab" * 32), b"\xab" * 32)
        for bad in ("", "zz" * 32, "ab" * 31):
            with self.assertRaises(GatewayError):
                secret_from_hex(bad)


class EdgeStub(BaseHTTPRequestHandler):
    """Verifies the HMAC exactly as the Edge does, then mimics its routes in memory."""

    store = FakeNonceStore()
    slots: dict = {}
    published: list = []
    agents: list = []
    directory: dict = {}
    extra: list = []
    now = 1_792_000_000   # None: the real clock

    def log_message(self, *_):
        pass

    def _handle(self, method):
        if method == "GET" and self.path == "/directory":
            entries = [e.hex() for e in self.directory.values()] + self.extra
            return self._reply(200, json.dumps({"version": 1, "entries": entries}).encode())
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.agents.append(self.headers.get("User-Agent", ""))
        request = GatewayRequest("faronet-edge", self.headers["X-FaroNet-Key"], method, self.path,
                                 self.headers["X-FaroNet-Timestamp"], self.headers["X-FaroNet-Nonce"], body)
        try:
            verify_and_admit(request, self.headers["X-FaroNet-Signature"], GATEWAY_SECRET,
                             expected_audience="faronet-edge", expected_key_id="gateway-1",
                             clock=lambda: EdgeStub.now or int(time.time()), store=self.store)
        except AuthError:
            return self._reply(401)
        if self.path == "/gateway/directory":
            entry = DirectoryEntry.decode(body)
            current = self.directory.get(entry.node_id)
            if current is not None and DirectoryEntry.decode(current).issued_at > entry.issued_at:
                return self._reply(409)
            self.directory[entry.node_id] = body
            return self._reply(201)
        if self.path.startswith("/gateway/rooms/"):
            self.published.append(body.decode())
            return self._reply(202)
        slot = self.path.rsplit("/", 1)[1]
        if method == "POST":
            if slot in self.slots or len(body) != DROP_BYTES:
                return self._reply(409)
            self.slots[slot] = body
            return self._reply(201)
        blob = self.slots.pop(slot, None)
        return self._reply(404) if blob is None else self._reply(200, blob)

    def _reply(self, status, body=b""):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._handle("POST")

    def do_GET(self):
        self._handle("GET")


class EdgeClientTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), EdgeStub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = EdgeClient(url, GATEWAY_SECRET, clock=lambda: 1_792_000_000)

    def test_publish_and_dead_drop_round_trip_through_signed_requests(self):
        self.client.publish("demo", "aviso público")
        self.assertEqual(EdgeStub.published[-1], "aviso público")
        self.client.drop_put(SHARED, 3, "nos vemos a las 8")
        with self.assertRaises(GatewayError) as occupied:
            self.client.drop_put(SHARED, 3, "otro")
        self.assertEqual(occupied.exception.status, 409)
        self.assertEqual(self.client.drop_take(SHARED, 3), "nos vemos a las 8")
        self.assertIsNone(self.client.drop_take(SHARED, 3))
        self.assertNotIn(SHARED.hex(), "".join(EdgeStub.slots))
        # Cloudflare blocks "Python-urllib" with 403 before the Worker runs.
        self.assertTrue(all(agent.startswith("FaroNet-Gateway/") for agent in EdgeStub.agents))

    def test_directory_entries_publish_and_fetch_verified(self):
        identity = Identity.generate()
        newer = identity.directory_entry(1_792_000_000, 1_792_000_000 + 3600, "pi-gw")
        older = identity.directory_entry(1_791_999_000, 1_791_999_000 + 3600, "pi-gw")
        self.assertTrue(self.client.publish_entry(newer))
        self.assertFalse(self.client.publish_entry(older))
        forged = bytearray(newer.encode())
        forged[-1] ^= 1
        EdgeStub.extra = [bytes(forged).hex(), "zz"]
        entries, rejected = fetch_directory(self.client.base_url, now=1_792_000_100)
        EdgeStub.extra = []
        self.assertIn(newer, entries)
        self.assertEqual(rejected, 2)
        _, rejected = fetch_directory(self.client.base_url, now=1_792_000_000 + 7200)
        self.assertGreaterEqual(rejected, 1)  # expired entries are not trusted

    def test_gateway_mesh_node_publishes_what_it_learns(self):
        from faronet.node import chat
        from faronet.node.lan import LanNode

        async def scenario():
            lan = LanNode(Identity.generate(), "gw-node")
            with patch.dict(os.environ, {"FARONET_GATEWAY_SECRET": GATEWAY_SECRET.hex()}), \
                    patch.object(EdgeStub, "now", None), patch("sys.stdout", io.StringIO()):
                chat._publish_directory(lan, self.client.base_url)
                for _ in range(200):
                    if lan.node_id in EdgeStub.directory:
                        break
                    await asyncio.sleep(0.01)
            await lan.close()
            return lan.node_id

        node_id = asyncio.run(scenario())
        self.assertIn(node_id, EdgeStub.directory)

    def test_wrong_gateway_secret_is_refused(self):
        client = EdgeClient(self.client.base_url, bytes(32), clock=lambda: 1_792_000_000)
        with self.assertRaises(GatewayError) as refused:
            client.publish("demo", "x")
        self.assertEqual(refused.exception.status, 401)

    def test_unreachable_edge_is_a_static_error(self):
        client = EdgeClient("http://127.0.0.1:9", GATEWAY_SECRET, timeout=1)
        with self.assertRaisesRegex(GatewayError, "^No se pudo contactar el edge$"):
            client.publish("demo", "x")


class SecretFileTests(unittest.TestCase):
    def test_secret_is_stored_owner_only_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.dict(os.environ, {"FARONET_STATE_DIR": folder}, clear=False):
            os.environ.pop("FARONET_GATEWAY_SECRET", None)
            with self.assertRaises(GatewayError):
                commands.load_secret()
            with patch("getpass.getpass", return_value="ab" * 32), patch("sys.stdout", io.StringIO()):
                self.assertEqual(commands.run(type("A", (), {"command": "gateway-secret"})()), 0)
            path = Path(folder) / "gateway-secret"
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(commands.load_secret(), b"\xab" * 32)
            with patch.dict(os.environ, {"FARONET_GATEWAY_SECRET": "cd" * 32}):
                self.assertEqual(commands.load_secret(), b"\xcd" * 32)
            with patch("getpass.getpass", return_value="not-hex"), patch("sys.stderr", io.StringIO()):
                self.assertEqual(commands.run(type("A", (), {"command": "gateway-secret"})()), 2)
            self.assertEqual(commands.load_secret(), b"\xab" * 32)


if __name__ == "__main__":
    unittest.main()
