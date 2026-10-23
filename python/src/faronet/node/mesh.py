"""In-process mesh simulation: Nodes, neighbor links and onion forwarding.

This exercises proposal 0002 end to end on a laptop. Two Nodes can be
joined by the simulated optical link from the first milestone, so an
envelope really crosses Manchester-coded Faro frames in six fragments.
Other neighbors use an instant in-memory link standing in for the future
laptop/LAN transport, which is not specified yet.

There are no sockets, threads, wall-clock sleeps or GPIO operations.
Counters are anonymous; message text is kept only in the destination's
inbox object so tests can check it.
"""

from collections import Counter, OrderedDict
from collections.abc import Callable
import secrets
from typing import Protocol

from faronet.dispositivo_luz_adaptador import DispositivoLuzAdaptador
from faronet.dispositivo_luz_adaptador.simulation import FaultPlan, LinkError, SimulatedLink
from faronet.node.envelope import (
    RELAY_HOPS, Delivery, EnvelopeError, PrivateMessage, Relay, Route, build_envelope, peel,
)
from faronet.node.fragment import FRAGMENT_COUNT, Reassembler, fragment
from faronet.node.identity import Directory, DirectoryError, Identity

SEEN_NONCES = 1024
DEFAULT_ENTRY_LIFETIME = 7 * 24 * 3600


class MeshError(ValueError):
    """Static text only; the simulation never reports IDs or message text."""


class Link(Protocol):
    def carry(self, source: bytes, destination: bytes, envelope: bytes) -> bool:
        """Move one envelope to a neighbor; True means the neighbor received it."""


class Node:
    """A mesh participant: originates, relays or receives fixed-size envelopes."""

    def __init__(self, identity: Identity, directory: Directory, clock: Callable[[], int]) -> None:
        self.identity = identity
        self.directory = directory
        self.clock = clock
        self.neighbors: dict[bytes, Link] = {}
        self.inbox: list[Delivery] = []
        self.counters: Counter[str] = Counter()
        self._seen: OrderedDict[bytes, None] = OrderedDict()

    @property
    def node_id(self) -> bytes:
        return self.identity.node_id

    def attach(self, neighbor_id: bytes, link: Link) -> None:
        if neighbor_id == self.node_id:
            raise MeshError("A node cannot be its own neighbor")
        self.neighbors[neighbor_id] = link

    def send(self, route: Route, message: PrivateMessage) -> bool:
        link = self.neighbors.get(route.relays[0])
        if link is None:
            raise MeshError("The first relay must be a direct neighbor")
        envelope = build_envelope(self.identity, self.directory, route, message)
        self.counters["sent"] += 1
        return link.carry(self.node_id, route.relays[0], envelope)

    def receive(self, envelope: bytes) -> None:
        """Peel one layer. Failures are counted, never raised to the link."""
        try:
            result = peel(self.identity, self.directory, envelope)
        except (EnvelopeError, DirectoryError):
            self.counters["rejected"] += 1
            return
        if isinstance(result, Relay):
            link = self.neighbors.get(result.next_hop)
            if link is None:
                self.counters["undeliverable"] += 1
                return
            self.counters["relayed"] += 1
            link.carry(self.node_id, result.next_hop, result.envelope)
            return
        if result.nonce in self._seen:
            self.counters["duplicate"] += 1
            return
        self._seen[result.nonce] = None
        if len(self._seen) > SEEN_NONCES:
            self._seen.popitem(last=False)
        if result.message.expires_at < self.clock():
            self.counters["expired"] += 1
            return
        self.counters["delivered"] += 1
        self.inbox.append(result)


class DirectLink:
    """Instant bidirectional neighbor link, a placeholder for the LAN transport."""

    def __init__(self, mesh: "MeshSimulation") -> None:
        self._mesh = mesh
        self.carried = 0

    def carry(self, source: bytes, destination: bytes, envelope: bytes) -> bool:
        self.carried += 1
        self._mesh.nodes[destination].receive(envelope)
        return True


