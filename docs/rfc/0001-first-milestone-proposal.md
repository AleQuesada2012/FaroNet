# First software milestone: optical codec and relay authentication

Status: ACCEPTED on 2026-10-09 (owner answers Q16-Q20).
Drafted: 2026-10-09. ASCII-only contract draft, not the complete FaroNet RFC.

## 1. Purpose and accepted direction

Build a testable foundation on laptops while optical hardware details are
pending. The inspected Pi's environment is recorded in
../../hardware/pi-environment.md. The accepted directions are Manchester over on/off
light, fixed 128-byte serialized frames, CRC-32, half-duplex turns with ACKs
and bounded retries, and HTTPS gateway HMAC-SHA-256 authentication.

The owner accepted this bounded contract and authorized its implementation.
Future-work boundaries remain explicit; acceptance does not imply the full
assignment is implemented. Current project decisions are in ../decisions.md.
Implementation entry points and validation commands are in ../milestone-1.md.

## 2. Accepted complete serialized frame

ACCEPTED: this is 128 bytes BEFORE Manchester coding. It includes all
preamble, sync, header, payload, padding and CRC bytes. Encoding the entire
frame produces 2,048 half-bit symbols. An encoded waveform's length is not
an additional payload allowance.

All multi-byte integer fields use unsigned big-endian serialization. Local
addresses and the session ID are opaque 8-byte values. They describe this
neighbor link, not the original sender or final mesh destination.

| Byte offsets | Size | Field | Accepted rule |
| --- | ---: | --- | --- |
| 0-3 | 4 | Preamble | 55 55 55 55 (hex) |
| 4-5 | 2 | Sync | D3 91 (hex) |
| 6 | 1 | Version | 1 |
| 7 | 1 | Type | 1 = DATA; 2 = ACK |
| 8-15 | 8 | Local source | Immediate transmitting Faro |
| 16-23 | 8 | Local destination | Immediate receiving Faro |
| 24-31 | 8 | Link session | Distinguishes a link incarnation |
| 32-35 | 4 | Sequence | DATA identifier; ACK echoes DATA sequence |
| 36-37 | 2 | Payload length | DATA: 0-86; ACK: 0 |
| 38-123 | 86 | Payload and padding | Payload, followed by zero padding |
| 124-127 | 4 | CRC | CRC-32 over bytes 6-123 inclusive |

Reject incorrect frame length, preamble/sync, version/type, payload length,
nonzero padding, nonempty ACK payload or CRC. CRC covers the header and
entire padded payload. Preamble/sync are checked separately for exact values.

An ACK swaps the DATA frame's local addresses and echoes its session and
sequence. A link ACK means that one neighbor accepted that frame; it is not
an end-to-end message-delivery receipt.

ACCEPTED CRC variant: CRC-32/ISO-HDLC, polynomial 0x04C11DB7 (reflected form
0xEDB88320), initial register 0xFFFFFFFF, reflected input/output, final XOR
0xFFFFFFFF. The check value for ASCII "123456789" is 0xCBF43926. Python's
zlib.crc32(data) already implements its initial/final complements; do not
manually add them. Its numeric result is serialized big-endian for this
FaroNet format. CRC reflection does not define the waveform's bit order.

ACCEPTED Manchester convention: transmit each byte most-significant bit
first; encode 0 as [OFF, ON] and 1 as [ON, OFF]. One virtual time unit is one
half-bit interval. These logical light states are independent of a future
active-low comparator or GPIO pin setting.

This milestone carries at most 86 opaque payload bytes per DATA frame.
Fragmentation/reassembly is a later contract and will consume some of that
space for metadata. Oversized payloads must fail explicitly here. Do not
silently truncate or claim support for full encrypted mesh packets yet.

## 3. Accepted simulator scope and reliability

The simulator emits Manchester levels with virtual durations and decodes
them using a known half-bit clock and aligned frame start. It can inject
signal corruption, lost frames, lost ACKs and duplicates. It is a codec/link
exercise; clock acquisition, drift recovery and physical GPIO capture remain
future work.

A duplicate fault repeats a decoder observation of the captured waveform;
it does not model physical optical reflections or their propagation delay.

ACCEPTED reliability policy:

- A simulator controller grants A-to-B and then B-to-A transmission turns.
  These are explicit half-duplex turns, not a decentralized turn protocol.
- Only the turn holder starts DATA; the receiver can answer with its ACK.
- One DATA frame is outstanding. Three total attempts means the original
  transmission plus at most two retries.
