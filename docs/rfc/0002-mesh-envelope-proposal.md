# Second software slice: mesh identities, fixed-size onion envelopes

Status: PROPOSED on 2026-10-22, not yet accepted. Teammate B drafted and
implemented it as a reviewable foundation; Teammate A and the owner must
agree to it (or change its numbers) before dependent work builds on it.
ASCII-only contract draft, not the complete FaroNet RFC.

## 1. Purpose and relation to the accepted milestone

The accepted first milestone (0001) fixed the 128-byte Faro frame with an
86-byte payload and the offline gateway HMAC contract. The plan lists the
mesh route, PyNaCl primitives, keys/directory trust, fixed-size encrypted
envelopes, fragmentation and private chat as contracts that must be agreed
before their implementation slices. This document proposes the smallest
consistent set of those contracts and records what was implemented against
it in python/src/faronet/node/. Everything here runs on laptops without
sockets, GPIO or a deployed service.

## 2. Primitives (PyNaCl 1.6.2, libsodium defaults)

| Use | Primitive | PyNaCl API | Overhead |
| --- | --- | --- | ---: |
| Directory signature | Ed25519 | nacl.signing.SigningKey | 64-byte signature |
| Hop layer (anonymous) | X25519 + XSalsa20-Poly1305 | nacl.public.SealedBox | 48 bytes |
| End-to-end message | X25519 + XSalsa20-Poly1305 | nacl.public.Box | 24-byte nonce + 16-byte tag |
| Node ID | SHA-256 of the verify key, first 16 bytes | hashlib | n/a |

Each Node holds one long-term Ed25519 signing key and one long-term X25519
encryption key. Keys are generated locally and never serialized by this
slice. Node IDs are derived, never chosen, so an entry cannot claim another
node's identifier without that node's signing key.

## 3. Signed directory entry

Canonical binary record, big-endian integers, covered by the signature:

| Field | Size | Rule |
| --- | ---: | --- |
| Prefix | 20 | ASCII "FARONET-DIRECTORY-V1" |
| Node ID | 16 | SHA-256(verify key)[0:16] |
| Verify key | 32 | Ed25519 public key |
| Public key | 32 | X25519 public key |
| Issued at | 8 | Unsigned Unix seconds |
| Expires at | 8 | issued < expires <= issued + 30 days |
| Alias length | 1 | 0-16 |
| Alias | 0-16 | ASCII letters, digits, hyphen, underscore; optional |
| Signature | 64 | Ed25519 over all preceding bytes |

Verification rejects any length mismatch, unknown prefix, non-ASCII alias,
node ID that does not match the verify key, lifetime outside the rule and
any signature failure. Clock policy: an entry is usable from issued-60 s
(issuer skew) through expires, inclusive. A newer issued time replaces an
older entry for the same node ID; an older one never replaces a newer one.
Ed25519 is deterministic, so fixtures/directory-v1.json gives exact bytes
the Rust public directory can verify with the same contract.

What this does not provide: how a Node first learns which entries to trust
(bootstrap), replication through the gateway, revocation, and whether the
alias is shown in the chat. Those remain separate decisions.

## 4. Fixed-size envelope and fragmentation

The envelope is the unit forwarded between Nodes on every link. Its size
follows from the accepted Faro budget:

- Fragment payload = 86 bytes: tag (2, chosen per envelope by the sending
  neighbor), index (1, 0-5), count (1, always 6), data (82).
- ENVELOPE_SIZE = 6 x 82 = 492 bytes. Six DATA frames per envelope, each
  acknowledged under the accepted stop-and-wait rules.
- Reassembly is per incoming neighbor, keeps at most four incomplete tags,
  evicts the oldest, ignores repeated fragments and rejects any index or
  count outside this version. A complete envelope is produced once.

Sending an envelope across the simulated link costs 6 x 4,112 = 24,672
virtual half-bit units when every frame is acknowledged first time. This is
a size/latency trade-off to confirm, not a measured bitrate.

## 5. Onion layers

Exactly three relays, then the destination. Innermost first:

```text
envelope = len(c1) [2 bytes] || c1 || random padding to 492 bytes
c1 = Seal_relay1( 0x01 || id_relay2      || c2 )
c2 = Seal_relay2( 0x01 || id_relay3      || c3 )
c3 = Seal_relay3( 0x01 || id_destination || c4 )
c4 = Seal_dest  ( 0x02 || id_sender || nonce || Box_sender->dest( message ) )
```

