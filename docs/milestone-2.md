# Second software slice (Teammate B): mesh node foundation

Status: implemented and locally verified on 2026-10-22; the contract it
follows, [proposal 0002](rfc/0002-mesh-envelope-proposal.md), is PROPOSED,
not accepted. Review it with Teammate A and the owner; its constants can
still change. Changes remain uncommitted.

## What is implemented

| Component | Entry point | Behavior |
| --- | --- | --- |
| Identities and signed directory | `python/src/faronet/node/identity.py` | Ed25519/X25519 keys, derived 16-byte node IDs, 190-byte canonical signed entries, lifetime/clock rules, newest-entry directory |
| Fragmentation | `python/src/faronet/node/fragment.py` | 492-byte envelope to six 86-byte Faro payloads; bounded, duplicate-tolerant reassembly per neighbor |
| Onion envelopes | `python/src/faronet/node/envelope.py` | Three SealedBox relay layers, Box end-to-end layer, 190-byte padded message, strict peeling |
| Mesh simulation | `python/src/faronet/node/mesh.py` | Nodes, in-memory links, the optical link from milestone 1, source routing over adjacency, anonymous counters |
| Shared examples | `fixtures/directory-v1.json`, `fixtures/mesh-fragment-v1.json` | Deterministic signed entry and fragment layout for Rust/Python interoperability |
| Demo | `python -m faronet mesh-demo` | Pi-3 Node to a laptop Node through three relays, first hop over the simulated optical link, then a reply |

The only new runtime dependency is `pynacl==1.6.2`, declared in
`python/pyproject.toml`. The optical modules from milestone 1 are unchanged;
the node slice consumes their payload budget and simulated adapter.

## Run it

From `python/`, with its virtual environment active and reinstalled so
PyNaCl is present:

```bash
python -m pip install -r requirements.txt
python -m faronet mesh-demo
python -m unittest discover -s tests -v
```

The demo prints anonymous counters only: accepted first hop, relay count,
total relays and deliveries, optical envelopes/frames and virtual half-bit
units. It never prints node IDs, keys or message text.

## Verification completed

| Check | Result |
| --- | --- |
| Python behavior tests | 79 passed: 41 from milestone 1 plus 38 for identity/directory, fragmentation, envelopes and the mesh simulation |
| Directory fixture | Deterministic seeds reproduce node ID, keys, signed bytes, signature and entry bytes exactly; every single-bit change is rejected |
| Envelope invariants | Every hop sees 492 bytes; wrong node, wrong order, tampering, impersonation and unknown senders fail; padding changes do not |
| Mesh simulation | Delivery once through three relays with the first hop over six acknowledged optical frames; lost ACK delivers once; retry exhaustion fails until session reset; expired and replayed messages are counted, not delivered |
| Python environment | Bytecode compilation and `pip check` passed with PyNaCl 1.6.2 |

Verified on macOS with Python 3.14.7. No Raspberry Pi, no real link, no
socket transport and no Rust build were exercised. Rust toolchain was not
available on the machine used for this slice, so no Rust code was added;
the Rust directory/dead-drop work must start from the shared fixtures with
`cargo test --locked` available.

## Review together

Teammate B leads this slice; Teammate A reviews the fragment contract (it
sits on A's payload budget and adapter) and the optical link usage in the
simulation. Confirm or change the numbered decisions in proposal 0002
section 9 before the private terminal chat, LAN transport and gateway
client are built on top of it.

## What still needs the next contract

- Laptop/LAN transport for envelopes, Pi-side process layout and how a
  Node learns its neighbors.
- Directory bootstrap and replication through the gateway; Rust public
  directory verification using `fixtures/directory-v1.json`.
- Interactive terminal chat, multi-envelope messages and conversation
  state; key rotation and the achievable panic cleanup scope.
- Gateway client routes and the live HTTPS/header contract; Rust dead drop
  with fixed-size blobs and TTL; rate limiting.
