"""LAN links for the mesh: fixed-size records over TCP, link proofs and gossip.

Every record on a LAN link is RECORD_SIZE bytes: one type byte, then a
492-byte body. An envelope fills the body exactly; control records carry a
2-byte length and zero padding. The onion layers protect envelope contents,
so the TCP stream itself is not encrypted.

A link starts with HELLO (the sender's signed directory entry and a random
challenge) in both directions, then PROOF: an Ed25519 signature over the
peer's challenge and both Node IDs. Only then is the peer a neighbor.
Directory entries and signed neighbor lists (LINKS) are public mesh state,
flooded to every neighbor so each Node can choose source routes over
adjacency that both ends confirm. Relays wait a short random delay before
forwarding to blur timing; there is no cover traffic.
"""

import asyncio
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
import secrets
import time

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from faronet.node.envelope import RELAY_HOPS, Delivery, PrivateMessage, Route
from faronet.node.fragment import ENVELOPE_SIZE
from faronet.node.identity import (
    NODE_ID_SIZE, SIGNATURE_SIZE, Directory, DirectoryEntry, DirectoryError, Identity,
)
from faronet.node.mesh import Node

RECORD_BODY = ENVELOPE_SIZE
RECORD_SIZE = 1 + RECORD_BODY
CONTROL_LENGTH = 2
LINKS_PREFIX = b"FARONET-LINKS-V1"
PROOF_PREFIX = b"FARONET-LAN-PROOF-V1"
CHALLENGE_SIZE = 32
MAX_NEIGHBORS = 16
MAX_NODES = 256
ENTRY_LIFETIME = 24 * 3600
HANDSHAKE_SECONDS = 10
RECONNECT_SECONDS = 2
MAX_FORWARD_DELAY_MS = 200
MAX_BUFFERED = 64 * RECORD_SIZE
_LINKS_FIXED = len(LINKS_PREFIX) + NODE_ID_SIZE + 8 + 1


class LanError(ValueError):
    """Static messages only; never include addresses, IDs or message text."""


class RecordType(IntEnum):
    HELLO = 1
    PROOF = 2
    ENTRY = 3
    LINKS = 4
    ENVELOPE = 5


def encode_record(kind: RecordType, body: bytes) -> bytes:
    if kind == RecordType.ENVELOPE:
        if len(body) != RECORD_BODY:
            raise LanError("Envelope records carry exactly one envelope")
        return bytes([kind]) + body
    if len(body) > RECORD_BODY - CONTROL_LENGTH:
        raise LanError("Control record body is too long")
    return (bytes([kind]) + len(body).to_bytes(CONTROL_LENGTH, "big") + body).ljust(RECORD_SIZE, b"\0")


def decode_record(raw: bytes) -> tuple[RecordType, bytes]:
    if len(raw) != RECORD_SIZE:
        raise LanError("Record has the wrong size")
    try:
        kind = RecordType(raw[0])
    except ValueError:
        raise LanError("Unknown record type") from None
    if kind == RecordType.ENVELOPE:
        return kind, raw[1:]
    length = int.from_bytes(raw[1:1 + CONTROL_LENGTH], "big")
    end = 1 + CONTROL_LENGTH + length
    if length > RECORD_BODY - CONTROL_LENGTH or any(raw[end:]):
        raise LanError("Control record length or padding is invalid")
    return kind, raw[1 + CONTROL_LENGTH:end]


def _links_signed(node_id: bytes, issued_at: int, neighbors: tuple[bytes, ...]) -> bytes:
    if len(node_id) != NODE_ID_SIZE or not 0 <= issued_at < 1 << 64:
        raise LanError("Links record header is invalid")
    if (len(neighbors) > MAX_NEIGHBORS or len(set(neighbors)) != len(neighbors)
            or node_id in neighbors or any(len(n) != NODE_ID_SIZE for n in neighbors)):
        raise LanError("Links record neighbors are invalid")
    return (LINKS_PREFIX + node_id + issued_at.to_bytes(8, "big") + bytes([len(neighbors)])
            + b"".join(neighbors))


