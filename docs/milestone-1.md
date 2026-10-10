# First software milestone

Status: implemented and locally verified on 2026-10-09, awaiting owner review.
The owner accepted Q16-Q20 and authorized implementation.
The [accepted contract](rfc/0001-first-milestone-proposal.md) defines the
parameters; [the work plan](development-plan.md) records the provisional
division, time envelopes and checkpoints. Changes remain uncommitted.

## What is implemented

| Component | Entry point | Behavior |
| --- | --- | --- |
| Python frame codec | `python/src/faronet/dispositivo_luz_adaptador/frame.py` | Exact 128-byte serialization, 86-byte payload budget, strict fields/padding and CRC-32/ISO-HDLC |
| Manchester codec | `python/src/faronet/dispositivo_luz_adaptador/manchester.py` | MSB-first binary light levels, 0=OFF/ON, 1=ON/OFF, known-clock decoding |
| Simulated adapter | `python/src/faronet/dispositivo_luz_adaptador/simulation.py` | Two neighbors, scripted turns, external frames, ACK matching, three attempts, duplicate suppression and explicit reset after exhausted retries |
| Python gateway helpers | `python/src/faronet/gateway/auth.py` | Versioned canonical input, exact-body SHA-256, HMAC-SHA-256, strict syntax, configured scope, freshness and nonce admission |
| Rust gateway helpers | `rust/src/gateway_auth.rs` | Matching contract using RustCrypto; testable on the laptop and compiled for WASM |
| Shared examples | `fixtures/optical-v1.json`, `fixtures/gateway-auth-v1.json` | Fixed synthetic golden vectors; public fake keys, IDs and bodies only |

Each waveform level lasts one virtual half-bit unit: a complete frame lasts
2,048 units. A clean DATA/ACK exchange lasts 4,112 units; a timed-out attempt
lasts 6,144. These values have no wall-clock bitrate meaning.

Loss of every ACK can produce `acknowledged=False` with one receiver
acceptance. The sender cannot conclude that its message was never received.
After exhausted retries, the controller must explicitly choose a new session
before further exchanges; stale sessions cannot complete the new transfer.

Replay tests use explicit fake stores, injected clocks and synthetic secrets.
They recheck time during admission and retain accepted nonces through the
request's final valid second, including future-dated requests. Storage
failure rejects admission. No fake store is wired into a Worker handler.

## Run it

From `python/`, with its virtual environment active:

```bash
python -m faronet simulate
python -m faronet simulate --scenario lost-ack
python -m faronet auth-demo
python -m unittest discover -s tests -v
```

The simulator's default command runs clean, lost DATA, corrupt DATA, lost ACK,
duplicate DATA, stale ACK and retry-exhaustion scenarios. Successful scenarios
also exchange a reply after the controller grants the other neighbor's turn.
Output contains scenario names and anonymous counters, not message bodies,
addresses, nonces or authentication secrets.

From `rust/`:

```bash
cargo test --locked
npm run check
npm run dry-run
```

The native Rust tests and Python tests consume the same authentication
fixtures. Rustfmt/Clippy and packaging additionally verify Worker-target
compatibility. The existing `/health` and `/` behavior remains the local
Worker entry point; there are no authenticated relay endpoints yet.

## Review together

Teammate A leads the optical Python module and reviews Rust authentication.
Teammate B leads Python signing/Rust validation and reviews the optical module.
Both run the demonstrations/tests, review fixtures and record actual human
effort before rebalancing. A's public rooms/feed Rust implementation follows
this foundation; the overall approved division still gives both people
meaningful work in both languages.

## Verification completed

| Check | Result |
| --- | --- |
| Python behavior tests | 41 passed; fixed frame vectors, Manchester, loss/retry/reset and authentication/replay cases |
| Rust behavior tests | 14 passed; same signing vectors, malformed/tampered requests, time boundaries and fake-store failures |
| Independent HMAC fixture check | All four fixture signatures also match OpenSSL |
| Python demonstrations | All seven optical scenarios and fake authentication/replay demo passed |
| Python environment | Bytecode compilation and dependency check passed |
| Rust quality | Formatting and Clippy passed for WASM and native code/tests with warnings treated as errors |
| Worker release/package | Release build and Wrangler dry run passed; no bindings or deployment |
| Fresh local Worker | GET `/health` and `/` returned 200; unknown path, POST `/health` and POST `/v1/relay` returned 404 |
| Documentation | Local links, whitespace and ASCII RFC checks passed |

Verified using Python 3.14.7, Rust 1.99.0, worker/worker-build 0.8.7 and
Wrangler 4.149.0. The pre-existing local Wrangler manifest/lockfile edits were
preserved. The usual development port was occupied; runtime checks used a
separate instance on localhost port 8797, then stopped it. The existing
server was left running.

These are local software checks. No Raspberry Pi, actual laser/comparator,
real-time GPIO behavior or deployed Durable Object was verified.

## What still needs the next contract

- Real receiver/emitter profile, pin-role assignments and Python GPIO line I/O;
  actual timing, clock recovery, optical measurements and physical panic.
  Subsequent environment discovery identified the controller and settled
  the backend/numbering; see [the Pi profile](../hardware/pi-environment.md).
- Decentralized turn negotiation, address/session lifecycle and fragmentation.
- Mesh routes, PyNaCl primitives, keys/directory trust, fixed-size encrypted
  envelopes, private terminal chat, TTL and achievable panic cleanup.
- Live HTTPS/header/operation contract, atomic Durable Object admission,
  idempotency, rate limits, public rooms/browser WebSockets/feeds, dead drop
  and signed directory replica.

These remain required project work, except the already deferred LCD and
speaker/buzzer enhancements. The first milestone added no hardware package;
the subsequent accepted GPIO extra is documented in the Pi profile. No real
secret, CI workflow, license, provider binding, remote resource or deployment
was added here.
