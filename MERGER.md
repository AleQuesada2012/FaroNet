# Student A continuation log — 2026-10-25, Costa Rica

## Boundaries and starting state

- Read the supplied Oct 9 handoff and current repository/hardware guidance.
  No applicable `AGENTS.md` exists in this checkout or its ancestor folders.
- Refreshed origin; local and remote main both start at
  `a6518cf32d81bd575e8fdc5c1f46366db170dde5` (An-Gi, Oct 22,
  “Basic implementation for sending messages”). The checkout was clean.
- Created local branch `codex/student-a-optical-baseline` from that commit.
  No commits, pushes, deployments or provider account/resource changes.
- B's latest commit adds signed identities/directory, PyNaCl envelopes,
  six-frame fragmentation and a simulated mesh, with 79 existing tests.
  It does not add real GPIO/LAN/chat or Rust. RFC 0002 remains proposed.
- Owner corrected the environment: A's Pi 3 uses Ubuntu/direct image plus
  balenaEtcher and now has 5 V/2.5 A power. B's Pi 2 uses PiOS/Imager.
  The assembled circuit is disconnected until the Oct 26 meeting.
- All Worker code, toolchains, builds, runtime and browser tests stay on
  the Mac. Only Python, fixtures, tests and hardware references go to Pis.
- Current circuit authority is the revision-6 breadboard guide/HTML/SVGs,
  especially the common-cathode active-high RGB replacing old LS125 wiring.

## Implementation

1. Added the current eight-role BCM/physical pin profile with a test against
   `hardware/breadboard/circuit-reference.json`. SPI GPIO7–11 and ID0/1
   are not selected. Metadata preflight never requests or drives lines.
2. Added optional libgpiod v2 physical I/O: exclusive line ownership,
   initial LOW outputs, kernel monotonic edge timestamps, idle/preamble
   acquisition, bounded capture buffers, CRC/Manchester validation, event
   sequence-gap detection, absolute TX deadlines and timing failure stop.
   Acquisition uses the configured clock; continuous drift tracking is absent.
3. Added physical `send_frame`/`send`/`receive` boundary with the accepted
   v1 frame, matching ACKs, three attempts, exact-retry re-ACK and unique
   delivery, explicit session failure and cleanup. Humans choose sender and
   listener; autonomous turn negotiation is still pending.
4. Added profile/preflight, input monitor, fresh-session generator and
   synthetic send/listen CLI commands. Physical commands require explicit
   readiness confirmation. TX/RX indicators, opt-in revision-6 RGB and
   latched physical panic stop are implemented. No private chat text/logs.
   Cleanup drops references; it does not promise secure Python RAM erasure
   or key cleanup in another Node process.
5. Added local opt-in Rust public rooms: canonical room routing, one
   hibernating DO per room, same-origin upgrade validation, text-only
   bounded broadcasts, per-socket message limits, room connection cap and
   a browser page using textContent. No message-history storage. Only rate
   window/count is attached to each socket. Default flag stays false.
   Gateway auth/replay, feeds, dead drop and public directory remain separate.
6. Added a real local-runtime WebSocket test client (`ws` 8.21.0, pinned
   dev dependency already resolved in the prior lockfile), native Rust
   policy tests, browser verification, updated environment/ownership docs,
   and `docs/optical-bringup.md` with exact two-direction meeting commands.
7. Added `scripts/package_pi_baseline.py`, producing a Python-only handoff
   with tests, fixtures and breadboard references. No venv, secrets, bytecode,
   Git metadata or Rust files are included; the archive manifest was checked.

## Pi preparation and recovery evidence

- Initial SSH `BatchMode` authentication failed because this account uses
  a password. After the owner supplied the account/login details, interactive
  SSH succeeded. No credential was placed in source, shell arguments or docs.
- Live Pi: Raspberry Pi 3 Model B rev 1.2, Ubuntu Server 26.04.1,
  `aarch64`, Python 3.14.4. Existing `/home/ubuntu/FaroNet` remains clean.
- Created isolated `/home/ubuntu/faronet-baseline-20261025`, with a fresh
  `.venv` under its `python/`. Installed pinned PyNaCl 1.6.2 and gpiod 2.5.0
  using ARM64 wheels, plus their declared dependencies.
- Current `ubuntu` account lacks direct GPIO permission. Standalone
  gpiodetect/gpioinfo are not installed in PATH. The pinned Python binding's
  metadata preflight succeeds using existing passwordless sudo. No group,
  ACL, SPI or device permission change was made.
- Metadata confirms chip0/pinctrl-bcm2835, all eight assigned GPIOs unclaimed.
  No `request_lines` call or physical drive/capture was executed on the Pi.
- A new timestamped-wire integration test initially depended on tight host
  thread deadlines and failed on the slower Pi. Replaced that test harness
  with synchronous virtual edge delivery, keeping actual adapter ACK/retry
  logic and both directions. This avoids testing host scheduling as though
  it were the synthetic wire clock. Final suite passes on both hosts.
- Run Python installation commands from `python/` and Cargo/npm from `rust/`.
  The root shell's default Rust is older than the project's pinned 1.99.0;
  the correct directory selects the declared toolchain automatically.

## Final validation

| Target | Check | Result |
| --- | --- | --- |
| Mac Python | `python/.venv/bin/python -m unittest discover -s python/tests -q` | 100 passed |
| Pi Python | `.venv/bin/python -m unittest discover -s tests -q` | 100 passed |
| Both Python environments | compileall and pip check | Passed |
| Pi software demo | `python -m faronet mesh-demo` | Forward/reply through simulated optical hop and three relays |
| Pi metadata | `sudo .venv/bin/python -m faronet gpio-preflight` | Expected controller/pins; no line requests |
| Rust on Mac | `cargo test --locked` | 17 passed (14 existing auth, 3 public room policy) |
| Rust/WASM on Mac | `npm run check` | rustfmt/Clippy passed |
| Worker package on Mac | `npm run dry-run` | WASM build/optimization and Wrangler packaging passed; no deployment |
| Worker runtime on Mac | `npm run test:rooms` | Relay, room isolation, origins, text/binary/size/rate/connection limits, capacity recovery and reconnect passed |
| Default Worker on Mac | HTTP checks on temporary port 8790 | Rooms/JS/ws 404, health 200; temporary server stopped |
| Browser on Mac | Connect/send synthetic text | Rendered message and connected state verified; preview saved |
| Git | `git diff --check` | Passed; work remains uncommitted |

