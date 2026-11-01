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

