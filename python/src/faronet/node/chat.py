"""Private terminal chat and relay-only Nodes over LAN links (Layer 7, anonymous).

Each run generates a fresh identity: nothing is written to disk, and a
restart is a new Node to the mesh. Received text exists only on this
terminal; nothing is logged. An alias is self-chosen and proves nothing,
so compare the short ID out of band before trusting who is behind it.
"""

import asyncio
import gc
import sys
import threading

from faronet.node.envelope import MAX_TEXT_BYTES, Delivery, EnvelopeError
from faronet.node.identity import DirectoryError, Identity
from faronet.node.lan import LanError, LanNode
from faronet.faro.address import AddressStore
from faronet.faro.profile import PANIC

DEFAULT_PORT = 7400
DEFAULT_TTL = 300
MAX_TTL = 24 * 3600

HELP = f"""Commands:
  /peers          known nodes: name, whether linked directly, whether reachable
  /to NAME        choose the destination (alias, alias#idprefix or idprefix)
  /ttl SECONDS    message lifetime, 10-{MAX_TTL} (now {{ttl}})
  /quit           leave; nothing is saved
  /panic          erase keys, links and messages, clear the screen and leave
Any other line is sent to the destination (at most {MAX_TEXT_BYTES} UTF-8 bytes)."""


def address(value: str) -> tuple[str, int]:
    """HOST:PORT, with IPv6 hosts in brackets; a bare HOST uses the default port."""
    if value.startswith("["):
        host, _, port = value[1:].partition("]")
        port = port.removeprefix(":")
    else:
        host, _, port = value.rpartition(":") if ":" in value else (value, "", "")
    port = port or str(DEFAULT_PORT)
    if not host or not port.isdigit() or not 0 <= int(port) <= 65535:
        raise ValueError("Addresses must be HOST:PORT")
    return host, int(port)


def add_commands(commands) -> None:
    for name, text in (("chat", "Private terminal chat over the anonymous LAN mesh."),
                       ("mesh-node", "Relay-only mesh Node on the LAN.")):
        parser = commands.add_parser(name, help=text)
        parser.add_argument("--alias", default="",
                            help="Optional public alias: 0-16 letters, digits, - or _.")
        parser.add_argument("--listen", type=address, default=("0.0.0.0", DEFAULT_PORT),
                            help=f"HOST:PORT to accept links on (default 0.0.0.0:{DEFAULT_PORT}).")
        parser.add_argument("--peer", type=address, action="append", default=[],
                            help="HOST:PORT of a neighbor to link to; repeat for more.")
        parser.add_argument("--panic-gpio", metavar="CHIP",
                            help="Watch the Faro's panic button on this GPIO chip (for example "
                                 "/dev/gpiochip0); pressing it erases keys and messages and exits.")
        if name == "chat":
            parser.add_argument("--to", help="Initial destination (alias or ID prefix).")
            parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                                help=f"Message lifetime in seconds (default {DEFAULT_TTL}).")


def name_of(lan: LanNode, node_id: bytes) -> str:
    try:
        alias = lan.directory.get(node_id).alias
    except DirectoryError:
        alias = "?"
    return f"{alias}#{node_id.hex()[:8]}"


class ChatSession:
    """Terminal commands for one LanNode; output goes through `write`."""

    def __init__(self, lan: LanNode, write, ttl: int = DEFAULT_TTL, to: str | None = None) -> None:
        if not 10 <= ttl <= MAX_TTL:
            raise ValueError(f"TTL must be 10-{MAX_TTL} seconds")
        self.lan, self.write, self.ttl = lan, write, ttl
        self.destination: bytes | None = None
        self.panicked = False
        self._pending_to = to
        self._status = None
        lan.on_delivery = self.delivered
        lan.on_change = self.changed

    def resolve(self, name: str) -> bytes:
        alias, _, prefix = name.partition("#")
        known = [n for n in self.lan.directory.node_ids() if n != self.lan.node_id]
        matches = [n for n in known
                   if (not alias or self.lan.directory.get(n).alias == alias)
                   and n.hex().startswith(prefix.lower())]
        if not matches and not prefix and len(alias) >= 4:
            matches = [n for n in known if n.hex().startswith(alias.lower())]
        if len(matches) != 1:
            raise LanError("No single known node matches that name; see /peers")
        return matches[0]

    def changed(self) -> None:
        reachable = sum(bool(self.lan.routes_to(n)) for n in self.lan.directory.node_ids())
        status = (len(self.lan.neighbors()), len(self.lan.directory) - 1, reachable)
        if status != self._status:
            self._status = status
            self.write("· linked {}, known {}, reachable {}".format(*status))
        if self._pending_to:
            try:
                self.destination = self.resolve(self._pending_to)
            except LanError:
                return
            self._pending_to = None
            self.write(f"· destination: {name_of(self.lan, self.destination)}")

    def delivered(self, delivery: Delivery) -> None:
        sender = name_of(self.lan, delivery.sender_id)
        self.write(f"[{sender}] {delivery.message.text}")
        if self.destination is None and self._pending_to is None:
            self.destination = delivery.sender_id
            self.write(f"· replies go to {sender}")

    def handle(self, line: str) -> bool:
        """Run one terminal line; False means quit."""
        line = line.rstrip("\r\n")
        command, _, rest = line.partition(" ")
        try:
            if command == "/quit":
                return False
            if command == "/panic":
                self.panicked = True
                self.destination = None
                return False
            if command == "/help":
                self.write(HELP.format(ttl=self.ttl))
            elif command == "/peers":
                self.peers()
            elif command == "/to":
                self.destination, self._pending_to = self.resolve(rest.strip()), None
                self.write(f"· destination: {name_of(self.lan, self.destination)}")
            elif command == "/ttl":
                if not rest.strip().isdigit() or not 10 <= int(rest) <= MAX_TTL:
                    raise LanError(f"TTL must be 10-{MAX_TTL} seconds")
                self.ttl = int(rest)
                self.write(f"· ttl {self.ttl} s")
            elif line.startswith("/"):
                self.write("Unknown command; /help lists them")
            elif line.strip():
                if self.destination is None:
                    raise LanError("Choose a destination first: /peers, then /to NAME")
                route = self.lan.send_text(self.destination, line, self.ttl)
                hops = " > ".join(name_of(self.lan, hop) for hop in route.relays)
                self.write(f"· sent via {hops} (expires in {self.ttl} s)")
        except (LanError, EnvelopeError) as error:
            self.write(f"! {error}")
        return True

    def peers(self) -> None:
        known = [n for n in self.lan.directory.node_ids() if n != self.lan.node_id]
        self.write(f"· you are {name_of(self.lan, self.lan.node_id)}")
        if not known:
            self.write("· no other nodes known yet")
        for node_id in known:
            linked = "linked" if node_id in self.lan.neighbors() else "      "
            reachable = "reachable" if self.lan.routes_to(node_id) else "no route yet"
            self.write(f"  {name_of(self.lan, node_id):<26} {linked} {reachable}")