Worker demo was left running locally on `127.0.0.1:8787` for inspection
(`npm run dev:rooms`; this turn's terminal session 99665). It uses local
bindings only; default configuration still disables room routes. Screenshot:
`output/public-rooms-preview.png`.

Pi handoff archive: `output/faronet-pi-baseline-2026-10-25.tar.gz`.
It contains 50 files and is 601256 bytes in this snapshot. SHA-256:
`5332d04359e5ef386e87fb145bf3357be9c3a168ef2047ff3ee6fb769784c67a`.
Rebuilding may change gzip/tar metadata and therefore the digest.

## Next action at the meeting

Use `docs/optical-bringup.md`: qualify signal levels and button wiring,
connect with power off, inspect B's PiOS/Python/gpiochip environment,
monitor both receivers, then run three synthetic frames A→B and B→A with
fresh sessions. Start at 5 ms half-bits; slow both boards if timing fails.
Measure at three distances and record failures as well as accepted payload
errors and throughput. No real optical success, raw BER, live panic result,
Pi-2 compatibility, autonomous turns or full private-chat deployment is
claimed by today's software tests.

## Follow-up: use the Pis' existing clones

The owner clarified that both Pis already cloned the repository. The normal
source distribution path is now explicit: owner review/commit/push under
the existing contribution contract, then a clean-checkout Git fast-forward
to the same published commit on each Pi. No commit/push was authorized or
performed by this clarification; all implementation files, tests and guides
remain in the Mac repository branch for the owner's review.

Updated the optical guide, Python/development/root guides and Pi profile to
start from the existing clones, preserve local work, reuse each Pi's own
`python/.venv` and create it only if missing. Requirement installation and
Python checks run there. Worker tooling/builds/tests stay on the Mac.
The isolated Pi copy above remains historical validation evidence; the
existing Pi checkout has not been updated with uncommitted source.
The archive generator is an optional offline-review fallback, not the
normal Pi setup/update path. Its earlier size/digest describe the prior
snapshot; the regenerated artifact has updated guides. No hardware I/O
or environment changes were needed for this documentation correction.

## Publication authorized after owner review

On Oct 25 the owner reviewed the changes and explicitly requested making
them available on `main` and pushing to the remote. This authorizes this
commit/push and supersedes the earlier review hold for this slice; it does
not change the ongoing requirement for owner review of future work.

Publication target: `origin/main` in
`https://github.com/AleQuesada2012/FaroNet.git`. Prepare one implementation
commit on `codex/student-a-optical-baseline`, fast-forward local `main`, and
push `main` normally, preserving existing remote history. The source base
is `a6518cf32d81bd575e8fdc5c1f46366db170dde5`; the publication commit can be
identified by `git log --oneline --grep='Add Student A optical baseline and local public rooms'`.
Final checks include the staged diff, remote-tip refresh and equality of
local `main` with `origin/main` after pushing. Existing Python/Rust/runtime
validation is recorded above; subsequent changes only adjust documentation
and archive packaging. No deployment or Pi checkout update is part of this
publication request. Both Pis update their existing clones using the guide.

## Follow-up: both assembled breadboard variants

The owner reaffirmed `hardware/breadboard/` as the current circuit authority
and clarified that RGB is optional debugging; patterns may be chosen later.
Started from published main `de0ccc417f6de8a8c72549ac2b2604d2062a5aea` on
local branch `codex/optional-breadboard-rgb`.

Audit: optical TX/RX, indicators, panic, and active-high common-cathode RGB
mapping already match the breadboard reference. Runtime RGB outputs were
already opt-in, but metadata preflight inspected all eight GPIOs, so occupied
optional pins could incorrectly fail a basic-board check. Added shared basic
and RGB pin selection to both preflight and the driver, with `--rgb` on
preflight. Default checks five core GPIOs and leaves BCM5/6/13 untouched;
RGB mode adds those three outputs. A basic board and an RGB board may be
peers without changing the wire protocol. Existing colors are provisional
debug output and have no protocol role. No breadboard wiring was changed.

Regression checks compare each software profile with the corresponding
`layout-data.json` header wiring, exercise a basic-board transmission and
cleanup with RGB lines already owned, and verify preflight only rejects
those optional claims when RGB is explicitly selected. Python suite: 102
passed on the Mac. Both profile-only CLI variants were checked without
opening GPIO. No physical test or Pi-side change was performed for this
follow-up.

The owner subsequently reviewed this follow-up and explicitly authorized
making it available on `main` as well. Publication target: `origin/main`,
using a normal fast-forward from `codex/optional-breadboard-rgb` and push.
The commit title is `Support both basic and optional RGB breadboard profiles`.
The 102-test validation above covers the published code; final publication
checks are the staged diff and equality of local and remote `main` after
pushing. Both Pis obtain it through their existing clones. This publication
does not perform hardware tests, modify either Pi or deploy the Worker.

## Follow-up: RV1 calibration telemetry command

Started from published main `e1007e092c324b6d10e8cf57426dba608698f7fb`
(revision 7). User-reported bench state on A's Pi 3 with the rev-7 board and
all eight header wires connected: `gpio-preflight` matched
`pinctrl-bcm2835` with all five lines unclaimed; `gpio-monitor` held
`light` at 1 with only monitor light or a covering hand; the panic button
stopped the monitor. No analog voltages were reported for this state.

Added `gpio-calibrate`, a persistent replacement for a pasted one-off
script. It claims the same five-line request as the monitor, samples
OPT_RX every 2 ms and prints one JSON line per 0.5 s with level, percentage
HIGH, a bar and RX edges per second; the yellow indicator mirrors RX.
`--blink` toggles TX and green every second and reports how often RX
matched IR, for a reflector held over D1 and Q2. `--seconds` defaults to
120. Panic (including a latched short press), Ctrl+C and normal completion
leave every output LOW and release the request. The backend gained
`sample_rx()` (edge count without decoding) and a public `set_output()`.

Fake-gpiod tests cover blink reports with a simulated reflector, IR staying
off without `--blink`, the panic stop, cleanup and the CLI readiness flag.
Python suite: 104 passed on the Mac. The command has not run on physical
GPIO; RV1 calibration, receiver voltages and optical ACK remain pending.
The owner authorized pushing this follow-up directly to `origin/main`.


## Bench follow-up: receiver power/ground faults and revision 7a

User-reported, Faro A, Pi powered, black probe on GND, before any fix:
U1 pin 8 ≈2.2–2.3 V (expected ~5 V), U1 pin 4 ≈0.7–0.8 V (expected 0 V),
VBIAS at e48 ≈2.7 V (expected ~2.1 V), Q2 emitter 0 V, VTH at e41
≈0.003 V (RV1 turned to its GND end), OPT_RX ≈0 V. `gpio-calibrate`
`--blink` lit D1, but RX never reported light. The SENSE readings
(b52 vs d63) were ambiguous and are not carried forward.

Found with power off and corrected by the owner: W20 (b49 ↔ b51,
R6 hysteresis) and W16 (d50 → TG:40, U1 pin 4 to GND) were missing.
Continuity from R9's rail end (BG:41) to the top GND rail was
intermittent through W04 at TG:4 ↔ BG:4; the wire itself tested good.
Added a second GND bridge TG:21 ↔ BG:21 and kept W04 (revision 7a,
recorded in `hardware/breadboard/README.md`; generated plan/HTML not
regenerated). Netlist and values are unchanged. The owner reports all
other continuity checks pass. Powered re-measurement of U1 pins 8/4,
VBIAS, SENSE and VTH, meter-based RV1 setting and the Q2 IR response
remain pending.

## Bench follow-up: Faro A receiver qualified by reflection; loopback command

User-reported, Faro A, after the 7a fixes: U1 pin 8 reads 5 V along the
whole 5 V path, U1 pin 4 0 V, VBIAS 2.07 V, SENSE ≈1.51 V with Q2 only
partly covered (room light). An apparent 5 V–GND beep disappeared with
Pi pin 2 disconnected and behaved like C1 charging; not a short. RV1 was
set by the `gpio-calibrate` procedure (room-light switch point, then a few
degrees further). `gpio-calibrate --blink` with paper or a hand a few cm
over D1/Q2: `rx_matches_ir_pct` 100 in every window; with nothing in front,
`rx` stays 0. Reflection worked up to about 8–10 cm. Panic stopped the run.
Not yet reported: OPT_RX meter reading while HIGH, ambient-change check,
SENSE dark/IR values. Faro B is not ready.

Added `optical-loopback`: sends synthetic DATA frames and decodes each
frame's own reflection on the same board, reporting per-frame match and
bit errors plus rejects, overruns, TX lateness and matched payload rate.
`transmit()` gained an opt-in `loopback` mode that feeds its own edges to
the decoder instead of ignoring them, lights the RX indicator during
capture and returns the decoded echo; the default path is unchanged.
Fake-gpiod tests drive a timestamped echo: frames round-trip, a missing
reflection or lost edge fails without a delivery, outputs end LOW and the
normal transmit still discards its reflection. Python suite: 107 passed
on the Mac; no physical loopback run yet. The owner asked
for bench commands to be published to `origin/main` for Pi-side use.

## Bench follow-up: loopback rejected every capture on sequence gaps

User-reported first physical `optical-loopback` on Faro A (3 frames,
10 ms half-bit, paper over D1/Q2): no frame echoed; `event_overruns` 2267
equal to `rejected_waveforms` 2267, so every rejection came from the
gap check; TX max lateness 2.727 ms. The 1 s blink test still followed.

Cause in software: any jump in `global_seqno` called `lose_sync()`. In
Linux's GPIO cdev, edges arriving before the IRQ thread runs are merged into
one event that skips sequence numbers and reports the line's current level,
so fast comparator glitches at transitions produce gaps without corrupting
the final level. Gaps are now counted but no longer abandon a capture;
Manchester and CRC validation decide. The decoder's edge bound became
4 × FRAME_SYMBOLS for glitch room. `sample_rx()` also counts gaps;
`gpio-calibrate` reports `seq_gaps` per window and takes `--blink-ms` to
toggle IR at half-bit rates. A fake-echo test with merged events fails on
the old rule and passes now. Python suite: 109 passed on the Mac. Whether
this fixes the physical loopback, and how much the comparator chatters,
is not yet measured.

## Bench results, CSMA/CA link and new deadlines (2026-10-31)

User-reported, Faro A, after the sequence-gap fix: `optical-loopback`
at 10 ms matched 3/3 frames, 0 bit errors, 0 rejected waveforms, 2281
sequence gaps, TX max lateness 2.566 ms, 4.162 payload B/s.
`gpio-calibrate --blink --blink-ms 10`: `rx_matches_ir_pct` 100 in every
window, exactly 100 edges/s, about 24 `seq_gaps` per 0.5 s window (roughly
one per two transitions; likely a glitch on one edge direction). Loopback
at 5, 3 and 2 ms each stopped with "TX missed its timing budget".
The owner chose more comparator hysteresis (for example R6 47 kOhm instead
of 100 kOhm) for the soldered board, not the breadboard.

The owner updated the deadlines: code, BOM, documentation and RFC on
Sunday 2026-11-01 23:59:59 (Costa Rica), code frozen from Monday; the
soldered, working Faros two days later.

Medium access: the owner selected CSMA/CA, the accepted three attempts and a
first slice of MAC, simulator and CLI (proposal 0003, PROPOSED). Added
`dispositivo_luz_adaptador/medium.py` (CsmaLink state machine and a
two-Faro SimulatedMedium where overlapping light loses both frames),
`faro/link.py` and the `optical-link` command, run identically on both
Pis. `GpioFrameIO.channel()` reports carrier sense; RX is ignored for one
half-bit after our own TX; frames already decoded before a transmission
are no longer discarded. Tests: 30 seeds of simultaneous traffic with
collisions recovered, deferral and ACK priority, lost ACK, retry
exhaustion, stale frames and the driver loop against a fake peer.
Python suite: 119 passed on the Mac. No physical two-Faro run yet.

TX timing follow-up: every symbol was late by up to the sleep overshoot plus
any scheduler or garbage-collection pause (2.57 ms max at 10 ms, over the
0.4-half-bit budget at 5 ms and below). `_wait_until` now sleeps until 1 ms
before each deadline and then busy-waits; while a frame is on air the
process requests SCHED_FIFO priority 50 (effective under sudo, ignored
otherwise) and pauses Python's garbage collector, restoring both afterwards.
Each symbol still sleeps about half its time at 2 ms, which stays clear of
Linux real-time throttling. On the Mac, sleep overshoot alone reached
1.25 ms, so a Mac run cannot qualify the Pi; the 5/3/2 ms loopback must be
rerun on Faro A. Python suite: 121 passed on the Mac.

## Edge: Atom topic feeds and rate limiting (2026-10-31)

Student A's edge slice. `GET /rooms/{topic}/feed.atom` serves an Atom 1.0
feed per public topic from the topic's `PublicRoom` Durable Object, which
now stores the last 20 public messages for at most 24 hours (sequence,
minute-resolution time, text; no identity or address) and erases expired
entries with an alarm. Every route except `/health` is limited to 60
requests per client per minute through a new `EdgeLimiter` Durable Object
(SQLite class, as the free plan requires) named by a SHA-256 of
`CF-Connecting-IP` and holding its counter in memory only. The rooms page
links to its feed. Verified on the Mac: `cargo test` (23 tests), `npm run
check` (fmt, wasm32 clippy), `npm run build`, the local runtime test against
`dev:rooms` (relay, limits, feeds, escaping, ordering, 429/Retry-After),
an XML well-formedness parse of a real feed, and `npm run dry-run` showing
both Durable Object bindings. Not deployed; `PUBLIC_ROOMS_ENABLED` remains
false in versioned configuration.

Deployment prep (not deployed): `npm run deploy` and `npm run dry-run` now
pass `--var PUBLIC_ROOMS_ENABLED:true`, keeping the versioned default false
for plain local runs. `/` is a short public landing page with the same
restrictive headers as the rooms page. `npm run smoke -- <https origin>` is
a light post-deploy check (about ten requests, one synthetic public message
in a throwaway room). Verified on the Mac: wasm32 clippy, local runtime
test, the smoke logic against a local Worker (with the https requirement
relaxed in a scratch copy), and a dry run listing both Durable Objects.
Wrangler is not logged in; the owner must run `npx wrangler login` and
deploy, then record the public URL.

Deployed by the owner on 2026-10-31 to
https://faronet-edge.faronet.workers.dev with `npm run deploy`. The owner
reports `npm run smoke` passed against it (health, landing, rooms, origin
check, relay, feed). Agent check: `GET /health` returned 200 "FaroNet edge
ready", the health text introduced in 797c6c7, so the deployed Worker runs
that revision's code or later.

## Unified RFC FN-1 (2026-10-31)

Added `docs/rfc/faronet-rfc.txt`, the project RFC: ASCII only, at most 72
columns (checked), RFC 7322 layout with BCP 14 keywords. It consolidates
the accepted 0001 frame, CRC, Manchester and gateway-authentication
contracts, Teammate B's 0002 mesh contract (still PROPOSED there), the
0003 CSMA/CA proposal and the deployed edge rooms, feeds and rate limits,
and adds Privacy Considerations (RFC 6973 structure, four-adversary threat
model), Security Considerations and an RFC 7942 implementation-status
appendix. New normative text not yet implemented, and marked so in
Appendix A: random link addresses stored in non-volatile storage and
rotated every 24 hours and on panic; LAN links as 492-byte records over
TCP (proposed). The Appendix B frame vector was checked against
fixtures/optical-v1.json. Author lines say Student A and Student B; the
team should put names there and Teammate B should review Section 5.

## BOM (2026-10-31)

Added `hardware/bom.md` and `hardware/bom.csv`: every part of the soldered
revision-7 Faro (refs from `circuit-reference.json`, R6 = 47 kOhm for the
soldered board), plus the per-node power supply. Prices come from the
team's "Team Parts List redes" (14 Oct 2026, 455 CRC/USD; DBU and H2
prices include tax, CRCibernetica +13 % IVA, MicroJPM IVA unconfirmed with
a separate 13 % reserve) and two MicroJPM lookups on 31 Oct (AD595 button,
AD7480 DIP8 socket). Raspberry Pis, microSD cards and Dupont jumpers are
team-owned and not costed. Totals: CRC 4,654.54 per board; CRC 15,427.46
for two Faros with power supplies (16,006.02 with the MicroJPM reserve).
Several installed parts came from earlier MJ Electronica purchases or are
unidentified (the IR LED); they are costed with the list's equivalent.

