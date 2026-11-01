"""CLI for the Gateway client. Secrets come only from the environment, never arguments.

FARONET_GATEWAY_SECRET  this Gateway's HMAC secret, hex (same value as the Edge's GATEWAY_SECRET);
                        if unset, the file written by `gateway-secret` is used
FARONET_DROP_SECRET     32-byte dead-drop secret shared with the other party, hex
FARONET_GATEWAY_KEY     key ID (default gateway-1); FARONET_EDGE_AUDIENCE (default faronet-edge)
"""

import getpass
import json
import os
import secrets
import sys

from faronet.faro.address import state_dir

from faronet.gateway.client import (
    DEFAULT_AUDIENCE, DEFAULT_KEY_ID, MAX_DROP_TEXT, EdgeClient, GatewayError, secret_from_hex,
)

EDGE_URL = "https://faronet-edge.faronet.workers.dev"
NAMES = ("gateway-secret", "gateway-publish", "drop-secret", "drop-put", "drop-take")


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
            raise GatewayError("No Gateway secret: run gateway-secret or set FARONET_GATEWAY_SECRET") from None
    return secret_from_hex(value)


def add_commands(commands) -> None:
    commands.add_parser("gateway-secret",
                        help="Store this Gateway's secret (typed hidden) in an owner-only file.")
    publish = commands.add_parser("gateway-publish", help="Post PUBLIC text to an Edge topic as the Gateway.")
    commands.add_parser("drop-secret", help="Generate a new 32-byte dead-drop secret to share out of band.")
    put = commands.add_parser("drop-put", help=f"Leave up to {MAX_DROP_TEXT} bytes in a dead-drop slot.")
    take = commands.add_parser("drop-take", help="Read and delete a dead-drop slot.")
    for parser in (publish, put, take):
        parser.add_argument("--url", default=EDGE_URL, help=f"Edge origin (default {EDGE_URL}).")
    publish.add_argument("--topic", required=True, help="Topic: 1-32 of a-z, 0-9 and -.")
    publish.add_argument("--text", required=True, help="Public text; anyone can read it.")
    for parser in (put, take):
        parser.add_argument("--slot", type=int, required=True, help="Slot number agreed with the other party.")
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
        if args.command == "gateway-secret":
            store_secret(getpass.getpass("Gateway secret (hex, not shown): ").strip())
            print(json.dumps({"stored": str(secret_path())}))
            return 0
        client = _client(args)
        if args.command == "gateway-publish":
            client.publish(args.topic, args.text)
            print(json.dumps({"published": args.topic}))
            return 0
        shared = secret_from_hex(os.environ.get("FARONET_DROP_SECRET", ""))
        if len(shared) != 32:
            raise GatewayError("FARONET_DROP_SECRET must be exactly 32 bytes (see drop-secret)")
        if args.command == "drop-put":
            client.drop_put(shared, args.slot, args.text)
            print(json.dumps({"stored_slot": args.slot, "expires_hours": 24}))
            return 0
        text = client.drop_take(shared, args.slot)
        print(json.dumps({"slot": args.slot, "empty": text is None}))
        if text is not None:
            print(text)
        return 0
    except GatewayError as error:
        status = f" (HTTP {error.status})" if error.status else ""
        if error.status == 403:
            status += "; blocked by Cloudflare before the Worker, not by FaroNet"
        print(f"Gateway command failed: {error}{status}", file=sys.stderr)
        return 2
