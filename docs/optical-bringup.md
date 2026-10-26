# Student A: optical baseline for the October 26 meeting

Prepared October 25, 2026, Costa Rica time. This is a physical smoke-test
baseline with **operator-controlled turns**, not autonomous private chat.
The serialized v1 frame, Manchester convention, CRC and three-attempt
stop-and-wait policy are unchanged. Test payloads are deterministic synthetic
86-byte blocks; the commands never accept or print private message text.

## What changed since the handoff

- Student A: Raspberry Pi 3 Model B rev 1.2, Ubuntu Server 26.04.1 ARM64,
  installed from the direct Ubuntu image with balenaEtcher; proper 5 V,
  2.5 A supply now available. SSH account: `ubuntu@zekken-pi.local`.
- Student B: Raspberry Pi 2 Model B, Raspberry Pi OS (PiOS), installed with
  Raspberry Pi Imager. Its exact OS/Python/library versions still need a
  live check. Do not assume its gpiochip number or architecture from A.
- The circuit is assembled but disconnected from A's Pi as of October 25.
  No physical signal, bitrate, BER or panic-button operation is verified.
- Commit `a6518cf32d81bd575e8fdc5c1f46366db170dde5` adds B's signed directory,
  492-byte encrypted envelopes, six-frame fragmentation and simulated mesh.
  It adds no GPIO transport, LAN socket transport, interactive chat or Rust.
  Proposal 0002 remains proposed. This baseline transports opaque payloads
  without accepting its unresolved routing, key-lifecycle or LAN choices.

## Hardware authority

Use [the revision-6 breadboard guide](../hardware/breadboard/README.md),
[review HTML](../hardware/breadboard/faronet-breadboard-review.html) and
the matching basic/RGB SVGs. `circuit-reference.json` supplies these pins.
Older top-level HTML RGB/LS125 instructions are superseded by the common-
cathode RGB revision. The implementation does not use SPI or ID pins.

| Role | BCM | Physical header | Logical behavior |
| --- | ---: | ---: | --- |
| Optical TX | 17 | 11 | HIGH = emitter on; idle LOW |
| Conditioned RX | 27 | 13 | HIGH = received light after calibration |
| TX indicator | 22 | 15 | HIGH while transmitting a frame |
| RX indicator | 23 | 16 | HIGH while a candidate frame is being captured |
| Panic | 24 | 18 | External pull-up, pressed LOW; stop latches |
| RGB red | 5 | 29 | HIGH = on, optional `--rgb` |
| RGB green | 6 | 31 | HIGH = on, optional `--rgb` |
| RGB blue | 13 | 33 | HIGH = on, optional `--rgb` |

All selected outputs are requested atomically with initial LOW values.
RGB is opt-in: green means ready and blue means transmitting. Cleanup turns
all requested outputs off. The RX comparator and panic circuit have external
pull-ups; the backend does not enable internal pull resistors.

Before connecting signal wires, follow the guide's unpowered continuity and
button/contact checks, then verify receiver output changes within **0–3.3 V**
with/without light. For the unspecified IR emitter, retain the guide's
conservative current-limiting resistor and measure before changing it.
`--hardware-ready` records the operator's completion of these checks; it
does not perform electrical measurements. Connect/rewire with power off.

## Software preparation on each Pi

Both Pis already have this repository cloned. Use those clones for normal
development and testing; no new clone or source archive transfer is needed.
On A the existing clone is `/home/ubuntu/FaroNet`; substitute B's actual
clone path in the commands below if different.

