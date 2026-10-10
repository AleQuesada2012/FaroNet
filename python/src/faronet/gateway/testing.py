"""Fake replay storage for local tests only; no persistence or global guarantee."""

from collections.abc import Callable
from threading import Lock

from faronet.gateway.auth import CLOCK_TOLERANCE, ReplayStoreUnavailable, check_freshness


class FakeNonceStore:
    """One-process fake, deliberately separate from any future production adapter."""

    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self._entries: dict[tuple[str, str, str], int] = {}
        self._lock = Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def claim(
        self, scope: tuple[str, str, str], timestamp: int, clock: Callable[[], int],
    ) -> bool:
        with self._lock:
            if not self.available:
                raise ReplayStoreUnavailable("Fake replay store unavailable")
            now = clock()
            check_freshness(timestamp, now)
            self._entries = {key: expiry for key, expiry in self._entries.items() if now <= expiry}
            if scope in self._entries:
                return False
            self._entries[scope] = timestamp + CLOCK_TOLERANCE
            return True
