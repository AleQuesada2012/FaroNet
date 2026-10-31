# Third slice: CSMA/CA medium access for the Faro link

Status: PROPOSED on 2026-10-31. The owner selected CSMA/CA, the accepted
three-attempt limit and this scope on 2026-10-31. Teammate B review and a
physical two-Faro run are still pending. ASCII-only contract draft, not the
complete FaroNet RFC.

## 1. Purpose

Proposal 0001 accepted the 128-byte frame, ACK matching, three attempts, the
3*F ACK deadline and duplicate suppression, but left "turn grant/handoff,
simultaneous transmit requests and recovery" open and forbade a required
external controller. Until now a human chose one sender and one listener.
This proposal lets both Faros run identical rules and share the optical
medium without roles. The frame format and version are unchanged.

## 2. Timing (units are half-bit intervals; F = 2048)

| Name | Units | Meaning |
| --- | ---: | --- |
| Guard | 16 | Darkness before every frame; also the ACK turnaround (SIFS) |
| DIFS | 64 | Peer darkness required before DATA contention may start |
| Slot | 32 | Backoff granularity; longer than guard + first edge + detection |
| CW | 8, 16, 32 | Backoff slots for attempts 1, 2, 3 |
| ACK deadline | 3*F | From the start of each DATA attempt (accepted, unchanged) |

## 3. Rules

1. An owed ACK is sent first, after only the guard, without carrier sense.
2. DATA needs the peer's light absent for DIFS. The Faro then draws k from
   [0, CW(attempt)) and waits k slots. If the peer's light appears or
   changes before the backoff ends, the backoff is abandoned (a deferral)
   and drawn again after a new DIFS of darkness.
3. One DATA is outstanding. No matching ACK by the deadline (loss or
   collision) starts the next attempt with the next, larger window.
4. After the third attempt the send fails explicitly; delivery is
   uncertain and sending stops for that session (accepted policy).
   Receiving and ACKing the peer continue.
5. A late ACK matching the outstanding DATA is still accepted.
6. Receive rules are the accepted ones: deliver sequential DATA once, re-ACK
   an exact retry of the last DATA, ignore other sessions, peers, gaps and
   changed retries.

Because the guard is shorter than DIFS, the receiver of DATA always wins the
medium for its ACK. After sending its ACK, that receiver has usually
already seen DIFS of darkness, so turns tend to alternate naturally.

```
A:  [guard][======= DATA (F) =======]                [listen for ACK]
B:                                   [guard][== ACK ==][DIFS][backoff][guard][== DATA ==]
          ^ carrier sense: B stays dark while A's light is present
```

## 4. Carrier sense on the breadboard Faro

The receiver is a comparator, so "light present" is a digital level. Busy
means a frame capture is in progress or RX is currently HIGH. Idle-since is
the kernel timestamp of the last accepted RX edge. While a Faro transmits it
ignores RX (its own reflection), and for one half-bit afterwards, because a
peer frame always begins with a 16-unit guard.

The vulnerable window is the guard plus the first rising edge and detection
latency (about 17 units). The 32-unit slot exceeds it, so two Faros that
draw different slots do not collide; equal draws do, and are resolved by
retries with a doubled window.

## 5. Implementation and evidence

- python/src/faronet/dispositivo_luz_adaptador/medium.py: CsmaLink, a
  hardware-independent state machine (poll/on_frame return actions), and
  SimulatedMedium, a two-Faro collision medium in virtual half-bit units.
- python/src/faronet/faro/link.py and the optical-link command drive one
  CsmaLink over GPIO. Both Pis run the same command with swapped addresses.
- Tests: both Faros offering three frames at once across 30 backoff seeds,
  with collisions recovered; carrier-sense deferral and ACK priority; lost
  ACK retry and single delivery; retry exhaustion; stale/foreign frames;
  the GPIO driver loop against a fake peer.

Not yet shown: a physical two-Faro run, measured collision rate, fairness
under sustained load, or behavior with ambient-light noise that keeps the
channel busy.

## 6. Open questions

1. Session bootstrap: the session ID is still copied manually to both Pis.
2. Address rotation (assignment privacy requirement) interacts with session
   and peer identity; not addressed here.
3. More than two Faros sharing one optical path; the rules generalize, but
   hidden terminals are not analyzed.
4. Whether the measured slot and DIFS can shrink after physical timing data.
