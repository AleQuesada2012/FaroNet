"""Carry one LAN mesh link across a two-Faro optical link (RFC FN-1 5.9).

The bridge runs on each Faro's Pi as its own process (`optical-bridge`), so
the transmit loop's timing never waits on a Node's event loop. Its local
side is one TCP connection from the Node, carrying the usual 493-byte LAN
records; its optical side is a CsmaLink. The Node treats the bridge like
any LAN neighbor, so the HELLO/PROOF handshake, gossip and routing run
unchanged across the light.

On the light every 86-byte payload is an envelope fragment (Section 5.3),
so envelopes cross as six full frames. Control records (the handshake,
public directory entries and signed neighbor lists) drop their zero
padding, because at about 20 payload bytes per second padding would cost
minutes, and form one byte stream cut into payloads of at most 85 bytes;
the payload length tells the two apart.

CsmaLink delivers in order and exactly once until three attempts fail.
Then the stream is broken, so the bridge moves to the next epoch: a fresh
CsmaLink whose session is derived from the agreed base session, an empty
DATA frame that tells the peer at once, and a closed Node connection (the
Node redials and the handshake starts again). The same happens when the
Node disconnects. A bridge that sees DATA from its peer in a later epoch
adopts it, drops what it held for the old stream and closes its Node
connection too.
"""

import hashlib
import secrets
import time

from faronet.dispositivo_luz_adaptador.frame import PAYLOAD_SIZE, FrameType
from faronet.dispositivo_luz_adaptador.medium import CsmaLink, Delivered, SendResult, Transmit
from faronet.node.fragment import FragmentError, Reassembler, fragment
from faronet.node.lan import (
    CONTROL_LENGTH, RECORD_BODY, RECORD_SIZE, LanError, RecordType, decode_record, encode_record,
)

EPOCH_PREFIX = b"FARONET-OPTICAL-EPOCH-V1"
EPOCH_WINDOW = 256  # How many later epochs a peer may be ahead and still be recognized.
MAX_PENDING = 64 * RECORD_SIZE
CONTROL_CHUNK = PAYLOAD_SIZE - 1  # Shorter than a fragment, which always fills the payload.
CONTROL_TYPES = frozenset(kind for kind in RecordType if kind != RecordType.ENVELOPE)


def epoch_session(base: bytes, epoch: int) -> bytes:
    """The 8-byte link session for one epoch; both Faros derive it from the same base."""
    return hashlib.sha256(EPOCH_PREFIX + base + epoch.to_bytes(4, "big")).digest()[:8]


def encode_wire(record: bytes) -> bytes:
    """A 493-byte LAN control record as it travels on the light: without its padding."""
    kind, body = decode_record(record)
    if kind == RecordType.ENVELOPE:
        raise LanError("Envelopes cross the light as fragments")
    return record[:1 + CONTROL_LENGTH + len(body)]


