"""Mesh node foundation (proposal 0002): identities, envelopes and simulation.

identity: PyNaCl keys, node IDs and signed directory entries.
fragment: one fixed-size envelope across six 86-byte Faro payloads.
envelope: three-relay onion layers and padded private messages.
mesh:     laptop simulation joining Nodes through in-memory or optical links.

The real LAN transport, interactive terminal chat, directory replication,
TTL enforcement by relays and panic cleanup remain later slices.
"""
