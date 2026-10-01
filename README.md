# FaroNet

Beginner-friendly development scaffold for Proyecto 1, Redes de Computadoras,
II semestre 2026. The edge application uses **Rust on Cloudflare Workers**;
nodes, the gateway, and Raspberry Pi Faro control use **Python**.

This repository currently provides development environments and entry points.
The optical protocol, mesh, encryption, GPIO control, and public application
features still need to be designed and implemented.

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
  hardware/               Schematics, BOM, photographs, measurement workspace
  .gitignore              Excludes environments, build output, and secrets
```

## Start with Python

From the repository root on macOS or GNU/Linux:

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m faronet --help
python -m faronet info
```

Use Python 3.11 or newer. The starter uses the standard library, so it works
without a Raspberry Pi. In PyCharm, open `python/`, choose the interpreter
`python/.venv/bin/python`, and mark `src/` as a Sources Root if needed.
See [the Python guide](python/README.md) before adding runtime dependencies.

## Start with Rust

Install Rust through [rustup](https://rustup.rs/) and Node.js 22 or newer.
From the repository root:

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
[the development guide](docs/development.md). Hardware, protocol, crypto, and
storage choices marked pending must be settled before their implementations.

The scaffold prints only static status text and does not store traffic.
Never add private keys, IP addresses, physical addresses, user identifiers, or
message contents to persistent debug logs. Real circuit tests and privacy
verification are still required as implementation progresses.

## Version control

Review local changes with `git status --short` and your IDE's diff viewer.
New files remain untracked until you choose to stage them. Run the relevant
local checks and the agreed circuit simulation or physical tests before
publishing changes, as described in the kick-off.

No commit, remote push, or deployment is part of this scaffold setup. The
repository owner will review, commit, and push. At the owner's request, hardware
dependencies, CI, and licensing are deferred until the scaffold is reviewed.