class WireDecoder:
    """Rebuild 493-byte LAN control records from the control chunks of one epoch, in order."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buffer += data
        records = []
        while self._buffer:
            if self._buffer[0] not in CONTROL_TYPES:
                raise LanError("Unknown control record type on the optical stream")
            kind = RecordType(self._buffer[0])
            if len(self._buffer) < 1 + CONTROL_LENGTH:
                break
            length = int.from_bytes(self._buffer[1:1 + CONTROL_LENGTH], "big")
            if length > RECORD_BODY - CONTROL_LENGTH:
                raise LanError("Control record length is invalid on the optical stream")
            start, end = 1 + CONTROL_LENGTH, 1 + CONTROL_LENGTH + length
            if len(self._buffer) < end:
                break
            records.append(encode_record(kind, bytes(self._buffer[start:end])))
            del self._buffer[:end]
        return records


class _Bridge:
    def __init__(self, io, local: bytes, peer: bytes, base: bytes, emit, rng) -> None:
        self.io, self.local, self.peer, self.base = io, local, peer, base
        self.emit, self.rng = emit, rng
        self.client = None
        self.stats = {"frames_sent": 0, "payloads_received": 0, "records_to_light": 0,
                      "records_from_light": 0, "resets": 0}
        self._start(0, "start")

    def _start(self, epoch: int, reason: str) -> None:
        self.epoch = epoch
        self.link = CsmaLink(self.local, self.peer, epoch_session(self.base, epoch),
                             self.io.half_ns / 1e9, self.rng)
        self.later = {epoch_session(self.base, e): e
                      for e in range(epoch + 1, epoch + 1 + EPOCH_WINDOW)}
        self.decoder = WireDecoder()
        self.reassembler = Reassembler()
        self.tag = secrets.randbelow(1 << 16)
        self.from_client = bytearray()
        self.to_client = bytearray()
        self.emit({"epoch": epoch, "reason": reason})

    def reset(self, reason: str) -> None:
        """Our stream broke: next epoch, tell the peer, make the Node redial."""
        self.stats["resets"] += 1
        self.drop_client()
        self._start(self.epoch + 1, reason)
        self.link.offer(b"")

    def drop_client(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def accept(self, listener) -> None:
        try:
            connection, _ = listener.accept()
        except BlockingIOError:
            return
        if self.client is not None:  # The Node redialed, so the old stream is dead.
            self.reset("redial")
        connection.setblocking(False)
        self.client = connection
        self.emit({"client": "connected", "epoch": self.epoch})

    def read_client(self) -> None:
        if self.client is None:
            return
        try:
            data = self.client.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self.reset("node-closed")
            return
        self.from_client += data
        while len(self.from_client) >= RECORD_SIZE:
            record = bytes(self.from_client[:RECORD_SIZE])
            del self.from_client[:RECORD_SIZE]
            try:
                kind, body = decode_record(record)
            except LanError:
                self.reset("node-record")
                return
            self.stats["records_to_light"] += 1
            if kind == RecordType.ENVELOPE:
                self.tag = (self.tag + 1) & 0xFFFF
                payloads = fragment(body, self.tag)
            else:
                wire = encode_wire(record)
                payloads = [wire[i:i + CONTROL_CHUNK] for i in range(0, len(wire), CONTROL_CHUNK)]
            for payload in payloads:
                self.link.offer(payload)

    def write_client(self) -> None:
        if self.client is None or not self.to_client:
            return
        try:
            sent = self.client.send(self.to_client)
        except BlockingIOError:
            return
        except OSError:
            self.reset("node-closed")
            return
        del self.to_client[:sent]

    def on_frame(self, frame, now: float) -> None:
        if (frame.kind == FrameType.DATA and frame.source == self.peer
                and frame.destination == self.local and frame.session in self.later):
            self.drop_client()
            self._start(self.later[frame.session], "peer")
        self.act(self.link.on_frame(frame, now))

    def act(self, actions) -> None:
        for action in actions:
            if isinstance(action, Transmit):
                self.io.guard()
                self.io.transmit(action.frame)
                self.stats["frames_sent"] += 1
            elif isinstance(action, Delivered):
                self.stats["payloads_received"] += 1
                try:
                    if len(action.payload) == PAYLOAD_SIZE:
                        envelope = self.reassembler.accept(action.payload)
                        records = [encode_record(RecordType.ENVELOPE, envelope)] if envelope else []
                    else:
                        records = self.decoder.feed(action.payload)
                except (FragmentError, LanError):
                    self.reset("stream")
                    return
                self.stats["records_from_light"] += len(records)
                for record in records:
                    self.to_client += record
                if len(self.to_client) > MAX_PENDING:
                    self.reset("overflow")
                    return
            elif isinstance(action, SendResult) and not action.acknowledged:
                self.reset("send-failed")
                return


def serve_bridge(io, local: bytes, peer: bytes, base_session: bytes, listener, emit, stop,
                 clock=time.monotonic, rng=None) -> dict:
    """Bridge one Node connection on `listener` to the peer Faro until `stop` is set.

    `io` is a GpioFrameIO (or a fake with the same receive/transmit/guard/channel
    methods and `half_ns`). PanicStop from it propagates to the caller.
    """
    listener.setblocking(False)
    bridge = _Bridge(io, local, peer, base_session, emit, rng)
    try:
        while not stop.is_set():
            bridge.accept(listener)
            bridge.read_client()
            now = clock()
            # Collect decoded frames first so an owed ACK is decided before we transmit.
            frame = io.receive(min(max(bridge.link.wake_at - now, 0.0005), 0.05))
            if frame is not None:
                bridge.on_frame(frame, clock())
            bridge.act(bridge.link.poll(clock(), *io.channel()))
            bridge.write_client()
    finally:
        bridge.drop_client()
        emit(bridge.stats | {"epoch": bridge.epoch})
    return bridge.stats
