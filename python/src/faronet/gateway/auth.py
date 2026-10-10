"""Offline gateway HMAC contract. HTTP routes and durable admission follow later."""

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import hmac
import re
import secrets
from typing import Protocol

PREFIX = "FARONET-GATEWAY-HMAC-V1"
MAX_BODY_BYTES = 65_536
CLOCK_TOLERANCE = 60
MAX_TIMESTAMP = (1 << 64) - 1
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}", re.ASCII)
_PATH = re.compile(r"/(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?", re.ASCII)


class AuthError(ValueError):
    """Static error text deliberately excludes request values and secrets."""


class ReplayStoreUnavailable(AuthError):
    """Admission must fail closed when replay state cannot be accessed."""


class ReplayError(AuthError):
    """A valid nonce has already been admitted in this scope."""


def _lower_hex(value: str, length: int) -> bool:
    return (
        isinstance(value, str) and len(value) == length
        and all(char in "0123456789abcdef" for char in value)
    )


def _secret(secret: bytes) -> None:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise AuthError("Gateway secret must contain at least 32 bytes")


def _unsigned_time(value: int) -> None:
    if type(value) is not int or not 0 <= value <= MAX_TIMESTAMP:
        raise AuthError("Clock must return unsigned 64-bit Unix seconds")


def check_freshness(timestamp: int, now: int) -> None:
    """Python integers widen naturally; neither subtraction nor expiry wraps."""
    _unsigned_time(timestamp)
    _unsigned_time(now)
    if abs(now - timestamp) > CLOCK_TOLERANCE:
        raise AuthError("Request is outside the accepted clock window")


def new_nonce() -> str:
    return secrets.token_hex(16)


@dataclass(frozen=True, repr=False)
class GatewayRequest:
    """Sign these body bytes and transmit these same bytes without reserialization."""

    audience: str
    key_id: str
    method: str
    path: str
    timestamp: str
    nonce: str
    body: bytes = field(repr=False)

    def validate(self) -> int:
        for identifier in (self.audience, self.key_id):
            if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
                raise AuthError("Invalid audience or gateway key identifier")
        if self.method not in ("GET", "POST"):
            raise AuthError("Only canonical GET or POST is supported")
        if not isinstance(self.path, str) or not _PATH.fullmatch(self.path):
            raise AuthError("Invalid canonical path")
        if (
            not isinstance(self.timestamp, str)
            or not re.fullmatch(r"0|[1-9][0-9]{0,19}", self.timestamp, re.ASCII)
        ):
            raise AuthError("Invalid canonical timestamp")
        timestamp = int(self.timestamp)
        _unsigned_time(timestamp)
        if not _lower_hex(self.nonce, 32):
            raise AuthError("Invalid nonce encoding")
        if not isinstance(self.body, bytes) or len(self.body) > MAX_BODY_BYTES:
            raise AuthError("Body must be bytes within the authentication cap")
        if self.method == "GET" and self.body:
            raise AuthError("GET body must be empty")
        return timestamp

    def canonical_bytes(self) -> bytes:
        self.validate()
        fields = (
            PREFIX, self.audience, self.key_id, self.method, self.path,
            self.timestamp, self.nonce, hashlib.sha256(self.body).hexdigest(),
        )
        return ("\n".join(fields) + "\n").encode("ascii")


def sign_request(request: GatewayRequest, secret: bytes) -> str:
    _secret(secret)
    return hmac.new(secret, request.canonical_bytes(), hashlib.sha256).hexdigest()


class NonceStore(Protocol):
    """A claim must atomically recheck time, reject duplicates and record expiry.

    This synchronous interface is for the offline contract. A future durable
    HTTP adapter must preserve the policy inside its storage transaction.
    """

    def claim(
        self, scope: tuple[str, str, str], timestamp: int, clock: Callable[[], int],
    ) -> bool: ...


def verify_and_admit(
    request: GatewayRequest,
    signature: str,
    secret: bytes,
    *,
    expected_audience: str,
    expected_key_id: str,
    clock: Callable[[], int],
    store: NonceStore,
) -> None:
    """Offline integrity/freshness plus explicit replay admission; no side effects."""
    timestamp = request.validate()
    if (request.audience, request.key_id) != (expected_audience, expected_key_id):
        raise AuthError("Unexpected audience or gateway key")
    if not _lower_hex(signature, 64):
        raise AuthError("Invalid signature encoding")
    expected = sign_request(request, secret)
    if not hmac.compare_digest(expected, signature):
        raise AuthError("Authentication failed")
    check_freshness(timestamp, clock())
    try:
        admitted = store.claim((request.audience, request.key_id, request.nonce), timestamp, clock)
    except AuthError:
        raise
    except Exception:
        # Storage adapters may expose different errors; none should admit traffic.
        raise ReplayStoreUnavailable("Replay store unavailable") from None
    if admitted is False:
        raise ReplayError("Nonce already admitted")
    if admitted is not True:
        raise ReplayStoreUnavailable("Invalid replay-store admission result")