## Project documentation and schematic (2026-10-31)

Added `docs/documentacion.md` (Spanish) with every section the assignment
lists: introduction, environment, design (schematic, threat model), data
structures and functions, run instructions, activities per student,
self-evaluation (state, problems, commit report, rubric tables), lessons
and bibliography. Hours per student, rubric grades and learning scores are
left as "(completar)" for the team. Activities and authors come from the
Git history (e1007e0, the rev-7 redesign, is authored by An-Gi).
`scripts/build_docs.py` builds `output/FaroNet-documentacion.pdf` (ignored)
with pandoc and XeLaTeX: the documentation plus the BOM (annex A) and the
verbatim ASCII RFC (annex B); checked visually (title, figure, annexes).
Added `hardware/schematic/faro-rev7.tex` (CircuiTikZ) with its PDF and SVG,
checked net by net against `circuit-reference.json`; R6 = 47 kOhm.


## TX timing diagnosis on Faro A (2026-10-31)

User-reported, Faro A at `7992103` or later: `optical-loopback` at 5, 3
and 2 ms half-bits still stopped with "TX missed its timing budget".
Added `optical-loopback --timing-report` (cd95998): frames are sent in
full and each reports per-symbol lateness split into wait overshoot, GPIO
write and per-symbol work, plus whether SCHED_FIFO took effect and the
kernel, RT throttling, timer slack and CPU governor.

