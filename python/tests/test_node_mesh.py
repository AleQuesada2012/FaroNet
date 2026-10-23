"""Mesh simulation: routing over adjacency, optical hop, failures and privacy counters."""

import unittest

from faronet.dispositivo_luz_adaptador.simulation import Fault, FaultPlan
from faronet.node.envelope import PrivateMessage, Route, build_envelope
from faronet.node.fragment import FRAGMENT_COUNT
from faronet.node.mesh import MeshError, MeshSimulation

NOW = 1791561600


class Topology:
    """pi_3 -- optical -- pi_2 -- LAN -- four laptop Nodes (full mesh among laptops)."""

    def __init__(self, clock=lambda: NOW):
        self.simulation = MeshSimulation(clock)
        self.pi_3 = self.simulation.add_node('pi-3')
        self.pi_2 = self.simulation.add_node('pi-2')
        self.laptops = [self.simulation.add_node() for _ in range(4)]
        self.optical = self.simulation.connect_optical(self.pi_3, self.pi_2)
        self.lan = [self.simulation.connect(self.pi_2, laptop) for laptop in self.laptops]
        for index, laptop in enumerate(self.laptops):
            for other in self.laptops[index + 1:]:
                self.simulation.connect(laptop, other)

    def totals(self, counter: str) -> int:
        return sum(node.counters[counter] for node in self.simulation.nodes.values())


