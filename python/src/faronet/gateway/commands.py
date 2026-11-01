"""CLI for the Gateway client. Secrets come only from the environment, never arguments.

FARONET_GATEWAY_SECRET  this Gateway's HMAC secret, hex (same value as the Edge's GATEWAY_SECRET)
FARONET_DROP_SECRET     32-byte dead-drop secret shared with the other party, hex
FARONET_GATEWAY_KEY     key ID (default gateway-1); FARONET_EDGE_AUDIENCE (default faronet-edge)
"""

import json
import os
import secrets
import sys

from faronet.gateway.client import (
    DEFAULT_AUDIENCE, DEFAULT_KEY_ID, MAX_DROP_TEXT, EdgeClient, GatewayError, secret_from_hex,
)

EDGE_URL = "https://faronet-edge.faronet.workers.dev"
NAMES = ("gateway-publish", "drop-secret", "drop-put", "drop-take")


def add_commands(commands) -> None:
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
    return EdgeClient(args.url, secret_from_hex(os.environ.get("FARONET_GATEWAY_SECRET", "")),
                      os.environ.get("FARONET_GATEWAY_KEY", DEFAULT_KEY_ID),
                      os.environ.get("FARONET_EDGE_AUDIENCE", DEFAULT_AUDIENCE))


def run(args) -> int:
    try:
        if args.command == "drop-secret":
            print(secrets.token_hex(32))
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
        print(f"Gateway command failed: {error}{status}", file=sys.stderr)
        return 2