User-reported, `--timing-report` at 5/3/2 ms, three frames each: 9/9
matched, 0 bit errors, 0 rejected waveforms. Kernel 7.0.0-1020-raspi
PREEMPT_DYNAMIC, `realtime: true`, RT runtime 950000/1000000 us, ondemand
governor at 1.2 GHz. In every frame the only symbol over 40 % of the
half-bit was symbol 0, late 1.2-2.4 ms, while encoding the frame took
2.3-2.6 ms on the Pi. That encoding ran after the first deadline was
taken. All other symbols: p99 lateness at most 0.093 ms, worst 0.31 ms
(GPIO write), per-symbol work p50 about 0.2 ms, max 0.93 ms. The one
extra symbol over 25 % (2 ms, symbol 1, 0.6 ms) followed symbol 0's
delay. Symbol 0 is an OFF level and TX was already off, so the frames
still decoded. RT throttling and scheduler preemption did not appear.

Fix (agent): `transmit()` encodes the frame before entering the on-air
section and taking the first deadline. A regression test with a 2.5 ms
encoder fails without the change and passes with it. Python suite: 123
passed on the Mac. The 0.4 half-bit budget and `SPIN_NS` are unchanged;
the evidence does not call for changing them.

User-reported, Faro A at 08fc33b, plain `optical-loopback --count 10`:
2 ms 10/10 matched, 0 bit errors, 0 rejected, TX max lateness 0.191 ms,
20.744 payload B/s; 3 ms 10/10, 0.219 ms, 13.846 B/s; 5 ms 10/10,
0.204 ms, 8.316 B/s. 2 ms, the shortest half-bit the bring-up accepts,
is the fastest qualified setting on one board; two-Faro rates and
distance remain unmeasured. Documentation, RFC Section 4 and Appendix A
updated to match.

