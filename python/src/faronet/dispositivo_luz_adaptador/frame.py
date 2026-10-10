"""The accepted 128-byte Faro frame; CRC detects errors, not forgery."""

from dataclasses import dataclass
from enum import IntEnum
import struct
import zlib

FRAME_SIZE = 128
PAYLOAD_SIZE = 86
PREAMBLE = bytes.fromhex("55555555")
SYNC = bytes.fromhex("d391")
VERSION = 1
MAX_SEQUENCE = (1 << 32) - 1
_HEADER = struct.Struct(">BB8s8s8sIH")


class FrameError(ValueError):
    """A frame is malformed or outside the accepted contract."""


class FrameType(IntEnum):
    DATA = 1
    ACK = 2


@dataclass(frozen=True)
class Frame:
    """A neighbor-link frame, independent of GPIO and mesh message contents."""

    kind: FrameType
    source: bytes
    destination: bytes
    session: bytes
    sequence: int
    payload: bytes = b""

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FrameType):
            raise FrameError("Unknown frame type")
        for value in (self.source, self.destination, self.session):
            if not isinstance(value, bytes) or len(value) != 8:
                raise FrameError("Link IDs must be exactly eight bytes")
        if type(self.sequence) is not int or not 0 <= self.sequence <= MAX_SEQUENCE:
            raise FrameError("Sequence must be an unsigned 32-bit integer")
        if not isinstance(self.payload, bytes) or len(self.payload) > PAYLOAD_SIZE:
            raise FrameError("Payload must be bytes, at most 86 bytes")
        if self.kind == FrameType.ACK and self.payload:
            raise FrameError("ACK payload must be empty")

    def encode(self) -> bytes:
        """Serialize all headers, zero padding and CRC into exactly 128 bytes."""
        header = _HEADER.pack(
            VERSION, self.kind, self.source, self.destination,
            self.session, self.sequence, len(self.payload),
        )
        protected = header + self.payload.ljust(PAYLOAD_SIZE, b"\0")
        crc = zlib.crc32(protected).to_bytes(4, "big")
        return PREAMBLE + SYNC + protected + crc

    @classmethod
    def decode(cls, raw: bytes) -> "Frame":
        """Validate an externally constructed frame without truncation."""
        if not isinstance(raw, bytes) or len(raw) != FRAME_SIZE:
            raise FrameError("Serialized frame must be exactly 128 bytes")
        if raw[:6] != PREAMBLE + SYNC:
            raise FrameError("Invalid preamble or sync")
        if zlib.crc32(raw[6:124]) != int.from_bytes(raw[124:], "big"):
            raise FrameError("CRC mismatch")
        version, kind, source, destination, session, sequence, length = (
            _HEADER.unpack(raw[6:38])
        )
        if version != VERSION:
            raise FrameError("Unsupported frame version")
        try:
            frame_type = FrameType(kind)
        except ValueError:
            raise FrameError("Unknown frame type") from None
        if length > PAYLOAD_SIZE:
            raise FrameError("Payload length exceeds the frame budget")
        if any(raw[38 + length:124]):
            raise FrameError("Padding must be zero")
        return cls(frame_type, source, destination, session, sequence, raw[38:38 + length])

    def acknowledgment(self) -> "Frame":
        """Acknowledge DATA at the neighbor link, not end-to-end delivery."""
        if self.kind != FrameType.DATA:
            raise FrameError("Only DATA can be acknowledged")
        return Frame(
            FrameType.ACK, self.destination, self.source, self.session, self.sequence,
        )

    def is_ack_for(self, data: "Frame") -> bool:
        return (
            self.kind == FrameType.ACK
            and data.kind == FrameType.DATA
            and self.source == data.destination
            and self.destination == data.source
            and self.session == data.session
            and self.sequence == data.sequence
        )
