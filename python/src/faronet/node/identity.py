"""Node identities and the signed directory entry contract (proposal 0002).

Long-term keys use PyNaCl: Ed25519 for directory signatures and X25519 for
onion/end-to-end encryption. Nothing here logs, prints or persists keys.
Python cannot promise that every RAM copy of a key is overwritten; the
achievable panic cleanup boundary is a separate decision.
"""

from dataclasses import dataclass
import hashlib
import re

from nacl.exceptions import BadSignatureError
from nacl.public import PrivateKey, PublicKey
from nacl.signing import SigningKey, VerifyKey

DIRECTORY_PREFIX = b"FARONET-DIRECTORY-V1"
NODE_ID_SIZE = 16
KEY_SIZE = 32
SIGNATURE_SIZE = 64
MAX_ALIAS_BYTES = 16
MAX_LIFETIME = 30 * 24 * 3600
MAX_TIMESTAMP = (1 << 64) - 1
_ALIAS = re.compile(r"[A-Za-z0-9_-]{0,16}", re.ASCII)
_FIXED_SIGNED = len(DIRECTORY_PREFIX) + NODE_ID_SIZE + 2 * KEY_SIZE + 16 + 1


class DirectoryError(ValueError):
    """Static messages only; never include keys, IDs or aliases."""


def node_id_for(verify_key: bytes) -> bytes:
    """The mesh identifier is derived from the signing key, never chosen."""
    if not isinstance(verify_key, bytes) or len(verify_key) != KEY_SIZE:
        raise DirectoryError("Verify key must be 32 bytes")
    return hashlib.sha256(verify_key).digest()[:NODE_ID_SIZE]


def _time(value: int) -> None:
    if type(value) is not int or not 0 <= value <= MAX_TIMESTAMP:
        raise DirectoryError("Times must be unsigned 64-bit Unix seconds")


def _signed_bytes(
    node_id: bytes, verify_key: bytes, public_key: bytes,
    issued_at: int, expires_at: int, alias: str,
) -> bytes:
    """Canonical binary record covered by the Ed25519 signature."""
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise DirectoryError("Alias must be 0-16 ASCII letters, digits, hyphen or underscore")
    _time(issued_at)
    _time(expires_at)
    encoded_alias = alias.encode("ascii")
    return (
        DIRECTORY_PREFIX + node_id + verify_key + public_key
        + issued_at.to_bytes(8, "big") + expires_at.to_bytes(8, "big")
        + bytes([len(encoded_alias)]) + encoded_alias
    )