## LAN mesh links and private terminal chat (2026-10-31)

Student B is bringing up Faro B, so Student A took over the LAN transport
and the private terminal chat (the owner chose this over the edge items
and panic work). `git fetch` showed no An-Gi commits after e1007e0.

Added `node/lan.py`: fixed 493-byte records over TCP (type byte plus a
492-byte body; envelopes fill it, control records are length-prefixed and
zero-padded). Links start with HELLO (signed directory entry, random
challenge) and PROOF (Ed25519 over the peer's challenge and both Node
IDs); only then is the peer a neighbor. Directory entries and new signed
neighbor lists (`FARONET-LINKS-V1`) are flooded; an edge counts only when
both ends list it; senders pick a random route of three relays with a live
first hop. Relays forward after a random 0-200 ms delay. Duplicate links
between a pair settle on the one dialed by the smaller Node ID. Limits:
16 neighbors, 256 directory entries. `node/chat.py` adds `chat` and
`mesh-node`; each run generates an in-memory identity that is never
saved. RFC Sections 5.6-5.8, 8, 10, 11 and Appendix A updated; the
documentation gained run instructions.

Agent-verified on the Mac: 9 new tests over localhost TCP (records,
signed lists, five-node message and reply across three relays, no route
with only two relays, a relay leaving removes the route, an impostor
replaying another node's entry is never linked, links dialed from both
sides settle on one, chat commands); the suite passed 5 times in a row
(132 tests). Five separate processes (two `chat`, three `mesh-node`) on
127.0.0.1 exchanged a message and a reply, each through three relays,
with 0 rejections. Not yet run between Pis and laptops; Faro links are
not attached to live nodes.

User-reported, first run across machines at d377dce: `chat --alias alice`
on Faro A's Pi 3 (Wi-Fi), and on the Mac three `mesh-node` relays (r1
dialing the Pi, r2 and r3 on localhost) plus `chat --alias bob`. Bob's
"hola" went via r3 > r2 > r1 and appeared on the Pi as from bob with the
reply target set; alice's reply went via r1 > r2 > r3 and appeared on
bob. Both chats ended with sent 1, delivered 1, rejected 0. Only the
Pi-r1 hop crossed the network; a run with relays on separate machines
(Faro B, a second laptop) is still pending.

## Perfboard layout, guide and BOM (2026-10-31)

Owner-supplied photos: the team's 7 x 9 cm blue board is single-sided;
the bare side prints columns 001-032; the copper side has rails at columns
7, 14, 21 and 28 and two-hole pairs elsewhere, 24 rows. Owner decisions:
R10 and R11 330 Ohm, R6 47 kOhm, doubled GND bridge, cut female Dupont
leads soldered to the board instead of a header.

Added `hardware/perfboard/`: a hole model of the board (`board.py`), the
placement (`layout.py`), `check.py` (every netlist net joined, no shorts,
13 deliberate mistakes rejected, pressed S1 pulls PANIC to GND) and
`guide.py`, which writes both board sides as SVG, `guia.html` (stages with
checkboxes, continuity and isolation tests, first power-up) and a text
sheet. D1 (rows 4-5) and Q2 (rows 20-21) point out of the right edge about
4 cm apart in mirror rows. Agent-verified on the Mac only: validation and
visual review of the rendered SVGs; no part spacing was measured, and
nothing has been soldered. BOM (7 x 9 board, uncosted; no header; three
330 Ohm), schematic (R10/R11 330 Ohm) and documentation updated.

## Link address rotation and panic erasure (2026-10-31)

Student A took over this Student B privacy item. `faro/address.py`
stores the Faro's random 8-byte link address in an owner-only file
(FARONET_STATE_DIR or ~/.faronet), replaces it every 24 hours, and
`optical-address [--rotate]` shows it. `--local` is now optional on the
link commands. Any panic during an optical command still turns outputs
off and releases GPIO, and now also rotates the address (exit code 3).
The chat gains `/panic` and `--panic-gpio CHIP`: both close every link,
drop the private keys, directory, routes, messages and replay memory
(best effort in Python), rotate the address, clear the screen and
scrollback, and exit. Agent-verified on the Mac: 7 new tests (persistence,
permissions, 24 h rotation, damaged files, CLI, panic rotation through the
fake libgpiod, Node erasure with the peer seeing the link drop, GPIO
watcher); Python suite 139 passed. Not yet run on a Pi.

## Edge gateway relay and dead drop (2026-10-31)

