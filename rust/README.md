# Rust: Cloudflare Workers edge application

Open this folder in RustRover. `src/lib.rs` is the Rust entry point. Cargo
compiles it to WebAssembly; `worker-build` generates the runtime glue and
`build/index.js`, which Wrangler serves. Node.js is development tooling here.

## Setup and local development

Prerequisites: rustup, Node.js 22+, and npm. From `rust/`:

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
starter; all other requests return 404. No message endpoints exist yet.

## Check and build

```bash
npm run check
npm run build
npm run dry-run
```

`check` checks Rust formatting and compiles/lints for the Worker WASM target.
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
- Public topic rooms using Durable Objects and WebSockets.
- Atom or RSS feeds for public topics.
- Fixed-size encrypted dead-drop blobs with TTL and delete-on-read behavior.
- Read-only signed public node directory and rate limiting.

No resource bindings are declared until their implementation and storage
choice are settled. Worker logs and traces are disabled to follow the
assignment's no-records requirement. This does not establish that the
provider cannot observe metadata; address that in the threat model.

The starter follows [Cloudflare's Rust guide](https://developers.cloudflare.com/workers/languages/rust/)
and [workers-rs](https://github.com/cloudflare/workers-rs), with configuration
based on [Wrangler's reference](https://developers.cloudflare.com/workers/wrangler/configuration/).
