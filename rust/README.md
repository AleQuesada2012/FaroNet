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
`GET /health` returns a fixed readiness message; `GET /` is a short public
landing page. Public-room routes are disabled by default. For Student A's local
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
input/rate/connection limits, close/reconnect, HTTP routes, the Atom feeds
and the per-client request limit. Start a fresh `dev:rooms` before running
it, because it uses up the minute's request budget at the end. `ws==8.21.0`
is a pinned development-only test client, already present transitively in
the existing Wrangler lockfile. Rust business logic stays in Rust.

### Topic feeds and rate limiting

Every public topic has an Atom 1.0 feed at `GET /rooms/{topic}/feed.atom`
(same gating as the rooms). The room's Durable Object stores the last 20
public messages for at most 24 hours: sequence number, publication time
rounded down to the minute, and text. No identity, address or connection
data is stored. An alarm erases entries when their TTL ends even if nobody
reads the feed again. Text is XML-escaped and served as `type="text"`.

Every route except `/health` passes a per-client limit of 60 requests per
60 seconds; excess requests get `429` with `Retry-After: 60`. The
`EdgeLimiter` Durable Object is named by a SHA-256 of the client address
(`CF-Connecting-IP`) and keeps its fixed-window counter **in memory only**,
so nothing about the client is written to storage or logs. Hashing an IPv4
address is not anonymization, and the provider still sees addresses; the
threat model must say so. A Durable Object was chosen over the Workers rate
limiting binding because its free-plan availability was not confirmed and
SQLite-backed Durable Objects are explicitly available on the free plan.
Limits reset if the object is evicted, which errs toward admitting traffic.

`src/public_rooms.rs` exports one hibernating `PublicRoom` Durable Object
per canonical room slug. Message size is capped at 1,024 UTF-8 bytes, with
16 connections per room and five messages per connection per ten seconds.
Only the count/window is attached to a socket; apart from the feed entries
above, no message history, identity or IP is written by application code. These are local-demo limits: reconnect
can bypass the per-connection rate budget, and browsers are not
authenticated (the Gateway is; see below). Origin checking is not user
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

## Deployment (Cloudflare Workers free plan)

Live: <https://faronet-edge.faronet.workers.dev>, deployed by the owner on
2026-10-31 with `npm run deploy`; `npm run smoke` passed against it.

The versioned `wrangler.jsonc` is the deployment configuration. It keeps
`PUBLIC_ROOMS_ENABLED` false so plain local runs stay closed; `npm run
deploy` and `npm run dry-run` pass `--var PUBLIC_ROOMS_ENABLED:true`, so the
deployed Worker serves the rooms and feeds. Observability, logs and traces
are disabled. Both Durable Object classes use the SQLite backend, the only
one on the free plan. No secrets are needed yet.

Run from `rust/` on the Mac:

```bash
npx wrangler login
```

```bash
npm run dry-run
```

```bash
npm run deploy
```

`wrangler login` opens a browser for the account owner; do it yourself.
Deploy prints the public URL, `https://faronet-edge.<subdomain>.workers.dev`
(the subdomain belongs to the account). Then run the light smoke test
against it; it sends one synthetic public message to a throwaway room:

```bash
npm run smoke -- https://faronet-edge.<subdomain>.workers.dev
```

Record the URL in the project documentation; it is a required deliverable.
To take the public side down, `npx wrangler delete` removes the Worker.

`wrangler.jsonc` is versioned; secret values must not go in it. If local
secrets are later needed, copy `.dev.vars.example` to `.dev.vars` and add the
agreed names. Wrangler loads that file for local development; the example
currently contains comments only. Production secrets require a separate
Wrangler secret operation and are not uploaded from `.dev.vars`.

## Features to design and implement

- Authenticated gateway relay with replay protection.
- Integrate the local public-room baseline with the authenticated gateway.
- Fixed-size encrypted dead-drop blobs with TTL and delete-on-read behavior.
- Read-only signed public node directory.

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

## Gateway relay and dead drop

`src/gateway.rs` adds the routes of RFC FN-1 Sections 6, 7.1 and 7.6:

- `POST /gateway/rooms/{topic}` publishes a Gateway's public text into a
  topic (connections and feed), like a browser message.
- `POST /gateway/drop/{id}` stores one 1024-byte opaque blob in an empty
  slot (64 lowercase hex digits); `GET` reads and deletes it. Blobs expire
  after 24 hours. Each slot is a `DeadDrop` SQLite Durable Object.

Every request carries `X-FaroNet-Key`, `X-FaroNet-Timestamp`,
`X-FaroNet-Nonce` and `X-FaroNet-Signature` (the HMAC of
`gateway_auth.rs`). The Worker checks them and the body, then claims the
nonce in the `GatewayReplay` SQLite Durable Object (nonce and expiry
only), failing closed. Until `GATEWAY_SECRET` exists every gateway route
answers 404. Local check, on the Mac from `rust/`, with a throwaway secret
built into the scripts:

```bash
npm run dev:gateway
```

```bash
npm run test:gateway
```

To enable it on the deployment (owner's step), generate a secret, store
it in Cloudflare, deploy, and give the same value to the Gateway Pi as
`FARONET_GATEWAY_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

```bash
npx wrangler secret put GATEWAY_SECRET
```

```bash
npm run deploy
```

The Python side is `python -m faronet gateway-publish`, `drop-secret`,
`drop-put` and `drop-take` (`python/src/faronet/gateway/client.py`).
