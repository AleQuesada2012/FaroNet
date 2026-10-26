# Development plan

Updated 2026-10-25. Confirmed constraints are distinguished from proposals.
Source decisions remain in [decisions.md](decisions.md).

## Immediate Student A priority: Oct 26 optical meeting

The Oct 25 slice implements the current breadboard GPIO profile, libgpiod
v2 transmission and timestamped-edge reception, manual sender/listener
turns, matching ACKs, bounded retries, duplicate suppression, indicators
and panic stop. [The meeting guide](optical-bringup.md) provides setup,
synthetic two-direction tests, recovery and measurement recording.
Pre-publication Pi-3 validation used a separate copy; normal setup on both
Pis uses their existing repository clones after owner review/commit/push,
with each Pi's own `python/.venv`. Physical tests wait until the boards are
connected at the meeting.
Student B's Pi 2 runs PiOS, while A's Pi 3 runs Ubuntu installed with
balenaEtcher and has a proper 5 V/2.5 A supply. Worker work stays entirely
on the Mac: opt-in public browser rooms/WebSockets are locally implemented,
without deployment or live gateway integration. Autonomous turns, physical
qualification, full panic integration and private terminal/LAN transport
remain required follow-up work. The earlier checkpoints below are historical
targets, not evidence that their hardware checks happened.

## Confirmed constraints

- Delivery date: 2026-10-29, Costa Rica time; exact submission time pending.
- Two people, approximately 10 hours per week each starting 2026-10-09.
  This is roughly 29-30 hours each, 58-60 person-hours total through delivery.
- Both are strong in Python, new to Rust, and beginners at networking. The
  owner has some simple circuit design/build/soldering experience.
- Both must implement meaningful Python and Rust portions.
- Software-first optical simulation is approved. The inspected Pi 3's
  environment is Ubuntu Server 26.04.1 LTS/ARM64, kernel `7.0.0-1020-raspi`,
  Python 3.14.4; real hardware tests remain pending.
- Boards, updated 2026-10-22: one Raspberry Pi 3 Model B rev 1.2 and one
  Raspberry Pi 2 Model B v1.1, no longer two Pi 3 units. The Pi 2 B v1.1
  (BCM2836, ARMv7) is 32-bit only, has no onboard Wi-Fi/Bluetooth and shares
  the same 40-pin header and BCM numbering. The 64-bit image used on the
  Pi 3 cannot boot on it; it now runs PiOS. Its exact release, Python version,
  PyNaCl/gpiod availability and network access (Ethernet or USB adapter) must be
  confirmed before planning Pi-side tests. The breadboard layout already
  covers both boards.
- Each Pi can host its Node and Faro control; one also hosts the Gateway.
  Proposal: the Pi 3 hosts the Gateway because it has onboard Wi-Fi and a
  verified environment; confirm. Laptop processes can supply additional
  mesh participants.
- Private application: terminal chat. Hardware indicators: TX, RX, RGB, plus
  the physical panic control. LCD and speaker/buzzer are enhancements after
  the assignment minimum is complete; LCD assists rather than replaces chat.
- Assume laser acceptance for planning, with a matched IR fallback if needed.
- Commit/push ownership and deferred CI/licensing remain as previously agreed.

## Approved provisional ownership

Teammate A is the person with circuit experience. Teammate B is the other
person. These labels do not assign names or accounts. The owner accepted this
division in Q8 on 2026-10-09; rebalance it after the first working milestone.

| Area | Teammate A leads | Teammate B leads |
| --- | --- | --- |
| Python | Optical framing, simulated/real Faro adapter, TX/RX/RGB and panic integration, link measurements | Mesh/routing, private terminal chat, encryption/padding, signed directory, gateway client |
| Rust | Public rooms, browser/WebSocket interface, topic feed | Gateway authentication/replay protection, encrypted dead drop, public directory |
| Shared | Protocol/security contracts, hardware bring-up with B, integration, rate limiting, review, RFC/documentation/demo | Same; pair on optical tests and review A's modules |

Module ownership means implementation and evidence, including tests. Both
must be able to run both environments. Share protocol contracts and fixtures;
review across languages rather than treating the two folders as separate
projects. Agree on contracts before parallel feature implementation.

## Accepted provisional human-time envelopes

Accepted in Q19 on 2026-10-09. These are allocation targets, not task estimates or a promise that the whole
assignment fits. AI-assisted coding still needs human review and real tests.

| Activity | A hours | B hours |
| --- | ---: | ---: |
| Hardware/procurement/bring-up | 8 | 2 |
| Python implementation | 5 | 8 |
| Rust implementation | 5 | 8 |
| Learning and shared design/contracts | 3 | 3 |
| RFC/documentation/demo | 3 | 3 |
| Integration, review, fixes and reserve | 5 | 5 |
| Total | 29 | 29 |

Re-estimate after the first working milestone using actual human hours.
Rebalance tasks within these totals; do not silently defer mandatory features
to the enhancement iteration. Only LCD/speaker/buzzer are currently deferred
on that basis.

## Accepted provisional checkpoints

