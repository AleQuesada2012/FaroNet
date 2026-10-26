# Sources and implementation decisions

Reviewed on 2026-10-09, board change recorded on 2026-10-22, environment and
hardware authority refreshed on 2026-10-25. These sources
describe the project; this repository setup does not mean their deliverables
have been implemented.

## Sources

- [Kick-off Proyecto 1 Redes](https://docs.google.com/document/d/1T8HVIzvNXNovJKPM68aEU6CvZbR9tCTmzVtLurkvUcw/edit?usp=drivesdk),
  sections "Lenguajes seleccionados", "Entorno de desarrollo", "SBC
  seleccionado: Raspberry Pi", "Flujo de trabajo con VCS", and draft threat model.
- Assignment: `Proyecto1-ii2026.pdf`, supplied separately by the repository
  owner. Pages 2-6 describe languages and functional requirements; pages 7-8
  describe deliverables/documentation. The PDF has not been copied into Git.
- Owner's setup request: Rust edge environment, Python nodes, beginner-friendly
  repository, ask about uncertain additions, and no commits before review.
- [Team Parts List redes](https://docs.google.com/document/d/1ZU3QwoxfobShuVfnTxJT4O7N1sLdE7ZRgDXk2CdZ-M0),
  read on 2026-10-09 from the owner's ChatGPT Drive folder. It identifies two
  Raspberry Pi 3 Model B Rev 1.2 units, TSAL4400/TEFT4300 for IR, and a 650 nm
  laser module with a BPW34 photodiode for laser trials. It still describes IR
  as primary, an ADC, LCD, and buzzer; these are not all current scope choices.
- Owner's 2026-10-09 development direction: both teammates contribute Python
  and Rust; Raspberry Pi 3 Model B rev 1.2 with Ubuntu Server; laser preferred,
  IR fallback; required features and RGB debugging in the first iteration;
  LCD and speaker/buzzer only after minimum requirements are met.
- Owner's 2026-10-22 update and the team's breadboard guide
  (`hardware/breadboard/README.md`): the boards are now one Raspberry Pi 3
  Model B rev 1.2 and one Raspberry Pi 2 Model B v1.1, which share the
  40-pin header and BCM numbering. This supersedes the "two Pi 3" entries
  in the parts list and earlier owner direction.
- Owner's Pi command output: Ubuntu 26.04.1 LTS, `aarch64`, kernel
  `7.0.0-1020-raspi`, Python 3.14.4 and `getconf LONG_BIT` = 64; GPIO character
  devices and permissions recorded in [the Pi profile](../hardware/pi-environment.md).

## Source precedence for the current direction

The owner's October 25 update confirms A's Ubuntu Pi 3/direct-image plus
balenaEtcher installation and 5 V/2.5 A supply; B uses a Pi 2 with PiOS
installed by Imager. For current circuit pins and polarities, the revision-6
breadboard HTML/SVGs and `circuit-reference.json` supersede stale hardware
descriptions here and in the older handoff, including the LS125 RGB branch.
The current test board is the IR/PT333 comparator circuit shown there.
Physical operation still requires measurements. The Student A baseline
uses explicit manual turns for the Oct 26 test, without settling autonomous
medium access or accepting proposal 0002's pending choices. Its local-only
public-room prototype is disabled in the default Worker configuration.
Worker development/builds/tests stay on the owner's Mac. See
[the meeting runbook](optical-bringup.md) and [Pi profile](../hardware/pi-environment.md).

The owner reaffirmed that both `hardware/breadboard` variants represent
assembled circuits. The basic no-RGB profile is the default; the RGB branch
is optional local debugging, with future patterns still open. Its selection
does not affect the optical protocol or require the peer to use RGB. Only
selected pins are inspected/requested; basic operation leaves BCM5/6/13 alone.

The owner's 2026-10-09 decisions supersede the earlier LED/LDR plan and the
parts list's IR-first ordering. No LDR implementation is planned. The native
Google Docs are reference sources and have not been edited in this session.
For planning, the owner instructs us to assume the grader accepts the laser;
the matched IR link remains the fallback if that assumption changes. This is
an explicit planning assumption, not a recorded instructor approval. The
actual receiver circuit remains unresolved. The parts list's sample
SPI/I2C/GPIO wiring is not an approved project pin map.

## Confirmed choices and requirements

| Item | Choice or constraint | Source |
| --- | --- | --- |
| Edge language | Rust compiled to WebAssembly | Owner and kick-off |
| Edge IDE | RustRover | Kick-off |
| Node language | Python | Owner |
| Faro control | Python on GNU/Linux, Raspberry Pi, GPIO connection | Kick-off |
| Available boards | One Raspberry Pi 3 Model B rev 1.2 and one Raspberry Pi 2 Model B v1.1 (updated 2026-10-22; previously two Pi 3) | Owner; breadboard guide |
| Operating system | A/Pi 3: Ubuntu Server 26.04.1 LTS, direct image with balenaEtcher. B/Pi 2: PiOS installed with Imager; exact release pending | Owner's Oct 25 correction; live A `/etc/os-release` |
| Pi architecture | Pi 3: `aarch64`/ARM64; `getconf LONG_BIT` = 64. Pi 2 B v1.1: 32-bit ARMv7, to be confirmed on the board | Owner's command output; Pi 2 model facts |
| Pi kernel | Pi 3: `7.0.0-1020-raspi`; Pi 2 pending | Owner's `uname -r` output |
| Pi Python | A: Python 3.14.4; full Python suite and mesh demo pass. B: exact version/install/tests pending | Oct 25 SSH checks; MERGER.md |
| Pi networking | Pi 3 has onboard Wi-Fi; Pi 2 B v1.1 needs Ethernet or a USB adapter for SSH, LAN mesh links and any gateway role | Pi model facts; confirm the adapter |
| GPIO device/controller | A: chip0, `pinctrl-bcm2835`; current account requires sudo for metadata access; no lines requested | Oct 25 Python metadata preflight; Pi profile |
| GPIO backend | Official libgpiod v2 Python API, optional Linux-only `gpiod==2.5.0`; installed on A, metadata verified, physical line I/O pending | Owner's accepted backend; Oct 25 live setup |
| Pin numbering | BCM with physical header positions from revision-6 breadboard profile; code mapping checked against JSON reference | Owner's hardware authority update; breadboard guide |
| Existing GPIO reservations | GPIO7/8 claimed by SPI0; keep GPIO7-11 out of project roles while SPI remains enabled; reserve ID GPIO0/1 and exclude internal lines 28-53 | Owner's metadata output; official Pi header/SPI reference |
| Python IDE | PyCharm | Kick-off |
| Edge provider | Cloudflare Workers, free plan | Assignment p. 5; kick-off threat model |
| Physical link | Visible-light laser emitter and matching visible-light receiver preferred; IR emitter/phototransistor as fallback; LDR excluded | Owner, 2026-10-09; supersedes earlier source choices |
| Receiver interface | Comparator with hysteresis, providing digital input to the Pi; no ADC in the selected approach | Owner's 2026-10-09 clarification; circuit validation pending |
| Faro hardware | Soldered final board, removable/header connection, indicators, panic button | Assignment p. 3; kick-off |
| Faro adapter | Library named DispositivoLuzAdaptador | Assignment p. 4 |
| Frame constraints | Fixed 128 serialized bytes before line coding, including preamble/sync, headers, payload, padding and CRC; versioning and rotatable address | Assignment p. 4; owner's Q10 answer |
| Optical encoding | On/off modulation (OOK) with Manchester line coding | Owner's Q10 answer; lecturer recommendation reported by owner |
| Link integrity | Standard CRC-32 for accidental transmission errors; separate cryptographic authentication required | Owner's Q10 answer |
| Medium access | Two Faros, half-duplex explicit transmission turns, one outstanding data frame, acknowledgments, bounded retries and duplicate suppression | Owner's Q11 answer; recovery details pending |
| Privacy | Recognized crypto, E2E encryption, fixed padding, no identifying logs, TTL, panic zeroization | Assignment pp. 4-5 |
| Edge application | Authenticated relay, public rooms, feeds, dead drop, directory, rate limiting | Assignment p. 5 |
| Workflow | Circuit simulation or physical tests before publication; CI is exploratory | Kick-off |
| Git ownership | Owner reviews, commits, and pushes | Owner |
| Hardware dependencies | GPIO backend accepted as an optional dependency; circuit-specific additions await selection | Owner's setup clarification and subsequent backend acceptance |
| CI and license | Deferred until scaffold review | Owner's setup clarification |
| First iteration | Basic breadboard Faro with TX/RX indicators and physical panic; optional RGB debugging branch, with patterns to be decided later | Owner's latest clarification; current breadboard plans |
| Enhancement iteration | LCD screen and speaker/buzzer, only after minimum requirements are met | Owner, 2026-10-09 |
| LCD role | Optional status/short-message aid, not a substitute for the terminal application | Owner's round-1 answer |
| Team distribution | Two people; approved provisional cross-language ownership in the development plan, with effort rebalancing after the first milestone | Owner's Q8 answer |
| Deadline | 2026-10-29, Costa Rica time; submission time pending | Owner's round-1 answer |
| Human capacity | Approximately 10 hours per week per person from 2026-10-09; roughly 29-30 hours each before delivery | Owner's round-1 answer; planning estimate |
| Experience | Both strong in Python, little/no Rust and beginner networking; owner has simple circuit design/build/soldering experience | Owner's round-1 answer |
| First coding approach | Software-first optical simulation while hardware details are unresolved | Owner's round-1 answer |
| Deployment roles | Node and Faro control colocated on each Pi; one Pi also Gateway; extra mesh participants may run on laptops | Owner accepts proposed topology |
| Private application | One-to-one private terminal conversations initially; public topic rooms remain required edge scope | Owner's Q14 answer |
| Laser acceptance | Assumed for planning; use IR fallback if grader rejects the substitution | Owner's round-1 answer |
| Gateway transport/authentication | HTTPS requests use the accepted versioned HMAC contract with environment/key scope, method/path/body, timestamp and nonce; browser public rooms still use WebSockets | Owner's Q12 and Q18 answers; live HTTP/storage integration pending |
| Python cryptography | PyNaCl 1.6.2 now declared; proposal 0002 names Ed25519 signatures, SealedBox hop layers and Box end-to-end; trust bootstrap and key lifecycle remain to be specified | Owner's Q13 answer; proposal 0002 (PROPOSED) |
| Mesh privacy direction | Negotiated onion paths with at least three mesh hops; laptop Nodes supplement the two Pis. Proposal 0002 implements exactly three relays with sender-chosen routes and asks whether that satisfies the direction | Owner's Q15 answer; proposal 0002 (PROPOSED) |
| Procurement status | No emitter, receiver or comparator acquired yet; plans to acquire them Oct 10, draft the remaining order Oct 10, estimated arrival Oct 13 | Owner's Q9 answer, 2026-10-09; dates are estimates |

The starter uses a standard Python src layout, separate language folders,
virtual environments, and pinned Rust/npm tooling as development conveniences.
These are scaffold choices, not newly inferred network protocol rules.

## Pending decisions

- Physical line I/O and optical timing on the assigned breadboard pins.
  A's binding installation/controller/metadata and the current pin profile
  are verified; no physical lines have been requested. Check B during bring-up rather than
  assume its exact versions or chip number match.
- Laser wavelength and matching receiver; emitter modulation interface,
  detector/load conditioning, comparator model, hysteresis thresholds,
  output polarity, and GPIO-compatible output levels. The owner chose a
  hysteresis comparator and digital GPIO input instead of ADC sampling.
  This selects an interface direction, not a verified circuit.
- The owner clarified that the primary receiver must match the visible-light
  laser after checking TEFT4300's IR filtering. TEFT4300 is therefore only a
  candidate for the IR fallback. A BPW34-based conditioned receiver is a
  visible-light candidate from the parts list, not an approved final circuit.
  Resolve the exact receiver before finalizing the hardware profile.
- IR fallback as a spectrally matched emitter/receiver pair. The parts list
  proposes TSAL4400 plus TEFT4300, rather than pairing an IR-filtered detector
  with the red laser.
- Live timing, turn bootstrap/recovery, addressing/rotation, fragmentation,
  and the real node-to-Faro interface. The first-milestone serialized layout,
  CRC coverage, bit convention and simulator retry bounds are accepted. OOK,
  Manchester, CRC-32, fixed 128-byte serialization and half-duplex turns are
  settled; their first-milestone contract is accepted in Q16-Q20.
- Mesh routing/circuit design, packet sizes/padding, PyNaCl primitives,
  directory trust bootstrap, key lifecycle, panic zeroization scope, and
  message TTL values. The library and three-hop direction are settled.
  [Proposal 0002](rfc/0002-mesh-envelope-proposal.md) offers concrete
  numbers (492-byte envelope, six frames, three relays, 190-byte padded
  message, 30-day signed entries) and is implemented for review; its
  section 9 lists the decisions still needed from A and the owner.
- Pi 2 Model B bring-up: exact PiOS release/architecture, Python version,
  PyNaCl and gpiod installation path on ARMv7 (wheels may be unavailable,
  requiring distro packages or source builds), network adapter, gpiochip
  identification and bit timing on the slower CPU. Which Pi hosts the
  Gateway (Pi 3 proposed).
- Live HTTPS route/header contract, atomic durable replay-state integration
  and operation retry/idempotency. Canonical signing, clock tolerance and
  offline replay policy are accepted; future nonce storage uses Durable Objects.
- Atom or RSS, dead-drop storage (KV/D1/R2 or another suitable binding),
  blob size/TTL, delete-on-read behavior, and rate-limit policy.
- Whether the assignment PDF or a kick-off snapshot should be included in
  the repository. Further circuit-specific dependencies, CI, and licensing
  remain deferred.
- Detailed integration contracts beyond the accepted first milestone. Ownership,
  deadline, capacity, role colocation, one-to-one terminal conversations and
  simulation-first development are settled. A language-based team split is
  explicitly ruled out.

The inspected Pi's Ubuntu release/architecture/kernel/Python is confirmed from
the owner's output in [the Pi profile](../hardware/pi-environment.md).
The successful chip/line metadata queries identify the header controller.
Binding installation and current assignments are recorded in the Oct 25
update; physical line I/O and optical timing remain open. Metadata access
does not establish their behavior.
The approved provisional allocation and checkpoints are in
[the development plan](development-plan.md). Time envelopes and checkpoint
dates were accepted in Q19 and remain adjustable targets, not guarantees of
finishing within the capacity estimate.
The owner accepted the bounded first coding milestone in Q16-Q20 and
authorized implementation. Its [v1 contract](rfc/0001-first-milestone-proposal.md)
specifies the complete layout, virtual simulator timing and gateway HMAC
format. Implementation and validation are documented in
[the milestone guide](milestone-1.md). Acceptance of the contract is distinct
from complete assignment or hardware validation.

The current kick-off now expands the gateway and edge-provider threat model,
including provider-visible metadata and residual correlation/collusion risks.
Its remaining RFC choices include zeroization scope, rotation, TTL, rate
limits, and replay prevention. Claims about anonymity and erasure still need
implementation and verification before being treated as guarantees.

## Receiver terminology and verified component facts

A comparator converts the conditioned detector signal into a binary state.
Hysteresis uses separate rising and falling thresholds, reducing repeated
switches when a noisy signal stays near a threshold. This avoids an ADC in
the selected approach, but still requires analog signal conditioning and a
validated digital interface.
The accepted interface direction is recorded in
[ADR 0001](adr/0001-digital-optical-receiver.md).

- [TEFT4300 manufacturer datasheet](https://www.vishay.com/docs/81549/teft4300.pdf):
  daylight-blocking filter matched to 900-950 nm emitters, including TSAL4400.
  It is not the detector choice for the listed 650 nm red laser.
- [BPW34 manufacturer datasheet](https://www.vishay.com/docs/81521/bpw34.pdf):
  a discrete PIN photodiode sensitive from 430-1100 nm, including 650 nm.
  It needs conditioning; sensitivity alone does not establish receiver speed,
  GPIO compatibility, or an adequate signal level in this circuit.
- [Listed laser module](https://www.crcibernetica.com/laser-pointer-module/):
  650 nm emitter. A detector change to TEFT4300 alone does not form a matching
  IR fallback; the fallback needs a compatible IR emitter as well.