- Let F = 2,048 virtual half-bit units, the complete encoded frame duration.
  The ACK begins 16 units after DATA finishes. An ACK deadline is 3*F units
  after the DATA attempt starts, with zero simulated propagation delay.
  Each retry gets a new deadline and keeps the same DATA sequence.
- Accept an ACK only if its neighbor addresses, session and sequence match
  the outstanding DATA. A stale/unrelated ACK does not advance the sender.
- Re-ACK a duplicate DATA but deliver its payload only once. Corrupt DATA is
  not delivered or acknowledged. Retry exhaustion is an explicit failure with uncertain neighbor delivery;
  reset the scripted session before further transmissions.
- Simulator sequences increase within a session without wrapping. A new
  scripted session clears link state; old-session traffic cannot complete a
  new transfer. The controller cannot reuse a previously used session ID.
  Simulated IDs/session values are fixtures, not security keys.

These defaults establish neither a measured bitrate nor a real turnaround
delay. Live bootstrap, turn grant/handoff, simultaneous transmit requests,
recovery after lost control messages and address/session rotation must be
agreed before the decentralized link implementation. No local process is
allowed to become a required external controller for the final Faro link.

## 4. Accepted gateway authentication contract

Python constructs a request; Rust validates the same canonical bytes. Use
synthetic secrets and bodies in this milestone. Do not add a deployed route,
real gateway secret, provider binding or external resource yet.

ACCEPTED canonical ASCII signing input, including the final LF:

```text
FARONET-GATEWAY-HMAC-V1\n
<audience>\n
<gateway-key-id>\n
<method>\n
<path>\n
<timestamp>\n
<nonce>\n
<body-sha256>\n
```

The displayed "\n" means one LF byte (0A), not two literal characters.
Use HMAC-SHA-256 over that input and transmit the full 32-byte MAC as 64
lowercase hex characters. Compare MACs with the crypto library's constant-
time verification facility.

ACCEPTED field rules:

- Audience and gateway-key-id: 1-64 ASCII letters/digits, hyphen or underscore;
  configured by the verifier, never trusted just because the client sent them.
  Each gateway/environment has a distinct secret, at least 32 random bytes.
- Method: exact uppercase GET or POST for the offline fixture contract.
- Path: absolute ASCII path; no query/fragment, percent encoding, repeated
  slash, dot segments or trailing slash except the root. Components contain
  only ASCII letters/digits, hyphen or underscore. Future route names and
  HTTP adapters must preserve these semantics or version the contract.
- Timestamp: canonical unsigned decimal Unix seconds; no leading zero
  except "0", sign, fraction or whitespace. Bound it to unsigned 64-bit.
- Nonce: 16 cryptographically random bytes, encoded as 32 lowercase hex
  characters. Tests use explicit synthetic values instead of randomness.
- Body hash: SHA-256 of the exact transmitted body bytes, encoded as 64
  lowercase hex characters. Sign once and send those same bytes; do not
  reserialize JSON after signing. GET fixtures have an empty body.
- Reject line breaks or noncanonical scalar fields before canonicalization.
- Reject a body over a 65,536-byte authentication cap. This is an
  upper bound for these helpers, not an approved application/blob size.
- Future HTTP adapters must constrain or authenticate headers that change
  body interpretation, including content type/encoding. Route contracts and
  HTTP header names are outside this offline milestone.

This is FaroNet's custom HMAC format, informed by HTTP-signature guidance.
It is not a claim of implementing RFC 9421's complete protocol.

## 5. Accepted freshness and replay policy

ACCEPTED clock policy: accept only if timestamp-60 <= now <= timestamp+60
in integer Unix seconds. Use widened/checked arithmetic, without integer
underflow or wrapping. The 60-second value is a project default, not a
standard requirement. Future gateways must have a usable synchronized clock.

Verify syntax, expected audience/key, route policy, body bound/hash, MAC and
freshness BEFORE nonce admission. Authentication is not authorization to
use arbitrary routes; a live adapter also needs an allowed-operation policy.
In the nonce store, recheck freshness and
atomically claim (audience, gateway-key-id, nonce); reject a still-live claim.
Retain it through timestamp+60; it can expire only when now > timestamp+60.
An initially accepted future-dated request can therefore need 120 seconds of
retention from admission. A blanket 60-second TTL from admission is wrong.