def watch_panic(chip: str, on_press) -> None:
    """Thread body: call on_press once the Faro's active-low panic input is pressed."""
    import gpiod
    from gpiod.line import Direction, Edge, Value

    settings = gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.BOTH, active_low=True)
    request = gpiod.request_lines(chip, consumer="faronet-chat-panic", config={PANIC: settings})
    try:
        while request.get_value(PANIC) != Value.ACTIVE:
            if request.wait_edge_events(1.0):
                if any(e.event_type == e.Type.RISING_EDGE for e in request.read_edge_events(max_events=16)):
                    break
        on_press()
    finally:
        request.release()


def _print(text: str) -> None:
    print(text, flush=True)


def _stdin_lines(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
    for line in sys.stdin:
        loop.call_soon_threadsafe(queue.put_nowait, line)
    loop.call_soon_threadsafe(queue.put_nowait, None)


async def _serve(args) -> int:
    lan = LanNode(Identity.generate(), args.alias)
    session = None
    if args.command == "chat":
        session = ChatSession(lan, _print, args.ttl, args.to)
    else:
        status = [None]

        def changed() -> None:
            now = (len(lan.neighbors()), len(lan.directory) - 1)
            if now != status[0]:
                status[0] = now
                _print("· linked {}, known {}".format(*now))

        lan.on_change = changed
    loop = asyncio.get_running_loop()
    panicked = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue()

    def press() -> None:
        panicked.set()
        queue.put_nowait("/panic\n")

    if args.panic_gpio:
        threading.Thread(target=watch_panic, args=(args.panic_gpio, lambda: loop.call_soon_threadsafe(press)),
                         daemon=True).start()
    port = await lan.listen(*args.listen)
    _print(f"FaroNet {args.command} {name_of(lan, lan.node_id)} on port {port}; "
           + ("/help lists commands" if session else "Ctrl+C stops"))
    for host, peer_port in args.peer:
        lan.dial(host, peer_port)
    try:
        if session is None:
            await panicked.wait()
        else:
            threading.Thread(target=_stdin_lines, args=(loop, queue), daemon=True).start()
            while (line := await queue.get()) is not None and session.handle(line):
                pass
        if panicked.is_set() or (session is not None and session.panicked):
            return await _panic(lan)
    finally:
        counters = {key: lan.counters[key] for key in ("sent", "relayed", "delivered", "rejected")}
        await lan.close()
    _print("· stopped; nothing was saved. " + ", ".join(f"{k} {v}" for k, v in counters.items()))
    return 0


async def _panic(lan: LanNode) -> int:
    """RFC FN-1 4.8 and 10: erase what this Node holds, rotate the link address, clear the screen."""
    await lan.wipe()
    gc.collect()
    try:
        AddressStore().rotate()
    except OSError:
        pass  # The keys are gone either way; the address rotates on the next optical command.
    # Clear the visible screen and, where the terminal supports it, its scrollback.
    print("\033[3J\033[2J\033[H", end="", flush=True)
    print("Panic: keys, links and messages erased; link address rotated.", file=sys.stderr)
    return 3


def run(args) -> int:
    try:
        return asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as error:
        print(f"Mesh command failed: {error}", file=sys.stderr)
        return 2