Per-layer costs: relay layer 48 + 17 = 65 bytes; delivery layer
48 + 17 + 40 = 105 bytes. Ciphertext lengths seen by hop 1..4 are therefore
490, 425, 360 and 295 bytes; every envelope on every link is 492 bytes.

A relay peels its layer, reads the next hop, re-pads the inner ciphertext
with fresh random bytes to 492 and forwards. It cannot read any inner layer
and does not learn the sender or destination unless it is adjacent to them.
The destination opens the delivery layer, looks the sender up in its
directory and authenticates the message with Box. A relay or destination
that cannot open its layer counts a rejection and forwards nothing.

Route rules: three distinct relays, distinct from the sender and the
destination; the sender must never appear in its own route. In this slice
routes are chosen by the sender from known adjacency (source routing).
"Negotiated" paths with per-hop session keys would need a circuit-setup
protocol; that is a later decision and is not claimed here.

## 6. Padded private message (190 bytes)

MESSAGE_SIZE = 492 - 2 - 3 x 65 - 105 = 190 bytes, before Box.

| Field | Size | Rule |
| --- | ---: | --- |
| Version | 1 | 1 |
| Kind | 1 | 1 = TEXT |
| Expires at | 8 | Unsigned Unix seconds, set by the sender |
| Text length | 2 | 0-178 |
| Text | <= 178 | UTF-8; longer text fails explicitly, never truncated |
| Padding | rest | Zero bytes, verified on decode |

The destination discards messages whose expiry has passed and suppresses a
repeated Box nonce (bounded set of 1,024). Relays cannot see the expiry.
One message is one envelope; multi-envelope messages are a later decision.

## 7. Simulation scope

python/src/faronet/node/mesh.py joins Nodes with two link kinds: an instant
in-memory link standing in for the future laptop/LAN transport, and the
first-milestone simulated optical link, which really carries six Manchester
coded frames per envelope with the accepted retry/duplicate rules. A single
verified Directory stands in for every Node's replica. Delivery evidence
comes from the simulator's receiver acceptances, so a lost final ACK still
delivers once while the sender retries, and exhausted retries fail the
envelope explicitly until the controller resets the session.

Nothing here opens sockets, threads, GPIO or wall-clock timers.

## 8. Privacy and security considerations for this slice

- No single relay sees both endpoints. Relay 1 sees the sender as previous
  hop; relay 3 sees the destination as next hop. The shrinking ciphertext
  length tells each relay its position, the same knowledge Tor guards and
  exits have. Collusion of relay 1 and relay 3, or timing correlation on a
  quiet mesh, can still link the endpoints. No cover traffic exists.
- Box uses long-term keys: no forward secrecy. Compromise of a long-term
  key exposes past messages that an observer recorded. A per-conversation
  ephemeral exchange is a candidate follow-up.
- The sender's identity is inside the delivery layer, encrypted to the
  destination only. Relays see neighbor node IDs, 492-byte sizes and timing.
  On the optical link, the first-milestone local addresses and fragment
  tags are visible to anyone watching the light.
- CRC and the Faro ACK remain link mechanisms; integrity against forgery
  comes from Poly1305 in each layer and Box authentication at the end.
- Errors are static strings. Counters are anonymous. Message text exists
  only in the destination's in-memory inbox object. Python cannot promise
  that every RAM copy of a key or message is overwritten; panic cleanup
  scope is still a separate decision.

## 9. Decisions this proposal asks the team to confirm or change

1. ENVELOPE_SIZE 492 (six frames) versus a larger size with more latency.
2. Exactly three relays per path versus "at least three hops" counting the
   destination link.
3. Source routing from a signed directory in this project versus a
   negotiated circuit protocol.
4. Long-term Box for end-to-end versus adding ephemeral keys.
5. Whether the alias is kept, and how directory bootstrap/replication works
   through the gateway and the Rust public directory.
6. The laptop/LAN transport (plain TCP framing of 492-byte envelopes is the
   simplest candidate, since onion layers provide confidentiality).
7. Relay-visible TTL (not included: it would leak path position/age).

## 10. Reference facts

- PyNaCl public-key encryption, sealed boxes and signing:
  https://pynacl.readthedocs.io/en/latest/public/
  https://pynacl.readthedocs.io/en/latest/signing/
- libsodium sealed box construction (ephemeral key + box, 48 bytes):
  https://doc.libsodium.org/public-key_cryptography/sealed_boxes
- Onion routing background and the position/collusion model:
  https://spec.torproject.org/tor-spec/
- Privacy considerations guidance for the final RFC: RFC 6973.
