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