Student A took over this Student B edge item (owner's choice). Rust:
`gateway.rs` adds `POST /gateway/rooms/{topic}` (a Gateway's public text
published into a topic, connections and feed) and `POST`/`GET
/gateway/drop/{id}` (one 1024-byte opaque blob per 64-hex slot, write
once, delete on read, 24 h TTL, `DeadDrop` SQLite Durable Object). Every
route checks the HMAC contract (headers `X-FaroNet-*`), freshness and the
body, then claims the nonce in the `GatewayReplay` SQLite Durable Object
(nonce and expiry only), failing closed; routes answer 404 without
`GATEWAY_SECRET`. `Verifier::authenticate` splits the checks from the
claim while keeping the clock read after the MAC. Python:
`gateway/client.py` and the commands `gateway-publish`, `drop-secret`,
`drop-put`, `drop-take`; dead-drop ids and keys derive from a 32-byte
shared secret and blobs are SecretBox-sealed to exactly 1024 bytes.

Agent-verified on the Mac: `cargo test` (26), `npm run check`, `npm run
build`, `npm run test:gateway` against `dev:gateway` (unsigned, wrong
secret/key/clock, body rejected before the nonce is claimed, replay 409,
relay reaches a WebSocket and the feed, dead drop sizes, 201/409/200/404),
`npm run test:rooms` regression, `npm run dry-run` listing both new
Durable Objects, 7 Python client tests against a verifying stub, and the
Python CLI against the local Rust Worker (publish into the feed, drop
put/occupied/take/empty, wrong secret 401). Not deployed: the owner must
`wrangler secret put GATEWAY_SECRET` and deploy. RFC Sections 6, 7.1,
7.6, 8, 10 and Appendices A and C updated; directory replica still open.

Deployment (owner-reported, 2026-11-01): the owner stored GATEWAY_SECRET
with `wrangler secret put` and redeployed. Agent check: unsigned gateway
requests now get 400 instead of 404, so the Worker sees the secret. The
owner's first signed run got HTTP 403 on all three commands; the agent
reproduced it as Cloudflare error 1010 for the `Python-urllib` User-Agent
(curl and any other agent reach the Worker). The client now sends
`FaroNet-Gateway/<version>`; agent check against the deployment: a
wrong-secret request now reaches the Worker and gets 401. Added
`gateway-secret`, which stores the secret typed into a hidden prompt in
an owner-only file on the Gateway Pi. Signed success on the deployment
still pending the owner's rerun.

Owner-reported, 2026-11-01, from the Gateway Pi against the deployment:
`gateway-publish --topic demo` returned published, `drop-put --slot 1`
stored the blob and `drop-take --slot 1` returned its text. The
authenticated relay and dead drop therefore work end to end on
https://faronet-edge.faronet.workers.dev.

## Q1 pinout correction (2026-11-01)

Owner-reported: a transistor tester shows the team's 2N2222 as E-B-C
facing the flat side, not C-B-E; on the breadboard it was simply turned
around with the base in the same hole. The perfboard holes stay (C F5,
B F6, E F7); the guide and drawing now place the flat face toward the
left (toward R2), and the reference note and breadboard README record
the correction. The electrical layout and `check.py` are unchanged.

## Spanish user-facing text (2026-11-01)

Owner direction: like the documentation, everything an end user sees is in
Spanish. The edge (landing and rooms pages, rooms.js, Atom feeds with
xml:lang es, HTTP error texts, WebSocket close reasons, gateway answers,
health text "Edge de FaroNet listo"), the terminal chat and relay node
(help, status lines, errors shown in the chat), the gateway commands
(plain Spanish sentences instead of JSON) and the panic messages are
translated. Code, comments and bench JSON stay in English. Agent-verified:
cargo test, npm run check, test:rooms and test:gateway on fresh local
Workers (the feed-root expectation now includes xml:lang), the rooms page
viewed in the browser pane, Python suite 147 passed, and a five-process
local chat run. The edge change needs the owner's `npm run deploy`.

## Public directory replica (2026-11-01)

Owner's choice. Rust `directory.rs`: `POST /gateway/directory` (gateway
HMAC) verifies a signed directory entry exactly as a Python node does
(format, Node ID from the verify key, 30-day lifetime rule, Ed25519 with
`ed25519-dalek` 3.0.0 verify_strict, usable now) before a
`DirectoryReplica` SQLite Durable Object stores it; newer replaces older
(201), same is 200, older 409, at most 256 entries, alarm erases expired
ones. `GET /directory` serves the entries as hex JSON. Python:
`fetch_directory` and `directory-fetch` re-verify every entry;
`EdgeClient.publish_entry`; `mesh-node --edge-publish [URL]` publishes each
entry the Gateway node learns, off the event loop.

Agent-verified on the Mac: Rust unit tests including the Python-signed
fixture and tampering (alias, Node ID, expiry, prefix), wasm clippy,
build, `npm run test:gateway` with Ed25519 entries signed by Node (201,
200, 409, tampered 400, forged ID 400, listing), 3 new Python tests
against the verifying stub (publish, older refused, forged and expired
rejected on fetch, the mesh node publishing), the suite, and a local run
where a gateway mesh-node published its own and its neighbour's entries
to the Rust Worker and `directory-fetch` verified them. Not deployed.

Deployment (owner, 2026-11-01): `npm run deploy` with the Spanish edge and
the directory replica. Agent check against the deployment: health text
"Edge de FaroNet listo", landing and rooms pages in Spanish, unsigned
POST /gateway/directory refused with 400, and `directory-fetch` from the
Mac verified the one entry published by the owner's Gateway node
(`pi-gateway#07a11975`) with 0 rejected.

## Q1 flat face turned to the right (2026-11-01)

Owner-reported while soldering: with the flat face away, the 2N2222 reads
C-B-E left to right, which is E-B-C from the flat side, as the tester
said. The earlier correction put the flat face toward the left, but seen
from the left the top hole (C, F5) is on the viewer's left, so that
placement reads C-B-E from the flat side and would have swapped C and E.
The guide and drawing now place the flat face toward the right (toward R3
and the board edge), with a check: from the right side of the board, the
flat face reads E-B-C left to right. Holes and `check.py` are unchanged
(13 mistakes still caught).

## Documentation sync before the freeze (2026-11-01)

`docs/documentacion.md` brought up to date with everything after
`5521917`: edge section (gateway relay, dead drop, directory replica,
Spanish text), data-structure tables (Python gateway client, address
store, Rust `gateway.rs` and `directory.rs`), run instructions (chat
`/panic`, gateway commands with `FARONET_DROP_SECRET`, `dev:gateway` /
`test:gateway`, `wrangler secret put`), Student A activities for the
work taken over from Student B, "Estado final" (deployed gateway and
directory, 149 Python and 30 Rust tests), two new problems (Q1
orientation, Cloudflare 1010) and the commit report up to `66e70a7`.
Hours, grades and learning scores stay "(completar)". The RFC appendix,
the root, Python and Rust READMEs no longer call deployed work pending.
Agent-verified: Python suite 149 and `cargo test --locked` 30 at
`66e70a7`; RFC still ASCII within 72 columns; PDF rebuilt.

## Faro links in the live mesh (2026-11-01)

