"""Fixed-size onion envelopes and padded private messages (proposal 0002).

Every envelope on every link is exactly ENVELOPE_SIZE bytes. A sender wraps
its message for the destination, then for three relays, innermost first:

    envelope = len(c1) || c1 || random padding
    c1 = Seal_relay1( RELAY || id_relay2 || c2 )
    c2 = Seal_relay2( RELAY || id_relay3 || c3 )
    c3 = Seal_relay3( RELAY || id_destination || c4 )
    c4 = Seal_destination( DELIVER || id_sender || nonce || Box_sender->dest(message) )

Seal is PyNaCl SealedBox (anonymous X25519 + XSalsa20-Poly1305); Box is the
authenticated sender-to-destination box. A relay learns only the previous
hop, the next hop and, through the shrinking length, its position in the
fixed three-relay path. No single relay sees both endpoints. The message
plaintext has a fixed size, so lengths never reveal how much was said.
"""

from dataclasses import dataclass
from enum import IntEnum
import secrets

from nacl.exceptions import CryptoError
from nacl.public import Box, SealedBox
import nacl.bindings

from faronet.node.fragment import ENVELOPE_SIZE
from faronet.node.identity import NODE_ID_SIZE, Directory, Identity

RELAY_HOPS = 3
LENGTH_PREFIX = 2
SEAL_OVERHEAD = nacl.bindings.crypto_box_SEALBYTES
NONCE_SIZE = Box.NONCE_SIZE
BOX_OVERHEAD = NONCE_SIZE + nacl.bindings.crypto_secretbox_MACBYTES
LAYER_HEADER = 1 + NODE_ID_SIZE
RELAY_LAYER = SEAL_OVERHEAD + LAYER_HEADER
DELIVER_LAYER = SEAL_OVERHEAD + LAYER_HEADER + BOX_OVERHEAD
MESSAGE_SIZE = ENVELOPE_SIZE - LENGTH_PREFIX - RELAY_HOPS * RELAY_LAYER - DELIVER_LAYER
MESSAGE_VERSION = 1
MESSAGE_HEADER = 1 + 1 + 8 + 2
MAX_TEXT_BYTES = MESSAGE_SIZE - MESSAGE_HEADER
MAX_TIMESTAMP = (1 << 64) - 1


class EnvelopeError(ValueError):
    """Static messages only: never include IDs, text or key material."""


class LayerKind(IntEnum):
    RELAY = 1
    DELIVER = 2


class MessageKind(IntEnum):
    TEXT = 1


