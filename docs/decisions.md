# Sources and implementation decisions

Reviewed on 2026-10-01. These sources describe the project; this repository
setup does not mean their deliverables have been implemented.

## Sources

- [Kick-off Proyecto 1 Redes](https://docs.google.com/document/d/1T8HVIzvNXNovJKPM68aEU6CvZbR9tCTmzVtLurkvUcw/edit?usp=drivesdk),
  sections "Lenguajes seleccionados", "Entorno de desarrollo", "SBC
  seleccionado: Raspberry Pi", "Flujo de trabajo con VCS", and draft threat model.
- Assignment: `Proyecto1-ii2026.pdf`, supplied separately by the repository
  owner. Pages 2-6 describe languages and functional requirements; pages 7-8
  describe deliverables/documentation. The PDF has not been copied into Git.
- Owner's setup request: Rust edge environment, Python nodes, beginner-friendly
  repository, ask about uncertain additions, and no commits before review.

## Confirmed choices and requirements

| Item | Choice or constraint | Source |
| --- | --- | --- |
| Edge language | Rust compiled to WebAssembly | Owner and kick-off |
| Edge IDE | RustRover | Kick-off |
| Node language | Python | Owner |
| Faro control | Python on GNU/Linux, Raspberry Pi, GPIO connection | Kick-off |
| Python IDE | PyCharm | Kick-off |
| Edge provider | Cloudflare Workers, free plan | Assignment p. 5; kick-off threat model |
| Physical link | Visible LED and LDR receiver design | Kick-off; receiver details pending |
| Faro hardware | Soldered final board, removable/header connection, indicators, panic button | Assignment p. 3; kick-off |
| Faro adapter | Library named DispositivoLuzAdaptador | Assignment p. 4 |
| Frame constraints | At most 128 bytes, integrity, medium access, versioning, rotatable address | Assignment p. 4 |
| Privacy | Recognized crypto, E2E encryption, fixed padding, no identifying logs, TTL, panic zeroization | Assignment pp. 4-5 |
| Edge application | Authenticated relay, public rooms, feeds, dead drop, directory, rate limiting | Assignment p. 5 |
| Workflow | Circuit simulation or physical tests before publication; CI is exploratory | Kick-off |
| Git ownership | Owner reviews, commits, and pushes | Owner |
| Hardware dependencies | Deferred until the hardware is selected | Owner's setup clarification |
| CI and license | Deferred until scaffold review | Owner's setup clarification |

The starter uses a standard Python src layout, separate language folders,
virtual environments, and pinned Rust/npm tooling as development conveniences.
These are scaffold choices, not newly inferred network protocol rules.

## Pending decisions

- Exact Raspberry Pi model, GNU/Linux distribution/version, GPIO backend,
  BCM/physical pin convention, and pin assignments.
- LDR conditioning/digitization method and suitable receiver sampling approach;
  the kick-off does not yet define a digital measurement interface.
- Optical line coding, frame layout, checksum/CRC, medium access, timing,
  addressing/rotation, and node-to-Faro interface.
- Mesh routing/circuit design, packet sizes/padding, cryptographic library,
  key lifecycle, panic zeroization scope, and message TTL values.
- Gateway HTTPS or WSS; signature scheme and replay prevention.
- Atom or RSS, dead-drop storage (KV/D1/R2 or another suitable binding),
  blob size/TTL, delete-on-read behavior, and rate-limit policy.
- Test/simulation framework and whether the assignment PDF or a kick-off
  snapshot should be included in the repository. Hardware dependencies, CI,
  and licensing remain deliberately deferred per the owner's clarification.

The kick-off's threat model is a draft. Its edge-provider section ends at
"Cloudflare Worker" and needs expansion. Claims about anonymity and panic
erasure need a precise threat model and verification before being treated as
guarantees. No incomplete source section is silently completed here.