Storage failure must reject the request, and side effects happen only after
successful admission. Repeating an admitted nonce fails even if the original
response was lost. At-most-once admission does not guarantee the operation
completed; application retries/idempotency need a later contract.

The first milestone uses an explicitly fake store and injected clock, testing
policy only. A Worker-global in-memory cache cannot provide production replay
protection across isolates/restarts. ACCEPTED future implementation: one
SQLite-backed Durable Object coordinator per gateway key scope, using atomic
durable storage. Store only minimal nonce/expiry state, not traffic bodies,
IPs or User-Agent values. This future storage direction is accepted; deployment still needs a live
storage contract and concurrency/expiry tests before replay protection is claimed.

## 6. First-milestone threat and privacy boundaries

Treat received frames and requests as untrusted. Malformed data, bit errors,
forged requests, expired/future requests, duplicate nonces and exhausted
retries must produce bounded, explicit failures rather than delivery.

CRC protects against accidental link errors, not malicious frame forgery.
The link's local IDs, lengths and activity remain observable. HMAC protects
request integrity/authenticity for parties that share the secret; compromise
of either gateway or verifier permits forgery for that key. Neither mechanism
provides end-to-end confidentiality or anonymity.

Use only synthetic data in tests and the simulator demo. Do not log request
bodies, keys, addresses, MACs or nonces; print static status or anonymous test
counters. Fake-store tests do not establish deployed replay protection or
provider erasure. Cloudflare can observe gateway connection metadata even
when application logs are disabled.

The kick-off's threat model and ../decisions.md remain the basis for later
live features. Before those slices, specify identity/directory trust,
recognized PyNaCl primitives, onion negotiation, fixed-size mesh envelopes,
fragmentation limits, TTL, key rotation and the achievable panic cleanup
boundary. Python-managed keys cannot be assumed to have every RAM copy
securely overwritten. Full privacy/security claims require separate evidence.

## 7. Accepted acceptance evidence

- Optical frame golden vector, min/max payload round trips, oversized payload
  rejection, bad length/version/type/padding, and header/payload CRC damage.
- CRC known-answer "123456789" = 0xCBF43926; Manchester bit vectors, all byte
  values and repeated 00/FF/55/AA; invalid/truncated Manchester pair rejection.
- Encoded-waveform exchange A-to-B and B-to-A; lost DATA, lost/final ACK,
  duplicate delivery suppression, stale ACK, retry exhaustion and reset.
- Shared synthetic Python/Rust canonical-input, body-hash and HMAC vectors;
  changing method/path/body/time/nonce/audience/key must fail validation.
- Noncanonical/query input rejection, clock-window boundary tests, future
  timestamp nonce retention, duplicate admission and fake-store failure.
- Python tests using the standard-library unittest runner; Rust unit tests
  for pure functions plus the existing formatting/build checks. A small CLI
  demonstration remains usable without Raspberry Pi hardware.

No new GPIO dependency, PyNaCl feature implementation, full relay endpoint,
mesh/chat, public room/feed, dead-drop service or deployment is included in
this first slice. Those remain required later work, except the already
deferred LCD/speaker/buzzer enhancements. CI and license stay deferred.

## 8. Reference facts

- CRC parameters: AUTOSAR CRC Library, section 7.2.3.1:
  https://www.autosar.org/fileadmin/standards/R22-11/CP/AUTOSAR_SWS_CRCLibrary.pdf
- Python CRC API:
  https://docs.python.org/3/library/zlib.html#zlib.crc32
- Manchester mappings (both conventions exist):
  https://docs.silabs.com/connect-stack/4.2.1/proprietary-radio-configurator-guide/03-radio-parameters#manchester-code-mapping
- Stop-and-wait and final-ACK loss precedent:
  https://www.rfc-editor.org/rfc/rfc1350
- HTTP signature security considerations:
  https://www.rfc-editor.org/rfc/rfc9421
- Exact HTTP content digest semantics:
  https://www.rfc-editor.org/rfc/rfc9530
- Python HMAC and secure random tokens:
  https://docs.python.org/3/library/hmac.html
  https://docs.python.org/3/library/secrets.html
- Durable Object consistency/transactions and free-plan availability:
  https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
  https://developers.cloudflare.com/durable-objects/platform/pricing/
- Python secret objects and underlying secure-memory limitations:
  https://github.com/pyca/pynacl/blob/main/src/nacl/secret.py
  https://libsodium.gitbook.io/doc/memory_management
