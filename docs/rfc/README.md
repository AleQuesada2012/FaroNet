# RFC workspace

**The project RFC is [faronet-rfc.txt](faronet-rfc.txt)** (RFC FN-1): the
Faro physical and link protocol, CSMA/CA medium access, the FaroNet mesh,
gateway authentication and the public edge, with Privacy and Security
Considerations and an implementation-status appendix. It is plain ASCII,
72 columns, in RFC 7322 style, as the assignment requires. The numbered
proposals below are the design records it consolidates. This README is not
the RFC.

[Accepted first-milestone contract](0001-first-milestone-proposal.md) is a bounded
contract accepted in Q16-Q20 on 2026-10-09. It distinguishes the first
implementation slice from future design work; it is not the complete assignment RFC.

[Proposal 0002](0002-mesh-envelope-proposal.md) is Teammate B's PROPOSED
contract for identities, signed directory entries, fragmentation, fixed-size
onion envelopes and padded private messages. It is implemented in the node
package for review and is not accepted yet.

[Proposal 0003](0003-optical-medium-access-proposal.md) is the PROPOSED CSMA/CA
medium access for the Faro link: carrier sense, random backoff and ACK
priority, with the accepted frame and three-attempt policy unchanged. The
owner selected its design choices on 2026-10-31; a physical two-Faro run and
Teammate B review are pending.

The future RFC must document versioning, frame/packet fields and explicit
lengths, integrity, medium access, addressing, routing, and the threat model,
with Privacy Considerations and Security Considerations. The assignment
points to RFC 9110, RFC 7322, and RFC 6973 as references.

Keep source documentation in Markdown or LaTeX. Generated PDFs can go under
the ignored repository-root `output/` directory during development; final
submission packaging should be agreed separately.
