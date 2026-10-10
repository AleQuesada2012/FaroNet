"""Logical light waveforms: MSB first, 0=OFF/ON, 1=ON/OFF.

Each level occupies one virtual half-bit unit. The decoder knows the clock
and frame alignment; this is not a GPIO capture or clock-recovery backend.
"""

from collections.abc import Sequence


class ManchesterError(ValueError):
    """The waveform contains invalid levels, pairs or incomplete bytes."""


def encode(data: bytes) -> tuple[int, ...]:
    """Convert serialized bytes into unit-duration logical light levels."""
    levels = []
    for byte in data:
        for shift in range(7, -1, -1):
            bit = (byte >> shift) & 1
            levels.extend((bit, 1 - bit))
    return tuple(levels)


def decode(levels: Sequence[int]) -> bytes:
    """Read a byte-aligned waveform with the agreed half-bit clock."""
    if len(levels) % 16:
        raise ManchesterError("Waveform must contain complete encoded bytes")
    result = bytearray()
    for offset in range(0, len(levels), 16):
        byte = 0
        for index in range(offset, offset + 16, 2):
            first, second = levels[index], levels[index + 1]
            if type(first) is not int or type(second) is not int:
                raise ManchesterError("Light levels must be binary integers")
            if (first, second) not in ((0, 1), (1, 0)):
                raise ManchesterError("Invalid Manchester pair")
            byte = (byte << 1) | first
        result.append(byte)
    return bytes(result)
