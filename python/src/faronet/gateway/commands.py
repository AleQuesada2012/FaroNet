"""CLI for the Gateway client. Secrets come only from the environment, never arguments.

FARONET_GATEWAY_SECRET  this Gateway's HMAC secret, hex (same value as the Edge's GATEWAY_SECRET);
                        if unset, the file written by `gateway-secret` is used
FARONET_DROP_SECRET     32-byte dead-drop secret shared with the other party, hex
FARONET_GATEWAY_KEY     key ID (default gateway-1); FARONET_EDGE_AUDIENCE (default faronet-edge)
"""

import getpass
import os
import secrets
import sys

from faronet.faro.address import state_dir

from faronet.gateway.client import (
    DEFAULT_AUDIENCE, DEFAULT_KEY_ID, MAX_DROP_TEXT, EdgeClient, GatewayError, fetch_directory,
    secret_from_hex,
)

EDGE_URL = "https://faronet-edge.faronet.workers.dev"
NAMES = ("gateway-secret", "gateway-publish", "drop-secret", "drop-put", "drop-take", "directory-fetch")


def secret_path():
    return state_dir() / "gateway-secret"


def store_secret(value: str) -> None:
    """Keep the Gateway secret in an owner-only file, replacing any previous one."""
    secret_from_hex(value)
    path = secret_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(value + "\n")
    os.replace(temporary, path)


def load_secret() -> bytes:
    value = os.environ.get("FARONET_GATEWAY_SECRET")
    if not value:
        try:
            value = secret_path().read_text().strip()
        except OSError:
            raise GatewayError("No hay secreto del gateway: ejecuta gateway-secret o define FARONET_GATEWAY_SECRET") from None
    return secret_from_hex(value)


def add_commands(commands) -> None:
    commands.add_parser("gateway-secret",
                        help="Guardar el secreto de este gateway (se escribe oculto) en un archivo privado.")
    publish = commands.add_parser("gateway-publish", help="Publicar texto PÚBLICO en un tema del edge como gateway.")
    commands.add_parser("drop-secret", help="Generar un secreto nuevo de 32 bytes para el buzón, a compartir fuera de banda.")
    put = commands.add_parser("drop-put", help=f"Dejar hasta {MAX_DROP_TEXT} bytes en una casilla del buzón.")
    take = commands.add_parser("drop-take", help="Leer y borrar una casilla del buzón.")
    fetch = commands.add_parser("directory-fetch",
                                help="Leer y verificar la réplica pública del directorio en el edge.")
    for parser in (publish, put, take, fetch):
        parser.add_argument("--url", default=EDGE_URL, help=f"Origen del edge (por defecto {EDGE_URL}).")
    publish.add_argument("--topic", required=True, help="Tema: 1-32 caracteres de a-z, 0-9 y -.")
    publish.add_argument("--text", required=True, help="Texto público; cualquiera puede leerlo.")
    for parser in (put, take):
        parser.add_argument("--slot", type=int, required=True, help="Número de casilla acordado con la otra persona.")
    put.add_argument("--text", required=True)


def _client(args) -> EdgeClient:
    return EdgeClient(args.url, load_secret(),
                      os.environ.get("FARONET_GATEWAY_KEY", DEFAULT_KEY_ID),
                      os.environ.get("FARONET_EDGE_AUDIENCE", DEFAULT_AUDIENCE))


def run(args) -> int:
    try:
        if args.command == "drop-secret":
            print(secrets.token_hex(32))
            return 0
        if args.command == "directory-fetch":
            entries, rejected = fetch_directory(args.url)
            print(f"Directorio del edge: {len(entries)} entradas verificadas, {rejected} rechazadas.")
            for entry in entries:
                print(f"  {entry.alias or '?'}#{entry.node_id.hex()[:8]}")
            return 0
        if args.command == "gateway-secret":
            store_secret(getpass.getpass("Secreto del gateway (hex, no se muestra): ").strip())
            print(f"Secreto guardado en {secret_path()}.")
            return 0
        client = _client(args)
        if args.command == "gateway-publish":
            client.publish(args.topic, args.text)
            print(f"Publicado en el tema {args.topic}.")
            return 0
        shared = secret_from_hex(os.environ.get("FARONET_DROP_SECRET", ""))
        if len(shared) != 32:
            raise GatewayError("FARONET_DROP_SECRET debe tener exactamente 32 bytes (ver drop-secret)")
        if args.command == "drop-put":
            client.drop_put(shared, args.slot, args.text)
            print(f"Guardado en la casilla {args.slot}; caduca en 24 horas o al leerlo.")
            return 0
        text = client.drop_take(shared, args.slot)
        if text is None:
            print(f"La casilla {args.slot} está vacía.")
        else:
            print(f"Casilla {args.slot} (ya borrada del edge):")
            print(text)
        return 0
    except GatewayError as error:
        status = f" (HTTP {error.status})" if error.status else ""
        if error.status == 403:
            status += "; bloqueado por Cloudflare antes del Worker, no por FaroNet"
        print(f"Falló el comando del gateway: {error}{status}", file=sys.stderr)
        return 2