| Date | Checkpoint |
| --- | --- |
| Oct 12 | Laptop-only optical codec/adapter simulation and a small Rust relay-contract/authentication slice with meaningful tests |
| Oct 16 | Visible transmitter/receiver prototype checkpoint; assess an IR switch if the laser is unavailable or unusable and a matched IR pair can be obtained |
| Oct 21 | Optical smoke test and synthetic application-to-edge integration; assess every mandatory requirement |
| Oct 25 | Feature freeze; concentrate remaining effort on required gaps, fixes and validation |
| Oct 26-28 | Hardware evidence, three-distance measurements, privacy checks, RFC/PDF, repeatable demonstration |
| Oct 29 | Delivery |

As of Oct 9, the team has no emitter, receiver or comparator. It plans to
acquire those on Oct 10, draft the order for the remaining parts on Oct 10,
and expects those remaining parts around Oct 13. These are plans and arrival
estimates, not confirmed purchases or shipping dates. IR fallback availability
is still unknown. The provisional Oct 16 checkpoint must not assume that an IR
replacement is already available.

The first milestone requires an agreed frame and relay contract. A simulator
should eventually exercise encoded optical transitions, not just copy already
decoded frames. It cannot verify actual laser modulation, comparator output,
GPIO timing, receiver alignment, ambient-light behavior, BER, or bitrate.

## Accepted software direction

- OOK with Manchester coding; fixed 128-byte serialized Faro frames before
  Manchester, including preamble/sync, headers, payload, padding and CRC.
- Standard CRC-32 for accidental link errors; CRC is not authentication.
- Half-duplex turn-taking, one outstanding data frame, acknowledgments,
  bounded retries and duplicate suppression.
- HTTPS gateway relay with HMAC-SHA-256 binding the request context and body,
  plus timestamp/nonce replay protection. Public browser rooms use WebSockets.
- PyNaCl for Python cryptography, with exact primitives still pending.
- One-to-one private terminal chat initially; public topic rooms at the edge.
- Negotiated onion paths with at least three mesh hops, including laptop Nodes
  alongside the Pis. Simulated hosts do not establish independent trust.

The owner accepted these directions in Q10-Q15 on 2026-10-09. Exact frame
fields, retry/expiry bounds, signing contract, route trust, key lifecycle and
recovery rules remain distinct decisions.

Reference facts use [Microchip's coding explanation](https://onlinedocs.microchip.com/oxy/GUID-06C36746-0136-4691-8940-69BFD41FCC56-en-US-1/GUID-C6B1F8E9-2BD6-49DC-9678-4B43E6FF46D1.html),
[NIST's CRC definition](https://csrc.nist.gov/glossary/term/cyclic_redundancy_check),
[Cloudflare's signing example](https://developers.cloudflare.com/workers/examples/signing-requests/),
and [PyNaCl documentation](https://pynacl.readthedocs.io/en/latest/).
Manchester's two symbols per bit affect symbol rate, not the frame's byte
budget. Real-time bit intervals remain hardware-dependent. CRC is not
cryptographic authentication. HMAC makes the gateway and Worker share an
authentication secret; Ed25519 is the alternative if the verifier should
hold only a public key.

## First implementation milestone: locally complete, awaiting review

Follow [the accepted first-milestone contract](rfc/0001-first-milestone-proposal.md)
accepted in Q16-Q20 on 2026-10-09. It specifies an optical codec and waveform simulator,
plus shared Python/Rust gateway-authentication fixtures and offline replay
policy tests. This is a foundation for the remaining mandatory features,
not a demonstration that the assignment is complete.

Implemented and locally verified on Oct 9 ahead of the Oct 12 checkpoint.
See [the milestone guide](milestone-1.md) for entry points, commands and
validation evidence. Human review, actual effort and later integration can
still change the plan; no commits or publication occurred.

For this milestone A leads the Python optical codec and reviews the Rust
authentication module; B leads the Python signing helper and Rust validator
and reviews the optical code. A's Rust public rooms/feed work follows this
foundation. Both review shared vectors and account for their actual time.

The inspected Ubuntu/kernel/Python is recorded in
[the Pi profile](../hardware/pi-environment.md). The owner accepted the
libgpiod v2 Python backend and BCM numbering after successful controller
metadata checks. The current breadboard profile supplies pin roles; A's
binding installation and metadata are verified. Physical line I/O, receiver
operation and measured bitrate still need validation.
Turn bootstrap/recovery, real replay-state storage, TTL/panic behavior,
dead-drop semantics and public services must be agreed before their
respective implementation slices.

## Second slice (Teammate B): proposed contract, implemented for review

On 2026-10-22 Teammate B drafted [proposal 0002](rfc/0002-mesh-envelope-proposal.md)
covering PyNaCl primitives, 16-byte node IDs, signed directory entries,
fragmentation of a 492-byte envelope into six Faro frames, three-relay onion
layers and a 190-byte padded private message, and implemented it in
`python/src/faronet/node/` with a laptop mesh simulation that reuses the
milestone-1 optical link. See [the slice guide](milestone-2.md) for entry
points, commands and the 79-test evidence. The proposal is not accepted:
its numbered decisions need A's and the owner's confirmation before the LAN
transport, terminal chat, gateway client and Rust directory/dead drop build
on it. No Rust was added because no Rust toolchain was available on the
machine used; the shared directory fixture is ready for that work.

Checkpoint note: the Oct 21 optical smoke test depends on hardware that is
still being assembled per the breadboard guide; the Oct 25 feature freeze
stands. Record actual human hours for this slice before rebalancing.
