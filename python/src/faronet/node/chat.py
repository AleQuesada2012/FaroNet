"""Private terminal chat and relay-only Nodes over LAN links (Layer 7, anonymous).

Each run generates a fresh identity: nothing is written to disk, and a
restart is a new Node to the mesh. Received text exists only on this
terminal; nothing is logged. An alias is self-chosen and proves nothing,
so compare the short ID out of band before trusting who is behind it.
"""

import argparse
import asyncio
import gc
import json
import signal
import subprocess
import sys
import threading

from faronet.node.envelope import MAX_TEXT_BYTES, Delivery, EnvelopeError
from faronet.node.identity import ALIAS_PATTERN, DirectoryError, Identity
from faronet.node.lan import LanError, LanNode
from faronet.faro.address import AddressStore
from faronet.gateway.client import GatewayError
from faronet.faro.profile import PANIC

DEFAULT_PORT = 7400
DEFAULT_TTL = 300
MAX_TTL = 24 * 3600
OPTICAL_HANDSHAKE_SECONDS = 600
PANIC_EXIT = 3

HELP = f"""Comandos:
  /peers          nodos conocidos: nombre, si hay enlace directo, si hay ruta
  /to NOMBRE      elige el destino (alias, alias#prefijo o prefijo del ID)
  /ttl SEGUNDOS   vida del mensaje, 10-{MAX_TTL} (ahora {{ttl}})
  /quit           salir; no se guarda nada
  /panic          borrar llaves, enlaces y mensajes, limpiar la pantalla y salir
Cualquier otra línea se envía al destino (máximo {MAX_TEXT_BYTES} bytes UTF-8)."""


class OptionError(argparse.ArgumentTypeError, ValueError):
    """argparse shows this text as is; plain ValueError text would be replaced in English."""


def alias(value: str) -> str:
    if not ALIAS_PATTERN.fullmatch(value):
        raise OptionError("El alias debe tener 0-16 letras, dígitos, - o _ (sin acentos)")
    return value


def address(value: str) -> tuple[str, int]:
    """HOST:PORT, with IPv6 hosts in brackets; a bare HOST uses the default port."""
    if value.startswith("["):
        host, _, port = value[1:].partition("]")
        port = port.removeprefix(":")
    else:
        host, _, port = value.rpartition(":") if ":" in value else (value, "", "")
    port = port or str(DEFAULT_PORT)
    if not host or not port.isdigit() or not 0 <= int(port) <= 65535:
        raise OptionError("Las direcciones deben ser HOST:PUERTO")
    return host, int(port)


def add_commands(commands) -> None:
    for name, text in (("chat", "Chat privado de terminal sobre la mesh anónima en la LAN."),
                       ("mesh-node", "Nodo de la mesh en la LAN que solo retransmite.")):
        parser = commands.add_parser(name, help=text)
        parser.add_argument("--alias", type=alias, default="",
                            help="Alias público opcional: 0-16 letras, dígitos, - o _.")
        parser.add_argument("--listen", type=address, default=("0.0.0.0", DEFAULT_PORT),
                            help=f"HOST:PUERTO donde aceptar enlaces (por defecto 0.0.0.0:{DEFAULT_PORT}).")
        parser.add_argument("--peer", type=address, action="append", default=[],
                            help="HOST:PUERTO de un vecino al cual enlazarse; repetir para más.")
        parser.add_argument("--edge-publish", metavar="URL", nargs="?", const="https://faronet-edge.faronet.workers.dev",
                            help="Solo en el gateway: publicar en la réplica pública del edge cada entrada "
                                 "del directorio que este nodo conozca (usa el secreto de gateway-secret).")
        parser.add_argument("--panic-gpio", metavar="CHIP",
                            help="Vigilar el botón de pánico del Faro en este chip GPIO (por ejemplo "
                                 "/dev/gpiochip0); al pulsarlo se borran llaves y mensajes y se sale.")
        parser.add_argument("--faro-peer", type=link_id, metavar="DIRECCION",
                            help="Enlazarse por luz con el nodo del otro Faro (su optical-address); "
                                 "requiere sudo y la misma --faro-session en ambos.")
        parser.add_argument("--faro-session", type=link_id, metavar="SESION",
                            help="Sesión acordada para el enlace óptico (optical-session).")
        parser.add_argument("--half-bit-ms", type=float, default=5,
                            help="Medio bit del enlace óptico en ms, igual en ambos Faros (por defecto 5).")
        parser.add_argument("--chip", default="/dev/gpiochip0", help="Chip GPIO del Faro.")
        parser.add_argument("--rx-inverted", action="store_true", help="Invertir la polaridad medida de RX.")
        if name == "chat":
            parser.add_argument("--to", help="Destino inicial (alias o prefijo del ID).")
            parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                                help=f"Vida del mensaje en segundos (por defecto {DEFAULT_TTL}).")


