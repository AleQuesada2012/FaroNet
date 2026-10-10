# Shared protocol examples

These are public **synthetic** test vectors, with fake addresses, sessions,
secrets and payloads. Never use their secrets as real gateway credentials.

- `optical-v1.json`: exact serialized DATA/ACK bytes and CRC, before Manchester.
- `gateway-auth-v1.json`: exact request/body bytes, canonical input, SHA-256
  and HMAC results; consumed unchanged by Python and Rust tests.

The gateway examples include binary content, an empty GET body, Unix time
zero and the unsigned 64-bit timestamp maximum. The canonical string includes
its final LF. Change vectors only with an explicit contract change; do not
regenerate expected outputs automatically during tests.
