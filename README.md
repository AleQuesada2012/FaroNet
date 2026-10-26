# FaroNet

Beginner-friendly development scaffold for Proyecto 1, Redes de Computadoras,
II semestre 2026. The edge application uses **Rust on Cloudflare Workers**;
nodes, the gateway, and Raspberry Pi Faro control use **Python**.

The first software milestone implements the optical frame/Manchester codec,
a laptop simulator, and matching Python/Rust gateway-authentication helpers.
The second slice adds the node foundation: signed directory entries,
fragmentation, fixed-size onion envelopes and a laptop mesh simulation that
reuses the optical link, following a contract that is still a proposal.
The Student A slice adds a GPIO optical smoke-test adapter with explicit
sender/listener turns, ACK/retry handling, indicators and panic stop, plus
an opt-in local Rust public-room/WebSocket demo. Autonomous optical
negotiation, LAN transport, private terminal chat and live gateway services
remain pending. Start with [the October 26 optical test guide](docs/optical-bringup.md).
See [the milestone guide](docs/milestone-1.md) and
[the node slice guide](docs/milestone-2.md) for demonstrations and tests.

## Repository map

```text
FaroNet/
  rust/                   Rust Cloudflare Worker; open in RustRover
    src/lib.rs            Local starter HTTP handler
    Cargo.toml            Rust dependencies and WASM build settings
    Cargo.lock            Resolved Rust dependency versions
    rust-toolchain.toml   Project-specific Rust version and WASM target
    package.json          Wrangler tooling and development commands
    package-lock.json     Resolved npm tooling versions
    wrangler.jsonc        Reproducible Worker configuration
  python/                 Python package; open in PyCharm
    src/faronet/          CLI and future node/gateway/Faro code
    requirements.txt      Install the local package in a virtual environment
    pyproject.toml        Python package metadata
  docs/                   Source decisions, development guide, RFC workspace
  fixtures/               Shared synthetic protocol/authentication examples
  hardware/               Schematics, BOM, photographs, measurement workspace
  .gitignore              Excludes environments, build output, and secrets
```

## Start with Python

From the repository root on macOS or GNU/Linux:

```bash
cd python
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m faronet --help
python -m faronet info
```

Use Python 3.11 or newer. The optical and gateway modules use the standard
library; the node modules need PyNaCl, installed by `requirements.txt`. All
of it runs without a Raspberry Pi. In PyCharm, open `python/`, choose the interpreter
`python/.venv/bin/python`, and mark `src/` as a Sources Root if needed.
See [the Python guide](python/README.md) before adding runtime dependencies.

## Start with Rust

Run Worker development on the Mac, using its existing repository clone.
Install Rust through [rustup](https://rustup.rs/) and Node.js 22 or newer.
From that clone's repository root:

```bash
cd rust
npm ci
npm run setup
npm run dev
```

The pinned toolchain may download on the first Cargo command. `setup` installs
`worker-build` inside the ignored `rust/.tools/` folder; it does not change your
default Rust toolchain. Node/npm are used for Wrangler tooling; application
logic lives in Rust and compiles to WebAssembly.

In another terminal:

```bash
curl http://127.0.0.1:8787/health
```

Expected result: `FaroNet edge scaffold ready`. Stop the server with Ctrl+C.
In RustRover, open `rust/` and use its `Cargo.toml` project.
See [the Rust guide](rust/README.md) for builds and deployment preparation.

## Before implementing features

Read [decisions and sources](docs/decisions.md), then
[the development guide](docs/development.md) and
[the accepted first-milestone contract](docs/rfc/0001-first-milestone-proposal.md).
Hardware, protocol, crypto, and storage choices still marked pending must be
settled before their implementations.

The tools print status and anonymous synthetic simulation counters.
Never add private keys, IP addresses, physical addresses, user identifiers, or
message contents to persistent debug logs. Real circuit tests and privacy
verification are still required as implementation progresses.

## Version control

Review local changes with `git status --short` and your IDE's diff viewer.
New files remain untracked until you choose to stage them. Run the relevant
local checks and the agreed circuit simulation or physical tests before
publishing changes, as described in the kick-off.

No commit, remote push, or deployment is part of this scaffold setup. The
repository owner will review, commit, and push. The accepted GPIO backend is
an optional Linux dependency; circuit-specific additions await selection.
CI and licensing remain deferred.

Both Pis already have clones: after publication, update those clones with
Git and use their own `python/.venv` environments. Follow
[the clone-based Pi setup](docs/optical-bringup.md#software-preparation-on-each-pi).
Worker dependencies, compilation and tests stay on the Mac.

## Current hardware direction

The team has one Raspberry Pi 3 Model B rev 1.2 running Ubuntu Server and
one Raspberry Pi 2 Model B v1.1 (updated 2026-10-22). Both share the 40-pin
header and BCM numbering; the Pi 2 is 32-bit only, has no onboard Wi-Fi, and
its operating system and Python environment are still to be confirmed. The
inspected Pi 3's environment and controller are recorded in
[the Pi profile](hardware/pi-environment.md). The accepted backend is official
libgpiod v2 with BCM numbering; [the Python guide](python/README.md) explains
the optional installation. Exact pin roles and physical I/O remain pending.
The preferred optical link is a visible-light laser and matching receiver,
with a matching IR emitter/receiver pair as fallback.
The receiver approach uses a comparator with hysteresis and digital GPIO input
without an ADC; its circuit and emitter/detector pairing still need validation.
The first iteration includes the required hardware and RGB debugging. LCD and
speaker/buzzer are enhancements only after minimum requirements are met.
See [the current decisions](docs/decisions.md) for source conflicts and open
choices. Both teammates must contribute meaningful Python and Rust work.