@dataclass(frozen=True)
class LinksRecord:
    """A Node's signed list of current neighbors; an edge counts only if both ends list it."""

    node_id: bytes
    issued_at: int
    neighbors: tuple[bytes, ...]
    signature: bytes

    @classmethod
    def sign(cls, identity: Identity, issued_at: int, neighbors) -> "LinksRecord":
        neighbors = tuple(sorted(neighbors))
        signed = _links_signed(identity.node_id, issued_at, neighbors)
        return cls(identity.node_id, issued_at, neighbors, identity.sign(signed))

    def encode(self) -> bytes:
        return _links_signed(self.node_id, self.issued_at, self.neighbors) + self.signature

    @classmethod
    def decode(cls, raw: bytes) -> "LinksRecord":
        if len(raw) < _LINKS_FIXED + SIGNATURE_SIZE or not raw.startswith(LINKS_PREFIX):
            raise LanError("Links record is malformed")
        offset = len(LINKS_PREFIX)
        node_id = raw[offset:offset + NODE_ID_SIZE]
        issued_at = int.from_bytes(raw[offset + NODE_ID_SIZE:_LINKS_FIXED - 1], "big")
        count = raw[_LINKS_FIXED - 1]
        end = _LINKS_FIXED + count * NODE_ID_SIZE
        if len(raw) != end + SIGNATURE_SIZE:
            raise LanError("Links record length does not match its count")
        neighbors = tuple(raw[i:i + NODE_ID_SIZE] for i in range(_LINKS_FIXED, end, NODE_ID_SIZE))
        record = cls(node_id, issued_at, neighbors, raw[end:])
        _links_signed(node_id, issued_at, neighbors)
        return record

    def verify(self, directory: Directory) -> None:
        entry = directory.get(self.node_id)
        try:
            VerifyKey(entry.verify_key).verify(self.encode()[:-SIGNATURE_SIZE], self.signature)
        except BadSignatureError:
            raise LanError("Links record signature is invalid") from None


def _proof_bytes(challenge: bytes, prover: bytes, verifier: bytes) -> bytes:
    return PROOF_PREFIX + challenge + prover + verifier


class _Link:
    """One verified TCP neighbor; satisfies the mesh Link protocol."""

    def __init__(self, lan: "LanNode", writer: asyncio.StreamWriter, dialer: bytes) -> None:
        self._lan = lan
        self.writer = writer
        self.dialer = dialer

    def write(self, kind: RecordType, body: bytes) -> None:
        transport = self.writer.transport
        if self.writer.is_closing() or transport.get_write_buffer_size() > MAX_BUFFERED:
            self._lan.counters["dropped"] += 1
            return
        self.writer.write(encode_record(kind, body))

    def carry(self, source: bytes, destination: bytes, envelope: bytes) -> bool:
        delay = secrets.randbelow(self._lan.forward_delay_ms + 1) / 1000
        asyncio.get_running_loop().call_later(delay, self.write, RecordType.ENVELOPE, envelope)
        return True

    def close(self) -> None:
        self.writer.close()