class OpticalLink:
    """Two Nodes joined through the simulated Faro link, six frames per envelope.

    The sending adapter holds the scripted turn for the whole envelope. The
    receiver's acceptances come from the simulator's delivery evidence, so a
    lost final ACK still delivers exactly once while the sender retries.
    """

    def __init__(
        self, mesh: "MeshSimulation", node_a: bytes, node_b: bytes, *,
        address_a: bytes = b"FAKE0001", address_b: bytes = b"FAKE0002", session: bytes = b"SESSION1",
    ) -> None:
        self._mesh = mesh
        self.link = SimulatedLink(address_a, address_b, session)
        self._addresses = {node_a: address_a, node_b: address_b}
        self._adapters = {
            node_a: DispositivoLuzAdaptador(self.link, address_a),
            node_b: DispositivoLuzAdaptador(self.link, address_b),
        }
        self._reassemblers = {node_a: Reassembler(), node_b: Reassembler()}
        self.next_faults: FaultPlan | None = None
        self.frames_attempted = 0
        self.envelopes_carried = 0
        self.envelopes_failed = 0

    def carry(self, source: bytes, destination: bytes, envelope: bytes) -> bool:
        if source not in self._adapters or destination not in self._adapters or source == destination:
            raise MeshError("Optical link endpoints do not match")
        try:
            self.link.grant_turn(self._addresses[source])
        except LinkError:
            self.envelopes_failed += 1
            return False
        reassembler = self._reassemblers[destination]
        for payload in fragment(envelope, secrets.randbelow(1 << 16)):
            faults, self.next_faults = self.next_faults, None
            result = self._adapters[source].send(payload, faults)
            self.frames_attempted += result.attempts
            for accepted in result.deliveries:
                complete = reassembler.accept(accepted)
                if complete is not None:
                    self._mesh.nodes[destination].receive(complete)
            if not result.acknowledged:
                self.envelopes_failed += 1
                return False
        self.envelopes_carried += 1
        return True

    def reset_session(self, session: bytes) -> None:
        self.link.reset_session(session)


class MeshSimulation:
    """A laptop mesh with one shared verified directory and explicit links."""

    def __init__(self, clock: Callable[[], int] = lambda: 1791561600) -> None:
        self.clock = clock
        self.directory = Directory()
        self.nodes: dict[bytes, Node] = {}
        self._order: list[bytes] = []

    def add_node(self, alias: str = "") -> Node:
        identity = Identity.generate()
        now = self.clock()
        self.directory.add(identity.directory_entry(now, now + DEFAULT_ENTRY_LIFETIME, alias), now)
        node = Node(identity, self.directory, self.clock)
        self.nodes[node.node_id] = node
        self._order.append(node.node_id)
        return node

    def connect(self, a: Node, b: Node) -> DirectLink:
        link = DirectLink(self)
        a.attach(b.node_id, link)
        b.attach(a.node_id, link)
        return link

    def connect_optical(self, a: Node, b: Node, **options: bytes) -> OpticalLink:
        link = OpticalLink(self, a.node_id, b.node_id, **options)
        a.attach(b.node_id, link)
        b.attach(a.node_id, link)
        return link

    def find_route(self, sender: Node, destination: Node) -> Route:
        """Source routing over known adjacency: three distinct relays, in order."""
        if sender is destination:
            raise MeshError("Sender and destination must differ")

        def extend(path: tuple[bytes, ...]) -> tuple[bytes, ...] | None:
            current = self.nodes[path[-1]]
            if len(path) == RELAY_HOPS + 1:
                return path if destination.node_id in current.neighbors else None
            for candidate in self._order:
                if candidate in path or candidate == destination.node_id:
                    continue
                if candidate in current.neighbors:
                    found = extend((*path, candidate))
                    if found is not None:
                        return found
            return None

        path = extend((sender.node_id,))
        if path is None:
            raise MeshError("No route with three distinct relays exists")
        return Route(path[1:], destination.node_id)

    def send_text(self, sender: Node, destination: Node, text: str, ttl: int) -> bool:
        route = self.find_route(sender, destination)
        return sender.send(route, PrivateMessage(text, self.clock() + ttl))


def frames_per_envelope() -> int:
    return FRAGMENT_COUNT