Owner direction for the remaining hours: keep working on pending code and
documentation. Built the item offered in the morning handoff. New
`faro/bridge.py` and the command `optical-bridge`: a separate process on
each Faro's Pi (so TX timing never waits on the Node's event loop or GIL)
accepting one local TCP connection from the Node and carrying its LAN
records over a CsmaLink session. Envelopes cross as the six 86-byte
fragments of RFC Section 5.3; control records cross unpadded in chunks of
at most 85 bytes (payload length tells them apart). After three failed
attempts, a broken stream or a Node disconnect, the bridge moves to the
next epoch (session = SHA-256("FARONET-OPTICAL-EPOCH-V1" || base ||
epoch)[0..7]), sends an empty DATA frame and closes its Node connection;
a peer seeing DATA in any of its next 256 epochs adopts it. `chat` and
`mesh-node --faro-peer ADDR --faro-session S [--half-bit-ms]` start the
bridge, dial it with a 600 s handshake (`LanNode.dial(...,
handshake_seconds)`), report epoch changes, turn a bridge panic exit (3)
into the Node's panic, and stop it with SIGTERM (SIGTERM now behaves like
Ctrl+C in chat and the optical commands; background jobs pass SIGINT as
ignored, which first left bridges running). RFC Section 5.9 added
(plus 5.6, 5.7, 8, 10, Appendix A); documentation, bring-up guide and
READMEs updated.