@dataclass(frozen=True)
class PrivateMessage:
    """The only thing the destination ever decrypts: UTF-8 text plus expiry."""

    text: str
    expires_at: int

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise EnvelopeError("Message text must be a string")
        if len(self.text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise EnvelopeError("Message text exceeds the fixed message size")
        if type(self.expires_at) is not int or not 0 <= self.expires_at <= MAX_TIMESTAMP:
            raise EnvelopeError("Expiry must be unsigned 64-bit Unix seconds")

    def encode(self) -> bytes:
        text = self.text.encode("utf-8")
        body = (
            bytes([MESSAGE_VERSION, MessageKind.TEXT]) + self.expires_at.to_bytes(8, "big")
            + len(text).to_bytes(2, "big") + text
        )
        return body.ljust(MESSAGE_SIZE, b"\0")

    @classmethod
    def decode(cls, raw: bytes) -> "PrivateMessage":
        if not isinstance(raw, bytes) or len(raw) != MESSAGE_SIZE:
            raise EnvelopeError("Padded message must have the fixed message size")
        if raw[0] != MESSAGE_VERSION or raw[1] != MessageKind.TEXT:
            raise EnvelopeError("Unsupported message version or kind")
        expires_at = int.from_bytes(raw[2:10], "big")
        length = int.from_bytes(raw[10:12], "big")
        if length > MAX_TEXT_BYTES or any(raw[MESSAGE_HEADER + length:]):
            raise EnvelopeError("Message length or padding is invalid")
        try:
            text = raw[MESSAGE_HEADER:MESSAGE_HEADER + length].decode("utf-8")
        except UnicodeDecodeError:
            raise EnvelopeError("Message text is not valid UTF-8") from None
        return cls(text, expires_at)


@dataclass(frozen=True)
class Route:
    """Three distinct relays, then the destination; the sender is excluded."""

    relays: tuple[bytes, ...]
    destination: bytes

    def __post_init__(self) -> None:
        hops = (*self.relays, self.destination)
        if len(self.relays) != RELAY_HOPS or len(set(hops)) != len(hops):
            raise EnvelopeError("A route needs exactly three distinct relays and a destination")
        for node_id in hops:
            if not isinstance(node_id, bytes) or len(node_id) != NODE_ID_SIZE:
                raise EnvelopeError("Route hops must be 16-byte node IDs")


@dataclass(frozen=True)
class Relay:
    next_hop: bytes
    envelope: bytes


@dataclass(frozen=True)
class Delivery:
    sender_id: bytes
    nonce: bytes
    message: PrivateMessage


def _pad(ciphertext: bytes) -> bytes:
    if len(ciphertext) + LENGTH_PREFIX > ENVELOPE_SIZE:
        raise EnvelopeError("Layer does not fit the fixed envelope")
    padding = secrets.token_bytes(ENVELOPE_SIZE - LENGTH_PREFIX - len(ciphertext))
    return len(ciphertext).to_bytes(2, "big") + ciphertext + padding


def build_envelope(
    sender: Identity, directory: Directory, route: Route, message: PrivateMessage,
) -> bytes:
    """Wrap a message for the destination and the relays, innermost first."""
    if sender.node_id in (*route.relays, route.destination):
        raise EnvelopeError("A sender cannot appear in its own route")
    destination = directory.get(route.destination)
    nonce = secrets.token_bytes(NONCE_SIZE)
    sealed = Box(sender.box_key, destination.encryption_key()).encrypt(message.encode(), nonce)
    inner = bytes([LayerKind.DELIVER]) + sender.node_id + nonce + sealed.ciphertext
    layer = SealedBox(destination.encryption_key()).encrypt(inner)
    next_hop = route.destination
    for relay_id in reversed(route.relays):
        relay = directory.get(relay_id)
        layer = SealedBox(relay.encryption_key()).encrypt(bytes([LayerKind.RELAY]) + next_hop + layer)
        next_hop = relay_id
    envelope = _pad(layer)
    assert len(envelope) == ENVELOPE_SIZE
    return envelope


def peel(identity: Identity, directory: Directory, envelope: bytes) -> Relay | Delivery:
    """Remove this node's layer: forward instructions or a decrypted message."""
    if not isinstance(envelope, bytes) or len(envelope) != ENVELOPE_SIZE:
        raise EnvelopeError("Envelope must have the fixed envelope size")
    length = int.from_bytes(envelope[:LENGTH_PREFIX], "big")
    if not SEAL_OVERHEAD + LAYER_HEADER <= length <= ENVELOPE_SIZE - LENGTH_PREFIX:
        raise EnvelopeError("Envelope layer length is invalid")
    try:
        plain = SealedBox(identity.box_key).decrypt(envelope[LENGTH_PREFIX:LENGTH_PREFIX + length])
    except CryptoError:
        raise EnvelopeError("Envelope layer is not addressed to this node") from None
    kind, next_hop, rest = plain[0], plain[1:1 + NODE_ID_SIZE], plain[1 + NODE_ID_SIZE:]
    if kind == LayerKind.RELAY:
        if len(rest) < SEAL_OVERHEAD + LAYER_HEADER:
            raise EnvelopeError("Relay layer carries no inner layer")
        return Relay(next_hop, _pad(rest))
    if kind != LayerKind.DELIVER or len(rest) != BOX_OVERHEAD + MESSAGE_SIZE:
        raise EnvelopeError("Delivery layer is malformed")
    sender = directory.get(next_hop)
    nonce, ciphertext = rest[:NONCE_SIZE], rest[NONCE_SIZE:]
    try:
        padded = Box(identity.box_key, sender.encryption_key()).decrypt(ciphertext, nonce)
    except CryptoError:
        raise EnvelopeError("Message authentication failed") from None
    return Delivery(next_hop, nonce, PrivateMessage.decode(padded))