class LanNode:
    """A mesh Node on the LAN: accepts and dials TCP links, gossips and routes."""

    def __init__(self, identity: Identity, alias: str = "", *,
                 clock: Callable[[], int] = lambda: int(time.time()),
                 forward_delay_ms: int = MAX_FORWARD_DELAY_MS) -> None:
        self.identity = identity
        self.clock = clock
        self.forward_delay_ms = forward_delay_ms
        self.directory = Directory()
        self.node = Node(identity, self.directory, clock)
        self.counters: Counter[str] = self.node.counters
        now = clock()
        self.entry = identity.directory_entry(now, now + ENTRY_LIFETIME, alias)
        self.directory.add(self.entry, now)
        self.links: dict[bytes, LinksRecord] = {}
        self._neighbors: dict[bytes, _Link] = {}
        self._tasks: set[asyncio.Task] = set()
        self._server: asyncio.Server | None = None
        self.on_delivery: Callable[[Delivery], None] = lambda delivery: None
        self.on_change: Callable[[], None] = lambda: None
        self._publish_links()

    @property
    def node_id(self) -> bytes:
        return self.identity.node_id

    def neighbors(self) -> tuple[bytes, ...]:
        return tuple(self._neighbors)

    async def listen(self, host: str, port: int) -> int:
        """Accept links; returns the bound port (useful with port 0)."""
        self._server = await asyncio.start_server(
            lambda reader, writer: self._connection(reader, writer, outgoing=False), host, port,
        )
        return self._server.sockets[0].getsockname()[1]

    def dial(self, host: str, port: int, handshake_seconds: float = HANDSHAKE_SECONDS) -> None:
        """Keep one outgoing link to host:port, reconnecting while the node runs.

        An optical bridge needs a much longer handshake_seconds: at about 20
        payload bytes per second the handshake alone takes a minute or more.
        """
        task = asyncio.get_running_loop().create_task(self._dial(host, port, handshake_seconds))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for link in list(self._neighbors.values()):
            link.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def wipe(self) -> None:
        """Panic: close every link, then drop keys, directory, routes and messages."""
        await self.close()
        self.identity.wipe()
        self.directory.clear()
        self.links.clear()
        self.node.forget()
        self._neighbors.clear()

    async def _dial(self, host: str, port: int, handshake_seconds: float) -> None:
        peer = None
        while True:
            if peer is None or peer not in self._neighbors:
                try:
                    reader, writer = await asyncio.open_connection(host, port)
                except OSError:
                    self.counters["dial_failures"] += 1
                else:
                    peer = await self._connection(reader, writer, True, handshake_seconds) or peer
            await asyncio.sleep(RECONNECT_SECONDS)

    async def _connection(self, reader, writer, outgoing: bool,
                          handshake_seconds: float = HANDSHAKE_SECONDS) -> bytes | None:
        """Run one TCP link to completion; returns the peer's Node ID once it proved it."""
        peer = None
        try:
            entry = await asyncio.wait_for(self._handshake(reader, writer), handshake_seconds)
            peer = entry.node_id
            link = _Link(self, writer, self.node_id if outgoing else peer)
            if not self._admit(peer, link):
                return peer
            try:
                self._learn_entry(entry, source=peer)
                for known in self.directory.node_ids():
                    link.write(RecordType.ENTRY, self.directory.get(known).encode())
                for record in self.links.values():
                    link.write(RecordType.LINKS, record.encode())
                while True:
                    kind, body = decode_record(await reader.readexactly(RECORD_SIZE))
                    self._handle(peer, kind, body)
            finally:
                self._drop(peer, link)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError,
                LanError, DirectoryError):
            self.counters["link_errors"] += 1
        finally:
            writer.close()
        return peer

    async def _handshake(self, reader, writer) -> DirectoryEntry:
        challenge = secrets.token_bytes(CHALLENGE_SIZE)
        writer.write(encode_record(RecordType.HELLO, self.entry.encode() + challenge))
        kind, body = decode_record(await reader.readexactly(RECORD_SIZE))
        if kind != RecordType.HELLO or len(body) <= CHALLENGE_SIZE:
            raise LanError("Expected a HELLO record")
        entry = DirectoryEntry.decode(body[:-CHALLENGE_SIZE])
        entry.check_valid_at(self.clock())
        if entry.node_id == self.node_id:
            raise LanError("A node cannot link to itself")
        proof = self.identity.sign(_proof_bytes(body[-CHALLENGE_SIZE:], self.node_id, entry.node_id))
        writer.write(encode_record(RecordType.PROOF, proof))
        kind, body = decode_record(await reader.readexactly(RECORD_SIZE))
        if kind != RecordType.PROOF:
            raise LanError("Expected a PROOF record")
        try:
            VerifyKey(entry.verify_key).verify(_proof_bytes(challenge, entry.node_id, self.node_id), body)
        except BadSignatureError:
            raise LanError("Peer could not prove its identity") from None
        return entry

    def _admit(self, peer: bytes, link: _Link) -> bool:
        current = self._neighbors.get(peer)
        if current is None and len(self._neighbors) >= MAX_NEIGHBORS:
            return False
        if current is not None:
            # Both ends keep the link dialed by the smaller Node ID; a redial replaces a stale one.
            preferred = min(self.node_id, peer)
            if current.dialer == preferred and link.dialer != preferred:
                return False
            current.close()
        self._neighbors[peer] = link
        self.node.neighbors[peer] = link
        self._publish_links()
        return True

    def _drop(self, peer: bytes, link: _Link) -> None:
        if self._neighbors.get(peer) is link:
            del self._neighbors[peer]
            self.node.neighbors.pop(peer, None)
            self._publish_links()

    def _handle(self, peer: bytes, kind: RecordType, body: bytes) -> None:
        if kind == RecordType.ENVELOPE:
            self.node.receive(body)
            while self.node.inbox:
                self.on_delivery(self.node.inbox.pop(0))
            return
        if kind not in (RecordType.ENTRY, RecordType.LINKS):
            raise LanError("Handshake records are not valid on an open link")
        try:
            if kind == RecordType.ENTRY:
                self._learn_entry(DirectoryEntry.decode(body), source=peer)
            else:
                self._learn_links(LinksRecord.decode(body), source=peer)
        except (LanError, DirectoryError):
            self.counters["rejected_gossip"] += 1

    def _flood(self, kind: RecordType, body: bytes, source: bytes | None) -> None:
        for neighbor, link in self._neighbors.items():
            if neighbor != source:
                link.write(kind, body)

    def _learn_entry(self, entry: DirectoryEntry, source: bytes | None) -> None:
        if entry.node_id in self.directory:
            if self.directory.get(entry.node_id) == entry:
                return
        elif len(self.directory) >= MAX_NODES:
            raise LanError("Directory is full")
        self.directory.add(entry, self.clock())
        self._flood(RecordType.ENTRY, entry.encode(), source)
        self.on_change()

    def _learn_links(self, record: LinksRecord, source: bytes) -> None:
        current = self.links.get(record.node_id)
        if record.node_id == self.node_id or (current and record.issued_at <= current.issued_at):
            return
        record.verify(self.directory)
        self.links[record.node_id] = record
        self._flood(RecordType.LINKS, record.encode(), source)
        self.on_change()

    def _publish_links(self) -> None:
        current = self.links.get(self.node_id)
        issued = max(self.clock(), current.issued_at + 1 if current else 0)
        record = LinksRecord.sign(self.identity, issued, self._neighbors)
        self.links[self.node_id] = record
        self._flood(RecordType.LINKS, record.encode(), None)
        self.on_change()

    def _confirmed(self, a: bytes, b: bytes) -> bool:
        return all(x in self.links and y in self.links[x].neighbors for x, y in ((a, b), (b, a)))

    def _usable(self, node_id: bytes) -> bool:
        try:
            self.directory.get(node_id).check_valid_at(self.clock())
        except DirectoryError:
            return False
        return True

    def routes_to(self, destination: bytes) -> list[Route]:
        """Every path of three distinct relays over confirmed links, first hop a live neighbor."""
        if destination == self.node_id or not self._usable(destination):
            return []
        routes = []

        def extend(path: tuple[bytes, ...]) -> None:
            if len(path) == RELAY_HOPS:
                if self._confirmed(path[-1], destination):
                    routes.append(Route(path, destination))
                return
            for candidate in self.links[path[-1]].neighbors if path else self._neighbors:
                if (candidate not in path and candidate not in (self.node_id, destination)
                        and self._usable(candidate)
                        and self._confirmed(path[-1] if path else self.node_id, candidate)):
                    extend((*path, candidate))

        extend(())
        return routes

    def send_text(self, destination: bytes, text: str, ttl: int) -> Route:
        """Wrap text for destination over a randomly chosen route; raises if none exists."""
        message = PrivateMessage(text, self.clock() + ttl)
        routes = self.routes_to(destination)
        if not routes:
            raise LanError("Aún no hay una ruta con tres relevos distintos hacia ese nodo")
        route = secrets.choice(routes)
        self.node.send(route, message)
        return route
