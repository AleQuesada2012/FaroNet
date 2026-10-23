# Shared protocol examples

These are public **synthetic** test vectors, with fake addresses, sessions,
secrets and payloads. Never use their secrets as real gateway credentials.

- `optical-v1.json`: exact serialized DATA/ACK bytes and CRC, before Manchester.
- `gateway-auth-v1.json`: exact request/body bytes, canonical input, SHA-256
  and HMAC results; consumed unchanged by Python and Rust tests.
- `directory-v1.json`: a deterministic signed directory entry from public
  synthetic seeds (proposal 0002); the Rust public directory can verify it.
- `mesh-fragment-v1.json`: one synthetic 492-byte envelope split into six
  86-byte Faro payloads with the 4-byte fragment header (proposal 0002).

The gateway examples include binary content, an empty GET body, Unix time
zero and the unsigned 64-bit timestamp maximum. The canonical string includes
its final LF. Change vectors only with an explicit contract change; do not
regenerate expected outputs automatically during tests.
