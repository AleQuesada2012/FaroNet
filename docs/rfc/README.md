# RFC workspace

Create the Faro physical protocol and FaroNet RFC here after the design
decisions are agreed. The specification requires the RFC, including diagrams,
to contain ASCII only. This README is not the RFC.

[Accepted first-milestone contract](0001-first-milestone-proposal.md) is a bounded
contract accepted in Q16-Q20 on 2026-10-09. It distinguishes the first
implementation slice from future design work; it is not the complete assignment RFC.

[Proposal 0002](0002-mesh-envelope-proposal.md) is Teammate B's PROPOSED
contract for identities, signed directory entries, fragmentation, fixed-size
onion envelopes and padded private messages. It is implemented in the node
package for review and is not accepted yet.

The future RFC must document versioning, frame/packet fields and explicit
lengths, integrity, medium access, addressing, routing, and the threat model,
with Privacy Considerations and Security Considerations. The assignment
points to RFC 9110, RFC 7322, and RFC 6973 as references.

Keep source documentation in Markdown or LaTeX. Generated PDFs can go under
the ignored repository-root `output/` directory during development; final
submission packaging should be agreed separately.