class RoutingTests(unittest.TestCase):
    def test_route_has_three_distinct_adjacent_relays(self):
        topology = Topology()
        route = topology.simulation.find_route(topology.pi_3, topology.laptops[3])
        hops = (topology.pi_3.node_id, *route.relays, route.destination)
        self.assertEqual(route.relays[0], topology.pi_2.node_id)
        self.assertEqual(len(set(hops)), 5)
        for previous, current in zip(hops, hops[1:]):
            self.assertIn(current, topology.simulation.nodes[previous].neighbors)

    def test_impossible_routes_fail_explicitly(self):
        simulation = MeshSimulation()
        a, b, c, d, e = (simulation.add_node() for _ in range(5))
        simulation.connect(a, b)
        simulation.connect(b, c)
        simulation.connect(c, d)
        with self.assertRaises(MeshError):
            simulation.find_route(a, d)
        with self.assertRaises(MeshError):
            simulation.find_route(a, a)
        with self.assertRaises(MeshError):
            a.send(Route((c.node_id, d.node_id, b.node_id), e.node_id), PrivateMessage('x', NOW))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.topology = Topology()
        self.simulation = self.topology.simulation

    def test_message_crosses_optical_hop_and_three_relays_once(self):
        destination = self.topology.laptops[3]
        self.assertTrue(self.simulation.send_text(self.topology.pi_3, destination, 'synthetic', 300))
        self.assertEqual([delivery.message.text for delivery in destination.inbox], ['synthetic'])
        self.assertEqual(destination.inbox[0].sender_id, self.topology.pi_3.node_id)
        self.assertEqual(self.topology.totals('delivered'), 1)
        self.assertEqual(self.topology.totals('relayed'), 3)
        self.assertEqual(self.topology.totals('rejected'), 0)
        self.assertEqual(self.topology.optical.envelopes_carried, 1)
        self.assertEqual(self.topology.optical.frames_attempted, FRAGMENT_COUNT)
        for node in self.simulation.nodes.values():
            if node is not destination:
                self.assertEqual(node.inbox, [])

    def test_reply_crosses_the_optical_link_in_the_other_direction(self):
        laptop = self.topology.laptops[0]
        self.assertTrue(self.simulation.send_text(self.topology.pi_3, laptop, 'request', 300))
        self.assertTrue(self.simulation.send_text(laptop, self.topology.pi_3, 'reply', 300))
        self.assertEqual([d.message.text for d in self.topology.pi_3.inbox], ['reply'])
        self.assertEqual(self.topology.optical.envelopes_carried, 2)
        self.assertEqual(self.topology.optical.frames_attempted, 2 * FRAGMENT_COUNT)

    def test_lost_ack_on_a_fragment_still_delivers_exactly_once(self):
        self.topology.optical.next_faults = FaultPlan(ack=(Fault.DROP,))
        destination = self.topology.laptops[1]
        self.assertTrue(self.simulation.send_text(self.topology.pi_3, destination, 'once', 300))
        self.assertEqual(len(destination.inbox), 1)
        self.assertEqual(self.topology.optical.frames_attempted, FRAGMENT_COUNT + 1)
        self.assertEqual(self.topology.totals('duplicate'), 0)

    def test_retry_exhaustion_fails_without_delivery_until_reset(self):
        self.topology.optical.next_faults = FaultPlan(data=(Fault.DROP,) * 3)
        destination = self.topology.laptops[2]
        self.assertFalse(self.simulation.send_text(self.topology.pi_3, destination, 'lost', 300))
        self.assertEqual(destination.inbox, [])
        self.assertEqual(self.topology.optical.envelopes_failed, 1)
        self.assertFalse(self.simulation.send_text(self.topology.pi_3, destination, 'blocked', 300))
        self.assertEqual(self.topology.optical.envelopes_failed, 2)
        self.topology.optical.reset_session(b'SESSION2')
        self.assertTrue(self.simulation.send_text(self.topology.pi_3, destination, 'after', 300))
        self.assertEqual([d.message.text for d in destination.inbox], ['after'])

    def test_expired_messages_are_not_delivered(self):
        destination = self.topology.laptops[0]
        route = self.simulation.find_route(self.topology.pi_2, destination)
        self.assertTrue(self.topology.pi_2.send(route, PrivateMessage('late', NOW - 1)))
        self.assertEqual(destination.inbox, [])
        self.assertEqual(destination.counters['expired'], 1)
        self.assertEqual(self.topology.totals('relayed'), 3)

    def test_replayed_envelope_is_delivered_once(self):
        sender, destination = self.topology.laptops[0], self.topology.laptops[3]
        route = self.simulation.find_route(sender, destination)
        envelope = build_envelope(sender.identity, self.simulation.directory, route, PrivateMessage('dup', NOW + 60))
        first_relay = self.simulation.nodes[route.relays[0]]
        for _ in range(3):
            first_relay.receive(envelope)
        self.assertEqual(len(destination.inbox), 1)
        self.assertEqual(destination.counters['duplicate'], 2)
        self.assertEqual(first_relay.counters['relayed'], 3)

    def test_misrouted_or_garbage_envelopes_are_counted_not_delivered(self):
        sender, destination = self.topology.laptops[0], self.topology.laptops[3]
        route = self.simulation.find_route(sender, destination)
        envelope = build_envelope(sender.identity, self.simulation.directory, route, PrivateMessage('x', NOW + 60))
        wrong = self.topology.laptops[1] if self.topology.laptops[1].node_id != route.relays[0] else self.topology.laptops[2]
        wrong.receive(envelope)
        wrong.receive(bytes(492))
        self.assertEqual(wrong.counters['rejected'], 2)
        self.assertEqual(self.topology.totals('delivered'), 0)

    def test_relay_without_a_link_to_the_next_hop_cannot_forward(self):
        simulation = MeshSimulation()
        nodes = [simulation.add_node() for _ in range(5)]
        for a, b in zip(nodes, nodes[1:]):
            simulation.connect(a, b)
        route = simulation.find_route(nodes[0], nodes[4])
        simulation.connect(nodes[0], nodes[2])
        broken = Route((nodes[1].node_id, nodes[3].node_id, nodes[2].node_id), nodes[4].node_id)
        self.assertTrue(nodes[0].send(broken, PrivateMessage('x', NOW + 60)))
        self.assertEqual(nodes[1].counters['undeliverable'], 1)
        self.assertEqual(nodes[4].inbox, [])
        self.assertEqual(route.relays, tuple(n.node_id for n in nodes[1:4]))


if __name__ == '__main__':
    unittest.main()
