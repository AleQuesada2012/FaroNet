# Rust: Cloudflare Workers edge application

Open this folder in RustRover. `src/lib.rs` is the Rust entry point. Cargo
compiles it to WebAssembly; `worker-build` generates the runtime glue and
`build/index.js`, which Wrangler serves. Node.js is development tooling here.

## Setup and local development

Run these steps on the Mac, from the existing clone's `rust/` folder.
The Pis run the Python side; their cloned `rust/` files do not require a
Pi-side Worker build. Prerequisites: rustup, Node.js 22+, and npm:

```bash
npm ci
npm run setup
npm run dev
```

`rust-toolchain.toml` pins Rust 1.99.0 and installs the WASM target, rustfmt,
and Clippy when rustup first resolves this project. It leaves the global
default toolchain unchanged. `setup` pins worker-build 0.8.7 and puts its
executable in the ignored `.tools/bin/` folder. The initial install compiles
the build tool and can take several minutes.

The development server listens on `http://127.0.0.1:8787` in local mode.
`GET /health` returns a fixed readiness message; `GET /` describes the
starter. Public-room routes are disabled by default. For Student A's local
browser/WebSocket baseline, run on the **Mac**, from `rust/`:

```bash
npm run dev:rooms
```

Open `http://127.0.0.1:8787/rooms` in two browser tabs, connect both to `demo`,
and send synthetic public text. Messages broadcast only to the same room,
including the sender, without server history. In another Mac terminal:

```bash
npm run test:rooms
```

The runtime test checks relay, room isolation, same-origin upgrade policy,
input/rate/connection limits, close/reconnect and HTTP routes. `ws==8.21.0`
is a pinned development-only test client, already present transitively in
the existing Wrangler lockfile. Rust business logic stays in Rust.

`src/public_rooms.rs` exports one hibernating `PublicRoom` Durable Object
per canonical room slug. Message size is capped at 1,024 UTF-8 bytes, with
16 connections per room and five messages per connection per ten seconds.
Only the count/window is attached to a socket; no message history, identity
or IP is written by application code. These are local-demo limits: reconnect
can bypass the per-connection rate budget, and global admission/authentication
and gateway relay integration remain pending. Origin checking is not user
authentication. The opt-in demo must not be treated as a production service.

Wrangler's installed schema supports the declarative `exports` block for
the SQLite-backed class. Editing config, local development and `dry-run`
create no remote resource. `PUBLIC_ROOMS_ENABLED` is `false` in versioned
configuration; `dev:rooms` overrides it only for the local run. Worker code,
toolchains, compilation and tests stay on the Mac, separate from the Pis.

`src/gateway_auth.rs` now implements the accepted offline authentication
contract, including canonicalization, HMAC verification, freshness and a
nonce-store interface. It is not connected to an HTTP route yet. Synthetic
fixtures and the fake store establish policy/interoperability, not deployed
replay protection. Future admission uses a Durable Object coordinator.

## Check and build

```bash
cargo test --locked
npm run check
npm run build
npm run dry-run
```

`check` checks Rust formatting and compiles/lints for the Worker WASM target.
`cargo test` runs authentication tests on your laptop using the root
`fixtures/gateway-auth-v1.json`, also consumed by the Python tests. The Worker
dependency/handler is WASM-specific so these pure tests need no browser,
provider login or WASM test runner. RustCrypto
[hmac 0.13.0](https://docs.rs/hmac/0.13.0/hmac/) and
[sha2 0.11.0](https://docs.rs/sha2/0.11.0/sha2/) provide the cryptographic
operations; application code does not implement HMAC or SHA-256 itself.
`build` generates the Worker bundle. `dry-run` checks Wrangler packaging
without deploying. Keep `Cargo.lock` and `package-lock.json` in Git so your
teammate can install the same resolved dependencies.

## Deployment later

Before an actual deployment, agree on the Cloudflare account, Worker name,
free-plan-compatible resources, authentication, and privacy design. Then run
`npx wrangler login` yourself and, when ready, `npm run deploy`. No account is
selected and no deployment is performed during scaffold setup.

`wrangler.jsonc` is versioned; secret values must not go in it. If local
secrets are later needed, copy `.dev.vars.example` to `.dev.vars` and add the
agreed names. Wrangler loads that file for local development; the example
currently contains comments only. Production secrets require a separate
Wrangler secret operation and are not uploaded from `.dev.vars`.

## Features to design and implement

- Authenticated gateway relay with replay protection.
- Integrate the local public-room baseline with the authenticated gateway.
- Atom or RSS feeds for public topics.
- Fixed-size encrypted dead-drop blobs with TTL and delete-on-read behavior.
- Read-only signed public node directory and rate limiting.

The local public-room binding is declared; no live resource was provisioned.
The future replay-store direction is accepted; its live integration remains
later work. Worker logs
and traces are disabled to follow the
assignment's no-records requirement. This does not establish that the
provider cannot observe metadata; address that in the threat model.

The starter follows [Cloudflare's Rust guide](https://developers.cloudflare.com/workers/languages/rust/)
and [workers-rs](https://github.com/cloudflare/workers-rs), with configuration
based on [Wrangler's reference](https://developers.cloudflare.com/workers/wrangler/configuration/).
The new slice also follows [WebSocket hibernation](https://developers.cloudflare.com/durable-objects/best-practices/websockets/)
and [declarative class exports](https://developers.cloudflare.com/durable-objects/reference/durable-objects-migrations/),
checked against workers-rs 0.8.7 and Wrangler 4.149.0 installed in this project.
