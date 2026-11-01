"""Gateway client for the Edge: public relay into topics and the dead drop.

Requests are signed with the HMAC contract in auth.py (RFC FN-1 Section 6)
and sent as X-FaroNet-* headers. Dead-drop slots and their encryption key
are derived from a 32-byte secret the two parties share out of band:

    slot id = SHA-256("FARONET-DEAD-DROP-ID-V1"  || secret || slot as u64 BE), hex
    key     = SHA-256("FARONET-DEAD-DROP-KEY-V1" || secret)
    blob    = SecretBox(key)(len (2 bytes BE) || UTF-8 text || zero padding)

Every blob is exactly 1024 bytes (24-byte nonce, 16-byte tag), so the Edge
stores only same-size opaque data under an identifier it cannot link to
the secret. Errors carry static text only; secrets and text are never logged.
"""

from dataclasses import dataclass
import hashlib
import time
import urllib.error
import urllib.request

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

from faronet import __version__
from faronet.gateway.auth import AuthError, GatewayRequest, new_nonce, sign_request

DROP_BYTES = 1024
DROP_PLAIN = DROP_BYTES - SecretBox.NONCE_SIZE - SecretBox.MACBYTES
MAX_DROP_TEXT = DROP_PLAIN - 2
DEFAULT_AUDIENCE = "faronet-edge"
DEFAULT_KEY_ID = "gateway-1"
# Cloudflare answers 403 (error 1010) to Python's default "Python-urllib" agent
# before the Worker runs, so the client always names itself.
USER_AGENT = f"FaroNet-Gateway/{__version__}"


class GatewayError(RuntimeError):
    """Static messages; `status` is the HTTP status when the Edge answered."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def secret_from_hex(value: str, minimum: int = 32) -> bytes:
    try:
        secret = bytes.fromhex(value or "")
    except ValueError:
        raise GatewayError("Los secretos deben estar en hexadecimal") from None
    if len(secret) < minimum:
        raise GatewayError(f"Los secretos necesitan al menos {minimum} bytes")
    return secret


def drop_slot_id(shared: bytes, slot: int) -> str:
    if len(shared) != 32 or not 0 <= slot < 1 << 64:
        raise GatewayError("El secreto del buzón debe tener 32 bytes y la casilla ser un u64")
    return hashlib.sha256(b"FARONET-DEAD-DROP-ID-V1" + shared + slot.to_bytes(8, "big")).hexdigest()


def _drop_box(shared: bytes) -> SecretBox:
    return SecretBox(hashlib.sha256(b"FARONET-DEAD-DROP-KEY-V1" + shared).digest())


def seal_drop(shared: bytes, text: str) -> bytes:
    data = text.encode("utf-8")
    if len(data) > MAX_DROP_TEXT:
        raise GatewayError("El texto excede el tamaño fijo del buzón")
    plain = (len(data).to_bytes(2, "big") + data).ljust(DROP_PLAIN, b"\0")
    blob = bytes(_drop_box(shared).encrypt(plain))
    assert len(blob) == DROP_BYTES
    return blob


def open_drop(shared: bytes, blob: bytes) -> str:
    if len(blob) != DROP_BYTES:
        raise GatewayError("El contenido del buzón tiene un tamaño incorrecto")
    try:
        plain = _drop_box(shared).decrypt(blob)
    except CryptoError:
        raise GatewayError("El contenido del buzón no abre con este secreto") from None
    length = int.from_bytes(plain[:2], "big")
    if length > MAX_DROP_TEXT or any(plain[2 + length:]):
        raise GatewayError("El relleno del buzón es inválido")
    try:
        return plain[2:2 + length].decode("utf-8")
    except UnicodeDecodeError:
        raise GatewayError("El texto del buzón no es UTF-8") from None


@dataclass(repr=False)
class EdgeClient:
    """One Gateway key talking to one Edge origin. Never print this object."""

    base_url: str
    secret: bytes
    key_id: str = DEFAULT_KEY_ID
    audience: str = DEFAULT_AUDIENCE
    clock: object = time.time
    timeout: float = 10.0

    def _send(self, method: str, path: str, body: bytes = b"") -> tuple[int, bytes]:
        request = GatewayRequest(self.audience, self.key_id, method, path,
                                 str(int(self.clock())), new_nonce(), body)
        try:
            signature = sign_request(request, self.secret)
        except AuthError as error:
            raise GatewayError(str(error)) from None
        http = urllib.request.Request(
            self.base_url.rstrip("/") + path, data=body if method == "POST" else None, method=method,
            headers={"X-FaroNet-Key": self.key_id, "X-FaroNet-Timestamp": request.timestamp,
                     "X-FaroNet-Nonce": request.nonce, "X-FaroNet-Signature": signature,
                     "Content-Type": "application/octet-stream", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(http, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            error.close()
            return error.code, b""
        except (urllib.error.URLError, OSError):
            raise GatewayError("No se pudo contactar el edge") from None

    def publish(self, topic: str, text: str) -> None:
        """Post public text to a topic room. Anyone can read it there and in the feed."""
        status, _ = self._send("POST", f"/gateway/rooms/{topic}", text.encode("utf-8"))
        if status != 202:
            raise GatewayError("El edge rechazó el mensaje público", status)

    def drop_put(self, shared: bytes, slot: int, text: str) -> None:
        status, _ = self._send("POST", f"/gateway/drop/{drop_slot_id(shared, slot)}", seal_drop(shared, text))
        if status != 201:
            raise GatewayError("La casilla del buzón está ocupada" if status == 409 else "El edge rechazó el contenido", status)

    def drop_take(self, shared: bytes, slot: int) -> str | None:
        """Read and delete the slot; None when it is empty or expired."""
        status, body = self._send("GET", f"/gateway/drop/{drop_slot_id(shared, slot)}")
        if status == 404:
            return None
        if status != 200:
            raise GatewayError("El edge rechazó la lectura", status)
        return open_drop(shared, body)