The implementation, tests and guides are repository source files, developed
on `codex/student-a-optical-baseline` and reviewed by the owner on Oct 25.
The owner authorized committing them to `main` and pushing to `origin`.
Follow
[the contribution/review workflow](development.md#review-without-committing):
the owner controls review and publication. The Git commands below retrieve
the published `main` revision. Do not treat the earlier scratch copy or an
archive as the shared repository's published revision.

After publication, update each existing Pi clone to the same approved
branch and commit. These examples use the authorized target, `main`.

```bash
cd ~/FaroNet
git status --short --branch
```

If there are local file changes, preserve them and resolve the checkout
before continuing. Do not reset, clean, overwrite, or automatically stash
teammate work. With a clean checkout:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
test -f python/src/faronet/faro/gpio.py
```

Compare the printed commit on both Pis with the reviewed published commit.
If the fast-forward fails, or the GPIO file is missing, stop and check the
branch/publication state; do not merge or substitute old source files.

Each Pi uses its own environment **inside its existing clone**, at
`python/.venv`. Reuse it if it already exists and belongs to that Pi;
create it only when missing. Do not copy the Mac's or the other Pi's venv.

```bash
cd ~/FaroNet/python
python3 --version
uname -m
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python --version
.venv/bin/python -m pip install -r requirements-gpio.txt
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m compileall -q src
.venv/bin/python -m pip check
```

If an existing `.venv` is broken or uses Python below 3.11, inspect and
repair it deliberately rather than deleting/replacing it automatically.
Python >=3.11 and **libgpiod's v2 Python API** are required. On B's 32-bit
PiOS a wheel may be unavailable; record any build failure rather than
substituting an incompatible v1 API. The optical modules themselves use
the standard library and the optional gpiod backend. PyNaCl is needed for
the full Node suite. Python is run directly from the clone; `compileall`
is a bytecode check. No Cargo, Rust/WASM compilation, npm or Wrangler step
is needed on either Pi. Worker setup/build/test commands run on the Mac
from its existing clone's `rust/` directory.

For A, run preflight from the updated existing clone in the SSH session:

```bash
cd ~/FaroNet/python
sudo .venv/bin/python -m faronet gpio-preflight
```

Preflight only opens the chip and reads metadata; it never requests lines.
On A it identifies `/dev/gpiochip0`, `pinctrl-bcm2835`, with all eight roles
unclaimed. A's current `ubuntu` account lacks chip permission; `sudo` works.
No permission/group/SPI changes were made. On B identify its controller
using its installed GPIO tools or inspect chip devices with preflight,
then supply `--chip /dev/gpiochipN` if necessary. Stop on an unexpected
controller or a role already claimed by another consumer.

### Earlier verification copy and optional offline transfer

The Oct 25 software checks used a separate review copy at
`/home/ubuntu/faronet-baseline-20261025` so the existing clone stayed clean
before owner review/publication. Its venv has PyNaCl 1.6.2 and gpiod 2.5.0;
the full suite and mesh simulation passed without opening GPIO lines.
That evidence applies to that copy, not to an update of `~/FaroNet`.

`python3 scripts/package_pi_baseline.py` on the Mac can still produce an
optional Python-only archive for offline review. It is not the normal
deployment/update path for these already-cloned Pis. Do not extract it over
an existing checkout or transfer venvs/compiled artifacts. Use Git to obtain
the reviewed source revision in the shared workflow above.

## Meeting sequence

1. Complete the electrical checks above, power off, connect each header,
   then power up. Follow the facing-layout SVG: rotate the second complete
   board 180 degrees and align each emitter with the other's detector.
2. Run metadata preflight on both Pis. Close any other program that owns
   these lines. Leave SPI configuration alone.
3. Run the input monitor on each Pi. Block/illuminate the detector: `light`
   must change 0→1. If measured polarity is opposite, pass `--rx-inverted`
   consistently on that Pi's later commands. Confirm the physical button
   stops the monitor; releasing it must not resume the process.

```bash
sudo .venv/bin/python -m faronet gpio-monitor --hardware-ready --seconds 20
```

4. Generate a **fresh session** once, and copy its printed 16-character
   lowercase hex value into both terminals. These are synthetic local link
   addresses, not keys or long-term mesh identities.

```bash
.venv/bin/python -m faronet optical-session
```

In **both** shells, set `FARONET_SESSION` to that printed value:

```bash
read -r FARONET_SESSION
```

Paste the value and press Enter. Start B as listener first (all commands
below run from the Pi copy's `python/` folder):

```bash
sudo .venv/bin/python -m faronet optical-listen --hardware-ready \
  --local 0202020202020202 --peer 0101010101010101 \
  --session "$FARONET_SESSION" --count 3 --timeout 300 --half-bit-ms 5
```

Wait for B's `ready` JSON line. On A, also from its existing clone's `python/`:

```bash
sudo .venv/bin/python -m faronet optical-send --hardware-ready \
  --local 0101010101010101 --peer 0202020202020202 \
  --session "$FARONET_SESSION" --count 3 --half-bit-ms 5
```

Expected: A reports three `acknowledged: true` frames; B reports three
unique received payloads and zero payload-bit mismatches. B stays listening
for about 73 seconds after the final unique frame to re-ACK retries if the
last ACK was lost. Let it finish before starting the next direction.
At 5 ms/half-bit, one frame lasts 10.24 s; nominal modulation is 100 bit/s,
with ACK/guard overhead reducing payload throughput. These are configured
durations, not measured performance. A clean three-frame run takes roughly
62 s plus B's retry linger.

5. Generate a new session, update both variables and swap sender/listener:
   A listens with local `0101010101010101`, B sends with local
   `0202020202020202`. Each `--peer` stays the other address. Never run two
   senders simultaneously or restart one side alone with the old session.
6. While transmitting a synthetic test, press panic and confirm emitter
   and indicators turn off. Also test Ctrl+C. Restart both sides with a
   fresh session after interruption, retry exhaustion or a timing error.
7. Repeat at three measured distances and record the table below.

Add `--rgb` on boards carrying the revision-6 common-cathode RGB only.
Keep the same half-bit setting on both Pis. A TX timing error stops output;
try 10 ms on both boards and increase listener timeout for the longer run.
The supported bring-up range is 2–20 ms, with no claim that its fast end
works on either board. Begin at 5 ms, then measure.

| Date/direction | Distance m | Ambient/threshold notes | Half-bit ms | Frames attempted/ACKed/unique | Retries | CRC-valid payload bit errors | Payload B/s | TX max lateness ms | Waveform rejects/overruns |
| --- | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| A→B | | | | | | | | | |
| B→A | | | | | | | | | |

The receiver checks known synthetic payloads **after** Manchester and CRC
validation. Rejected frames are counted separately. Zero mismatches among
accepted frames is not raw optical BER: corrupted/unacquired frames are
excluded. Record failures, elapsed time and delivery counts too. The TX
metric is software write lateness, not an oscilloscope edge measurement.
No measured results should be filled in before the meeting.

## Recovery and implementation boundaries

- No input changes: revisit polarity, alignment, RV1 threshold, power and
  wiring using the breadboard guide. GPIO metadata cannot diagnose analog
  receiver operation.
- Input changes but rejected waveforms: both clocks must match; check
  ambient interference and receiver conditioning, then slow both ends.
  Acquisition uses a quiet interval, preamble/sync, kernel monotonic edge
  timestamps and a configured clock. It has no continuous drift tracking.
- B receives but A exhausts retries: inspect B→A optics/polarity as well;
  every successful DATA exchange needs a working optical ACK return path.
- Wrong session/address/sequence traffic is ignored. Only the immediately
  previous exact DATA is re-ACKed; payload delivery occurs once per live
  process/session. State is in memory; use a new session after restart.
- Ctrl+C, panic and normal exceptions clear adapter references and turn
  outputs off/release requests. This does not promise secure erasure of
  Python memory, keys in other Node processes, or cleanup after power loss.
  Full application panic/zeroization remains a separate integration task.
- The physical adapter accepts externally serialized frames via
  `send_frame()` and opaque payloads via `send()`. A timestamped-wire test
  carries B's six fragment payloads through it, loses an ACK, reassembles
  exactly once and sends a reply. That is software integration evidence;
  the live private chat/LAN/three-relay deployment is still pending.
- No external turn coordinator is required by this smoke test; humans pick
  one sender and one listener. It does not implement the assignment's
  final autonomous turn acquisition, handoff, rotation or recovery protocol.

Backend API references: [libgpiod line requests](https://libgpiod.readthedocs.io/en/v2.3/python_line_request.html),
[line settings](https://libgpiod.readthedocs.io/en/master/python_line_settings.html),
[edge timestamps and sequence numbers](https://libgpiod.readthedocs.io/en/master/python_edge_event.html).
The installed Pi package is pinned to 2.5.0; its metadata API was exercised
without any line request.
