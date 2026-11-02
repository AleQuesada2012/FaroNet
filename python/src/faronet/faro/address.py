"""This Faro's 8-byte link address: random, kept on disk, rotated (RFC FN-1, 4.4).

The address is the optical analogue of a MAC address. It is generated with
`secrets`, written atomically with owner-only permissions, and replaced at
least every 24 hours and whenever the panic button is pressed, so a watcher
of the light cannot follow one device for long. Bench commands run with sudo,
so by default the file lives in root's home; set FARONET_STATE_DIR to share
one store between users.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import time

ADDRESS_SIZE = 8
ROTATE_SECONDS = 24 * 3600


class LinkIdError(argparse.ArgumentTypeError, ValueError):
    """argparse shows this text as is; plain ValueError text would be replaced in English."""


def link_id(value: str) -> bytes:
    """A link address or session as given on the command line: 16 lowercase hex characters."""
    if len(value) != 2 * ADDRESS_SIZE or any(c not in "0123456789abcdef" for c in value):
        raise LinkIdError("Las direcciones y sesiones ópticas son 16 caracteres hex en minúscula")
    return bytes.fromhex(value)


def state_dir() -> Path:
    return Path(os.environ.get("FARONET_STATE_DIR") or Path.home() / ".faronet")


class AddressStore:
    def __init__(self, path: Path | None = None, clock=time.time):
        self.path = Path(path) if path else state_dir() / "link-address.json"
        self.clock = clock

    def _load(self) -> tuple[bytes, float] | None:
        try:
            data = json.loads(self.path.read_text())
            address = bytes.fromhex(data["address"])
            created = float(data["created_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if len(address) != ADDRESS_SIZE or created > self.clock() + 60:
            return None
        return address, created

    def current(self) -> bytes:
        """The stored address, replaced first when missing, invalid or 24 hours old."""
        loaded = self._load()
        if loaded is None or self.clock() - loaded[1] >= ROTATE_SECONDS:
            return self.rotate()
        return loaded[0]

    def age_seconds(self) -> float | None:
        loaded = self._load()
        return None if loaded is None else self.clock() - loaded[1]

    def rotate(self) -> bytes:
        """Write a fresh random address; the old one is overwritten, never kept."""
        address = secrets.token_bytes(ADDRESS_SIZE)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump({"address": address.hex(), "created_at": self.clock()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        return address