@dataclass(frozen=True)
class DirectoryEntry:
    """A self-signed public record: who holds which keys, and for how long.

    The signature proves the holder of the signing key published these keys.
    It does not prove the alias belongs to any real person; trust bootstrap
    (how a node first learns which entry to believe) is a later decision.
    """

    node_id: bytes
    verify_key: bytes
    public_key: bytes
    issued_at: int
    expires_at: int
    alias: str
    signature: bytes

    def __post_init__(self) -> None:
        if node_id_for(self.verify_key) != self.node_id:
            raise DirectoryError("Node ID does not match the verify key")
        if not isinstance(self.public_key, bytes) or len(self.public_key) != KEY_SIZE:
            raise DirectoryError("Public key must be 32 bytes")
        _time(self.issued_at)
        _time(self.expires_at)
        if not self.issued_at < self.expires_at <= self.issued_at + MAX_LIFETIME:
            raise DirectoryError("Entry lifetime must be positive and at most 30 days")
        if not isinstance(self.alias, str) or not _ALIAS.fullmatch(self.alias):
            raise DirectoryError("Alias must be 0-16 ASCII letters, digits, hyphen or underscore")
        if not isinstance(self.signature, bytes) or len(self.signature) != SIGNATURE_SIZE:
            raise DirectoryError("Signature must be 64 bytes")
        try:
            VerifyKey(self.verify_key).verify(self.signed_bytes(), self.signature)
        except BadSignatureError:
            raise DirectoryError("Directory signature is invalid") from None

    def signed_bytes(self) -> bytes:
        return _signed_bytes(
            self.node_id, self.verify_key, self.public_key,
            self.issued_at, self.expires_at, self.alias,
        )

    def encode(self) -> bytes:
        return self.signed_bytes() + self.signature

    @classmethod
    def decode(cls, raw: bytes) -> "DirectoryEntry":
        if not isinstance(raw, bytes) or not _FIXED_SIGNED + SIGNATURE_SIZE <= len(raw):
            raise DirectoryError("Directory entry is too short")
        if raw[:len(DIRECTORY_PREFIX)] != DIRECTORY_PREFIX:
            raise DirectoryError("Unknown directory entry prefix")
        offset = len(DIRECTORY_PREFIX)
        node_id = raw[offset:offset + NODE_ID_SIZE]
        offset += NODE_ID_SIZE
        verify_key = raw[offset:offset + KEY_SIZE]
        offset += KEY_SIZE
        public_key = raw[offset:offset + KEY_SIZE]
        offset += KEY_SIZE
        issued_at = int.from_bytes(raw[offset:offset + 8], "big")
        expires_at = int.from_bytes(raw[offset + 8:offset + 16], "big")
        offset += 16
        alias_length = raw[offset]
        offset += 1
        if alias_length > MAX_ALIAS_BYTES or len(raw) != offset + alias_length + SIGNATURE_SIZE:
            raise DirectoryError("Directory entry length does not match its alias")
        try:
            alias = raw[offset:offset + alias_length].decode("ascii")
        except UnicodeDecodeError:
            raise DirectoryError("Alias must be ASCII") from None
        return cls(
            node_id, verify_key, public_key, issued_at, expires_at, alias,
            raw[offset + alias_length:],
        )

    def check_valid_at(self, now: int) -> None:
        """Clock policy: tolerate 60 s of issuer clock skew, never expiry."""
        _time(now)
        if now + 60 < self.issued_at:
            raise DirectoryError("Directory entry is not valid yet")
        if now > self.expires_at:
            raise DirectoryError("Directory entry has expired")

    def encryption_key(self) -> PublicKey:
        return PublicKey(self.public_key)


class Identity:
    """One node's long-term private keys. Never serialize or print this."""

    def __init__(self, signing_key: SigningKey, box_key: PrivateKey) -> None:
        self._signing_key = signing_key
        self._box_key = box_key
        self.node_id = node_id_for(bytes(signing_key.verify_key))

    def __repr__(self) -> str:
        return "Identity(<keys withheld>)"

    @classmethod
    def generate(cls) -> "Identity":
        return cls(SigningKey.generate(), PrivateKey.generate())

    @classmethod
    def from_seeds(cls, signing_seed: bytes, box_seed: bytes) -> "Identity":
        """Deterministic identities for fixtures and tests only."""
        return cls(SigningKey(signing_seed), PrivateKey(box_seed))

    @property
    def box_key(self) -> PrivateKey:
        return self._box_key

    @property
    def public_key(self) -> PublicKey:
        return self._box_key.public_key

    def directory_entry(self, issued_at: int, expires_at: int, alias: str = "") -> DirectoryEntry:
        verify_key = bytes(self._signing_key.verify_key)
        public_key = bytes(self.public_key)
        signed = _signed_bytes(self.node_id, verify_key, public_key, issued_at, expires_at, alias)
        signature = self._signing_key.sign(signed).signature
        return DirectoryEntry(
            self.node_id, verify_key, public_key, issued_at, expires_at, alias, signature,
        )


class Directory:
    """A node's local, verified copy of directory entries, keyed by node ID.

    Replication through the gateway and the Rust public directory come later;
    this class only enforces signature, freshness and newest-entry rules.
    """

    def __init__(self) -> None:
        self._entries: dict[bytes, DirectoryEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, node_id: bytes) -> bool:
        return node_id in self._entries

    def add(self, entry: DirectoryEntry, now: int) -> None:
        entry.check_valid_at(now)
        current = self._entries.get(entry.node_id)
        if current is not None and entry.issued_at < current.issued_at:
            raise DirectoryError("An older directory entry cannot replace a newer one")
        self._entries[entry.node_id] = entry

    def get(self, node_id: bytes) -> DirectoryEntry:
        try:
            return self._entries[node_id]
        except KeyError:
            raise DirectoryError("Unknown node") from None

    def node_ids(self) -> tuple[bytes, ...]:
        return tuple(self._entries)
