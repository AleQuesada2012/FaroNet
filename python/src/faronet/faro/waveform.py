"""Bounded acquisition from timestamped edges with a configured half-bit clock.

The first rising edge after idle belongs to the accepted 0x55 preamble.
No free-running sample loop or packet-aligned GPIO start is assumed. This
bring-up decoder does not negotiate a clock or track clock-rate drift.
"""

from faronet.dispositivo_luz_adaptador import Frame, FrameError
from faronet.dispositivo_luz_adaptador.frame import PREAMBLE, SYNC
from faronet.dispositivo_luz_adaptador.manchester import decode, ManchesterError

FRAME_SYMBOLS = 2048
GUARD_SYMBOLS = 16


def raw_bits(levels) -> bytes:
    """Best-effort bytes from a damaged capture: each bit is the first level of its pair."""
    result = bytearray()
    for offset in range(0, len(levels) - 15, 16):
        byte = 0
        for index in range(offset, offset + 16, 2):
            byte = (byte << 1) | (levels[index] & 1)
        result.append(byte)
    return bytes(result)


class EdgeDecoder:
    """Recover one frame at a time; require at least eight OFF units to sync."""

    def __init__(self, half_ns: int, now_ns: int, initial: int = 0):
        if half_ns <= 0 or initial not in (0, 1):
            raise ValueError("Invalid clock or initial light level")
        self.half_ns = half_ns
        self.level = initial
        self.low_since = now_ns if initial == 0 else None
        self.start = None
        self.edges = []
        self.rejected = 0
        self._header_checked = False
        # Bytes read from the last complete capture that failed to decode, for raw BER.
        self.last_raw: bytes | None = None

    def lose_sync(self) -> None:
        self.start = None
        self.edges.clear()
        self._header_checked = False
        self.rejected += 1

    def _levels(self, count: int) -> list[int]:
        edge_index, level = 0, 0
        levels = []
        for index in range(count):
            sample = self.start + index * self.half_ns + self.half_ns // 2
            while edge_index < len(self.edges) and self.edges[edge_index][0] <= sample:
                level = self.edges[edge_index][1]
                edge_index += 1
            levels.append(level)
        return levels

    def advance(self, now_ns: int) -> Frame | None:
        if self.start is None:
            return None
        elapsed = now_ns - self.start
        # Discard noise early instead of waiting a whole frame on a false start.
        if elapsed >= 96 * self.half_ns and not self._header_checked:
            try:
                if decode(self._levels(96)) != PREAMBLE + SYNC:
                    raise FrameError("Preamble/sync mismatch")
            except (FrameError, ManchesterError):
                self.lose_sync()
                return None
            self._header_checked = True
        if elapsed < FRAME_SYMBOLS * self.half_ns:
            return None
        levels = self._levels(FRAME_SYMBOLS)
        try:
            result = Frame.decode(decode(levels))
        except (FrameError, ManchesterError):
            self.rejected += 1
            self.last_raw = raw_bits(levels)
            result = None
        self.start = None
        self.edges.clear()
        return result

    def feed(self, timestamp_ns: int, level: int) -> Frame | None:
        completed = self.advance(timestamp_ns)
        if level == 1 and self.level == 0 and self.low_since is not None:
            if self.start is None and timestamp_ns - self.low_since >= 8 * self.half_ns:
                self.start = timestamp_ns - self.half_ns
                self.edges = []
                self._header_checked = False
        if self.start is not None:
            self.edges.append((timestamp_ns, level))
            # Bound memory; leave room for comparator glitches at transitions.
            if len(self.edges) > 4 * FRAME_SYMBOLS:
                self.lose_sync()
        if level == 0:
            self.low_since = timestamp_ns
        self.level = level
        return completed