Agent-verified on the Mac: 8 new tests (control wire format, garbage
rejected, epoch sessions; two bridges in threads on a fake light between
five real LanNodes over TCP: message and reply across the light with
envelopes as fragments, and recovery after a blocked light: A
`send-failed` to epoch 1, B `peer` to epoch 1, both Nodes relinked and
exchanged again; the chat's bridge process glue). Python suite 157
passed. End to end as separate processes, with a scratch sitecustomize
replacing GpioFrameIO by UDP between the two bridge processes:
alice - r1 =light= r2 - r3 - bob, "hola por la luz" delivered via
r1 > r2 > r3, 0 rejected, no process left after SIGTERM. Estimated at
T = 2 ms from measured record sizes: handshake about 1 minute, five-node
directory sync about 7 minutes, 52 s per envelope per optical hop. Not
run on Faros: needs both Faros passing `optical-link` first.

## Pre-freeze review (2026-11-01)

Owner asked for a final review of everything since `95b4338`. Two review
agents (standards and RFC/spec) reported; the agent checked each finding
in the code before acting. Fixed:
- the chat printed remote text unsanitized; control characters
  (newlines, ANSI/OSC escapes) are now shown as spaces, so a sender cannot
  forge a line or drive the terminal;
- a node that failed to start (port in use, no gateway secret) left its
  optical bridge holding the GPIO;
- `--edge-publish` ignored `FARONET_GATEWAY_KEY`/`FARONET_EDGE_AUDIENCE`
  (now shares `edge_client`), lost track of its tasks and counted a 409 as
  published; a missing secret crashed with a traceback;
- one late TX symbol (TimingError) ended the bridge; the frame now counts
  as lost and CsmaLink retries it;
- the panic handler of the optical commands could exit 1 instead of 3 if
  rotating the address failed, so the chat would not erase its Node;
- `LinksRecord` did not check the ascending order the RFC requires; two
  different directory entries with the same issue time could replace each
  other and flood forever (the first held now wins);
- Spanish: argparse option errors (alias, addresses), signing errors, and
  the bridge's stop/failure lines shown in the chat.
Documented rather than changed: the 24-hour address rotation and the
24-hour directory entry apply per run (restart daily); envelopes queue
behind the directory sync over light, so raise the TTL. Not changed
(would need a redeploy): the Edge answers 200 for a different entry with
the same issue time without storing it.

Agent-verified on the Mac: 4 new or extended tests (sanitized chat line,
unsorted LINKS rejected, same-time twin entry refused, two late TX frames
retried with both bridges alive); Python suite 158 passed; a mesh-node
with `--faro-peer` on a taken port exited 2 with no bridge left; the
alias error is shown in Spanish.

## Student B, freeze night (2026-11-01)

Owner (An-Gi) passed Student A's handoff and asked the agent to work
through its tasks; commits are the owner's, without agent attribution.

### Task 2: Edge directory refuses a same-time twin (409)

`decide` now takes the stored issue time and bytes. The same bytes again
answer 200; different bytes with the same issue time answer 409 (RFC
7.6) and the stored entry is kept. `DirectoryReplica` reads `issued,
entry` for the Node ID to compare. RFC 7.6 and Appendix A updated.

Agent-verified on the Mac: `cargo test --locked` 31 passed (one new
unit test), `npm run check` passed, and `npm run test:gateway` against a
fresh `npm run dev:gateway` passed with a new case (a second
`entry(now - 30)`, same time and different box key, answers 409). Not
deployed: Student A has to run `npm run deploy`.

### Task 3: a running node re-signs its directory entry every 12 h

`LanNode.reissue_entry()` signs a new 24-hour entry (same alias, issued
time strictly later) once 12 hours have passed since the current one,
stores it and floods it through `_learn_entry`, so peers and the
Gateway's `--edge-publish` (it publishes on `on_change`) get it before
the old entry expires. A task started by the first `listen` or `dial`
checks once a minute and stops with `close`/`wipe`. A node no longer has
to be restarted daily for its entry; the 24-hour Faro address rotation
still happens only when an optical command starts. RFC 5.2, 5.7 and
Appendix A updated.

Agent-verified on the Mac: one new test with an injected clock (two
Nodes over localhost TCP; no re-sign one second early, then the peer
holds the new entry, still usable after the first one expired); Python
suite 159 passed.

### Task 4: envelope fragments ahead of control chunks on the light

`read_client` still offers an envelope's six fragments to the CsmaLink
at once, but control chunks now wait in the bridge's own queue;
`feed_link` (called every loop turn) offers the next one only when the
link queue is empty, so their order is kept and a message no longer
waits minutes behind the directory sync. The queue resets with each
epoch. RFC 5.9 and Appendix A updated.

Agent-verified on the Mac: one new unit test (an ENTRY, a LINKS and an
ENVELOPE from the Node: only the six fragments are queued first, no
control chunk is offered while the queue is busy, and the chunks decode
back to the ENTRY and LINKS in order); all bridge tests pass, including
the two bridges on a simulated light; Python suite 160 passed. Not run
on Faros.

### Task 5: small cleanups

- One `link_id` parser, in `faro/address.py`, for the chat/mesh-node
  `--faro-peer`/`--faro-session` options and the optical commands'
  `--local`/`--peer`/`--session`. Same validation; the optical commands
  now show the chat's Spanish message instead of argparse's English
  "invalid link_id value" (it is still a ValueError). Python suite 160
  passed; `optical-link --peer XX` shows the Spanish error.
- `store_secret` flushes and fsyncs the temporary file before the
  atomic replace, as `AddressStore.rotate` does, so a power cut cannot
  leave an empty Gateway secret. Python suite 160 passed.
- One `now_seconds` for the Edge: `directory::runtime::now_seconds`,
  now `pub(crate)`, also used by the gateway routes. `cargo test
  --locked` 31 passed, `npm run check` passed, `npm run test:gateway`
  passed against a fresh `npm run dev:gateway`.
- `PANIC_EXIT = 3` is defined once next to `PanicStop` in `faro/gpio.py`;
  the optical commands return it instead of a literal 3 and the chat
  imports it from there. Python suite 160 passed.

### Task 1: Python suite on Faro B (Pi 2) and its environment

Owner-reported from Faro B over SSH after pulling `8696272`: Raspberry Pi
2 Model B Rev 1.1, Ubuntu 22.04.5 LTS, kernel `5.15.0-1061-raspi`,
`armv7l` with 32-bit user space; system Python 3.10.12, venv Python
3.11.18 (GCC 11.4.0), PyNaCl 1.6.2, gpiod 2.5.0. `unittest discover`
ran 160 tests, OK, in 32.7 s. Recorded in `hardware/pi-environment.md`
and `python/README.md`; Python 3.11 is the floor for new syntax.

### Uncaught errors found in a final code review

Three read-only review agents compared the code with the assignment;
the agent reproduced or read each of these before fixing it. Each one
used to end in a traceback:
- chat `/ttl ²` (a Unicode digit passes `isdigit()`, `int()` raised and
  the chat exited 2): now refused with the usual TTL message;
- `chat --panic-gpio` without gpiod or with a bad chip printed a thread
  traceback and kept running unprotected: `open_panic` now requests the
  line before the node starts, so it exits 2 with a Spanish message; a
  failure while watching prints one line;
- input that is not UTF-8 stopped the chat's stdin reader for good: it
  now reads bytes and shows invalid ones as U+FFFD;
- `optical-address` with an unwritable state dir: exit 2 with a message;
- `gateway-secret`: Ctrl+C/Ctrl+D at the prompt exit 130 ("Cancelado"),
  an OSError storing the file exits 2.

Agent-verified on the Mac: 3 new tests and 2 extended ones; Python
suite 163 passed; a piped chat session refused `/ttl ²`, accepted
`/ttl 60`, survived bytes FF FE and quit with 0; `--panic-gpio` without
gpiod exited 2 with the message. Known gaps left for the documentation
(no time before the freeze): no private topics inside the mesh, public
mesh text reaches the Edge only with `gateway-publish`, panic has no LED
pattern, and the reported bit errors count only CRC-valid frames.

### Public mesh text to the Edge, and private topics (layer 7)

Owner moved the deadline to 23:40 to close the gaps the review found.
`MessageKind` gains PUBLIC (2) and TOPIC (3); both carry a topic (1-32
of `[a-z0-9-]`, the Edge room rule) inside the same length-prefixed
body, so TEXT messages encode exactly as before. Chat commands:
`/tema TEMA A,B` (each line is encrypted once per member; it never
leaves the mesh), `/gateway NOMBRE` (default alias "gateway") and
`/publico TEMA TEXTO` (sent like any envelope to the Gateway). A
`chat`/`mesh-node --edge-publish` now also posts each PUBLIC message it
receives to that Edge topic, off the event loop; TEXT and TOPIC never
leave. RFC 5.5 and Appendix A updated.

Agent-verified on the Mac: 2 new tests (message kinds round trip and
validation; five LanNodes over TCP: a topic reaches the reachable member
and reports the unreachable one, a bad `/publico` is refused, a PUBLIC
message is posted once to a fake Edge); Python suite 165 passed. End to
end against `npm run dev:gateway`: alice > r1 > r2 > r3 > gateway,
`/publico avisos-e2e hola desde la mesh`, and the text appeared in
`/rooms/avisos-e2e/feed.atom`.

### Panic shown on the Faro's LEDs

`GpioFrameIO.close` after a panic now blinks LED_TX and LED_RX together
3 times (150 ms on/off) with TX (the IR emitter) off, then sets every
output INACTIVE before releasing the lines (a released line keeps its
last value; a Ctrl+C mid-blink still ends with all off). This covers
every optical command and the bridge, so `chat --faro-peer` shows it
too. RFC 4.8 updated.

Agent-verified on the Mac with the fake GPIO request: one new test
(three ACTIVE writes on each LED, TX never ACTIVE, all outputs off,
lines released); Python suite 166 passed. Not run on a Faro: check the
blink by pressing panic during `gpio-calibrate` or `optical-link`.

### `optical-inject`: a frame built outside the Faro, from the terminal

`optical-inject --hardware-ready --frame HEX [--count N]` (`-` reads the
hex from stdin, for example from a Scapy script) checks the 128 bytes
with `Frame.decode` before any GPIO line is requested, then guards and
transmits the frame unchanged N times, printing one JSON line per send.
A bad hex string, length, CRC or field exits 2 with the usual "Falló el
comando óptico" message. RFC 4 (`send_frame`) mentions it.

Agent-verified on the Mac with a fake GpioFrameIO: one new test (a
DATA frame sent twice unchanged, from the argument and from stdin; a
damaged CRC, non-hex and a short frame refused without transmitting);
Python suite 167 passed. Not run on a Faro.

### Raw BER in `optical-loopback`

The review found that `bit_errors_in_crc_valid_frames` is almost always
0, because a damaged frame never passes its CRC. `EdgeDecoder` now keeps
the bytes of the last complete capture that failed to decode
(`raw_bits`: the first level of each Manchester pair), `GpioFrameIO`
exposes them after a loopback transmit, and the loopback summary adds
`raw_bit_errors`, `raw_bits_compared`, `ber` and
`frames_without_capture`. Existing fields are unchanged. Bring-up guide
updated.

Agent-verified on the Mac with the simulated reflection: clean loopback
reports `ber` 0.0 over 2048 bits; a dropped edge yields a damaged capture
with raw bit errors > 0 counted in `ber`; no reflection reports `ber`
null and 2 frames without capture. Python suite 167 passed. Not run on
a Faro.
