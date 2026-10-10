# Development guide

## Work in the right environment

Use `python/` in PyCharm and `rust/` in RustRover. Each folder has its own
setup guide. From the repository root, change to the language folder before
running its commands. Each developer creates their own virtual environment,
Rust build output, npm dependencies, and local secret files; Git ignores them.

The repository is a monorepo: both languages and shared documentation belong
to one Git repository. IDE settings are local and are not shared.

## Suggested implementation order

1. Use the threat model and settle the software contracts in `decisions.md`
   and the RFC. Prototype the optical protocol and adapter with a simulator
   while GPIO and receiver details remain pending. The inspected Pi's
   software environment is recorded in `hardware/pi-environment.md`.
2. Bring up and measure the real GPIO/optical link once its hardware profile
   is confirmed, keeping the simulator usable for repeatable software tests.
3. Build node routing, signed directory entries, terminal private chat, and privacy
   controls with the approved cryptographic library.
4. Implement the gateway's authenticated relay and public-only forwarding.
5. Implement the Rust public application and its agreed bindings.
6. Complete hardware evidence, three-distance BER/throughput measurements,
   documentation, and privacy verification.

This order is development guidance, not a replacement for the assignment.
See [the development plan](development-plan.md) for the deadline, capacity,
and approved provisional cross-language ownership. Both teammates contribute
Python and Rust; simulator success does not establish physical-link performance.

## Check changes before sharing

From `python/` with `.venv` active:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
python -m faronet info
python -m pip check
```

From `rust/` after setup:

```bash
cargo test --locked
npm run check
npm run dry-run
```

The first-milestone tests exercise protocol failures and shared authentication
fixtures. Continue adding meaningful behavior tests with later features.
These checks do not replace physical-circuit tests before publication.
See [the milestone guide](milestone-1.md) for demonstrations and limitations.

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
