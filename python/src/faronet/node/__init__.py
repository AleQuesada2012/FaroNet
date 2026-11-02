"""Mesh node foundation (proposal 0002): identities, envelopes and simulation.

identity: PyNaCl keys, node IDs and signed directory entries.
fragment: one fixed-size envelope across six 86-byte Faro payloads.
envelope: three-relay onion layers and padded private messages.
mesh:     laptop simulation joining Nodes through in-memory or optical links.
lan:      TCP links with fixed 493-byte records, link proofs and gossip.
chat:     the private terminal chat and relay-only Node commands; with
          --faro-peer a Faro link through faronet.faro.bridge.
"""