def link_id(value: str) -> bytes:
    if len(value) != 16 or any(c not in "0123456789abcdef" for c in value):
        raise OptionError("Las direcciones y sesiones ópticas son 16 caracteres hex en minúscula")
    return bytes.fromhex(value)


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
            raise ValueError(f"El TTL debe estar entre 10 y {MAX_TTL} segundos")
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
            raise LanError("Ningún nodo conocido coincide con ese nombre de forma única; mira /peers")
        return matches[0]

    def changed(self) -> None:
        reachable = sum(bool(self.lan.routes_to(n)) for n in self.lan.directory.node_ids())
        status = (len(self.lan.neighbors()), len(self.lan.directory) - 1, reachable)
        if status != self._status:
            self._status = status
            self.write("· enlazados {}, conocidos {}, con ruta {}".format(*status))
        if self._pending_to:
            try:
                self.destination = self.resolve(self._pending_to)
            except LanError:
                return
            self._pending_to = None
            self.write(f"· destino: {name_of(self.lan, self.destination)}")

    def delivered(self, delivery: Delivery) -> None:
        sender = name_of(self.lan, delivery.sender_id)
        # Remote text must not forge lines or drive the terminal (newlines, ANSI/OSC escapes).
        text = "".join(c if c.isprintable() else " " for c in delivery.message.text)
        self.write(f"[{sender}] {text}")
        if self.destination is None and self._pending_to is None:
            self.destination = delivery.sender_id
            self.write(f"· las respuestas van a {sender}")

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
                self.write(f"· destino: {name_of(self.lan, self.destination)}")
            elif command == "/ttl":
                if not rest.strip().isdigit() or not 10 <= int(rest) <= MAX_TTL:
                    raise LanError(f"El TTL debe estar entre 10 y {MAX_TTL} segundos")
                self.ttl = int(rest)
                self.write(f"· TTL {self.ttl} s")
            elif line.startswith("/"):
                self.write("Comando desconocido; /help los muestra")
            elif line.strip():
                if self.destination is None:
                    raise LanError("Primero elige un destino: /peers y luego /to NOMBRE")
                route = self.lan.send_text(self.destination, line, self.ttl)
                hops = " > ".join(name_of(self.lan, hop) for hop in route.relays)
                self.write(f"· enviado por {hops} (caduca en {self.ttl} s)")
        except (LanError, EnvelopeError) as error:
            self.write(f"! {error}")
        return True

    def peers(self) -> None:
        known = [n for n in self.lan.directory.node_ids() if n != self.lan.node_id]
        self.write(f"· tú eres {name_of(self.lan, self.lan.node_id)}")
        if not known:
            self.write("· aún no se conoce ningún otro nodo")
        for node_id in known:
            linked = "enlazado" if node_id in self.lan.neighbors() else "        "
            reachable = "con ruta" if self.lan.routes_to(node_id) else "aún sin ruta"
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
                _print("· enlazados {}, conocidos {}".format(*now))

        lan.on_change = changed
    loop = asyncio.get_running_loop()
    panicked = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue()

    def press() -> None:
        panicked.set()
        queue.put_nowait("/panic\n")

    bridge = None
    if args.faro_peer:
        # The bridge owns the Faro's GPIO, panic input included; its panic exit is ours.
        bridge, bridge_port = _start_bridge(args)
        threading.Thread(target=_watch_bridge, args=(bridge, lambda: loop.call_soon_threadsafe(press)),
                         daemon=True).start()
    try:
        if args.panic_gpio:
            threading.Thread(target=watch_panic, args=(args.panic_gpio, lambda: loop.call_soon_threadsafe(press)),
                             daemon=True).start()
        if args.edge_publish:
            _publish_directory(lan, args.edge_publish)
        port = await lan.listen(*args.listen)
        _print(f"FaroNet {args.command} {name_of(lan, lan.node_id)} en el puerto {port}; "
               + ("/help muestra los comandos" if session else "Ctrl+C lo detiene"))
        for host, peer_port in args.peer:
            lan.dial(host, peer_port)
        if bridge is not None:
            lan.dial("127.0.0.1", bridge_port, handshake_seconds=OPTICAL_HANDSHAKE_SECONDS)
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
        if bridge is not None and bridge.poll() is None:
            # SIGTERM, not SIGINT: a background shell job passes SIGINT to children as ignored.
            bridge.send_signal(signal.SIGTERM)
            try:
                bridge.wait(10)
            except subprocess.TimeoutExpired:
                bridge.kill()
    labels = {"sent": "enviados", "relayed": "retransmitidos", "delivered": "recibidos", "rejected": "rechazados"}
    _print("· detenido; no se guardó nada. " + ", ".join(f"{labels[k]} {v}" for k, v in counters.items()))
    return 0


