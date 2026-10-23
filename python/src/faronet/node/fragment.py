"""Carry one fixed-size mesh envelope across several 86-byte Faro payloads.

Proposal 0002: a Faro DATA frame carries at most 86 payload bytes. Each
fragment spends 4 bytes on its header, so 82 bytes remain, and an envelope
is exactly six fragments. The envelope size is therefore a consequence of
the accepted link budget, not an independent choice.

Fragment payload layout (86 bytes):

    0-1  tag    unsigned 16-bit, chosen per envelope by the sending neighbor
    2    index  0-5
    3    count  always 6 in this version
    4-85 data   82 envelope bytes

The link adapter already suppresses exact duplicate frames; this module still
ignores repeated fragments so a different link behaves the same way.
"""

from collections import OrderedDict

from faronet.dispositivo_luz_adaptador.frame import PAYLOAD_SIZE

FRAGMENT_HEADER_SIZE = 4
FRAGMENT_DATA_SIZE = PAYLOAD_SIZE - FRAGMENT_HEADER_SIZE
FRAGMENT_COUNT = 6
ENVELOPE_SIZE = FRAGMENT_COUNT * FRAGMENT_DATA_SIZE
MAX_TAG = (1 << 16) - 1
MAX_PENDING = 4


class FragmentError(ValueError):
    """Malformed fragment or an envelope of the wrong size."""


def fragment(envelope: bytes, tag: int) -> tuple[bytes, ...]:
    """Split a 492-byte envelope into six complete Faro payloads."""
    if not isinstance(envelope, bytes) or len(envelope) != ENVELOPE_SIZE:
        raise FragmentError("Envelope must be exactly 492 bytes")
    if type(tag) is not int or not 0 <= tag <= MAX_TAG:
        raise FragmentError("Tag must be an unsigned 16-bit integer")
    return tuple(
        tag.to_bytes(2, "big") + bytes([index, FRAGMENT_COUNT])
        + envelope[index * FRAGMENT_DATA_SIZE:(index + 1) * FRAGMENT_DATA_SIZE]
        for index in range(FRAGMENT_COUNT)
    )


class Reassembler:
    """Per-neighbor reassembly with a bounded number of in-progress envelopes.

    One Reassembler belongs to one incoming link; tags from different
    neighbors must never share an instance. Accepting a payload returns the
    complete envelope once, or None while fragments are still missing.
    """

    def __init__(self) -> None:
        self._pending: OrderedDict[int, dict[int, bytes]] = OrderedDict()
        self.completed = 0
        self.ignored_duplicates = 0
        self.evicted = 0

    def accept(self, payload: bytes) -> bytes | None:
        if not isinstance(payload, bytes) or len(payload) != PAYLOAD_SIZE:
            raise FragmentError("Fragment must fill the 86-byte Faro payload")
        tag = int.from_bytes(payload[:2], "big")
        index, count = payload[2], payload[3]
        if count != FRAGMENT_COUNT or index >= FRAGMENT_COUNT:
            raise FragmentError("Fragment index or count is outside this version")
        parts = self._pending.get(tag)
        if parts is None:
            if len(self._pending) >= MAX_PENDING:
                self._pending.popitem(last=False)
                self.evicted += 1
            parts = self._pending[tag] = {}
        if index in parts:
            self.ignored_duplicates += 1
            return None
        parts[index] = payload[FRAGMENT_HEADER_SIZE:]
        if len(parts) < FRAGMENT_COUNT:
            return None
        del self._pending[tag]
        self.completed += 1
        return b"".join(parts[i] for i in range(FRAGMENT_COUNT))

    @property
    def pending(self) -> int:
        return len(self._pending)
