# Development guide

## Work in the right environment

Use `python/` in PyCharm and `rust/` in RustRover. Each folder has its own
setup guide. From the repository root, change to the language folder before
running its commands. Each developer creates their own virtual environment,
Rust build output, npm dependencies, and local secret files; Git ignores them.

The repository is a monorepo: both languages and shared documentation belong
to one Git repository. IDE settings are local and are not shared.

## Suggested implementation order

1. Complete the threat model and settle the pending hardware/protocol choices
   in `decisions.md` and the RFC before writing the protocol implementation.
2. Implement and measure the GPIO/optical link and DispositivoLuzAdaptador.
3. Build node routing, signed directory entries, private messaging, and privacy
   controls with the approved cryptographic library.
4. Implement the gateway's authenticated relay and public-only forwarding.
5. Implement the Rust public application and its agreed bindings.
6. Complete hardware evidence, three-distance BER/throughput measurements,
   documentation, and privacy verification.

This order is development guidance, not a replacement for the assignment.

## Check changes before sharing

From `python/` with `.venv` active:

```bash
python -m compileall -q src
python -m faronet info
python -m pip check
```

From `rust/` after setup:

```bash
npm run check
npm run dry-run
```

Add behavior tests as real implementations arrive. These initial checks
establish that the environments work; they do not replace the kick-off's
simulation or physical-circuit tests before publication.

## Keep development output private

Prefer static health/status output, anonymous counters, and local synthetic
test data. Do not persist IPs, physical addresses, user identifiers, private
message contents, or secrets in logs or test fixtures. Keep transient runtime
files under the ignored `runtime/` directory if they are later needed.
Discuss the provider's residual visibility in the RFC even with Worker logging
disabled.

## Review without committing

`git status --short` lists changes, including untracked new files. The owner
can inspect those files in the IDE before choosing what to stage and commit.
There are no automatic commit, push, deploy, or CI actions in this scaffold.