def _start_bridge(args) -> tuple[subprocess.Popen, int]:
    """Start optical-bridge on a free localhost port and return it with that port."""
    if args.faro_session is None:
        raise ValueError("--faro-peer necesita --faro-session")
    if args.panic_gpio:
        raise ValueError("Con --faro-peer el puente óptico ya vigila el botón de pánico; quita --panic-gpio")
    command = [sys.executable, "-m", "faronet", "optical-bridge", "--hardware-ready",
               "--chip", args.chip, "--half-bit-ms", str(args.half_bit_ms), "--listen", "127.0.0.1:0",
               "--peer", args.faro_peer.hex(), "--session", args.faro_session.hex()]
    if args.rx_inverted:
        command.append("--rx-inverted")
    # Its own process group: Ctrl+C in the chat must not interrupt the bridge mid-frame.
    bridge = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        ready = json.loads(bridge.stdout.readline() or "{}")
    except json.JSONDecodeError:
        ready = {}
    if ready.get("ready") != "optical-bridge":
        bridge.kill()
        raise OSError(f"No se pudo iniciar el puente óptico (código {bridge.wait()})")
    _print(f"· enlace óptico listo: trama de {ready['frame_seconds']:.1f} s; el saludo por luz tarda minutos")
    return bridge, ready["port"]


def _watch_bridge(bridge: subprocess.Popen, on_panic) -> None:
    """Thread body: report optical resets, then the bridge's exit; panic exits trigger ours."""
    for line in bridge.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("reason") not in (None, "start"):
            _print(f"· enlace óptico reiniciado (época {event['epoch']}); el saludo se repite")
    if bridge.wait() == PANIC_EXIT:
        on_panic()
    elif bridge.returncode not in (0, 130):
        _print(f"! el puente óptico terminó (código {bridge.returncode}); el enlace por luz se perdió")


def _publish_directory(lan: LanNode, url: str) -> None:
    """Gateway node: send each new verified entry to the Edge replica, off the event loop."""
    from faronet.gateway.client import GatewayError
    from faronet.gateway.commands import edge_client

    client = edge_client(url)
    published: dict[bytes, int] = {}
    pushes: set[asyncio.Task] = set()
    loop = asyncio.get_running_loop()
    previous = lan.on_change

    async def push(entries) -> None:
        sent = 0
        for entry in entries:
            try:
                # False: the Edge already holds a newer entry for this Node.
                sent += await loop.run_in_executor(None, client.publish_entry, entry)
            except GatewayError as error:
                published.pop(entry.node_id, None)
                _print(f"! directorio: {error}")
        if sent:
            s = "" if sent == 1 else "s"
            _print(f"· directorio: {sent} entrada{s} publicada{s} en el edge")

    def changed() -> None:
        previous()
        fresh = [lan.directory.get(n) for n in lan.directory.node_ids()
                 if published.get(n) != lan.directory.get(n).issued_at]
        for entry in fresh:
            published[entry.node_id] = entry.issued_at
        if fresh:
            task = loop.create_task(push(fresh))
            pushes.add(task)  # The loop keeps only weak references to tasks.
            task.add_done_callback(pushes.discard)

    lan.on_change = changed
    changed()


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
    print("Pánico: llaves, enlaces y mensajes borrados; dirección física rotada.", file=sys.stderr)
    return PANIC_EXIT


def run(args) -> int:
    # SIGTERM stops like Ctrl+C, so an optical bridge is always told to turn the Faro off.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        return asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, GatewayError) as error:
        print(f"Falló el comando de la mesh: {error}", file=sys.stderr)
        return 2
