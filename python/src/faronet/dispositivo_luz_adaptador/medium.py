"""CSMA/CA medium access for one half-duplex optical neighbor link (proposal 0003).

Hardware-independent: callers pass the current time, when the peer's light
was last seen (idle_since) and whether light is arriving now (busy). Times
are seconds; one half-bit unit lasts `half` seconds. The accepted v1 frame,
ACK matching, duplicate suppression, three attempts and 3*F ACK deadline are
unchanged. No controller grants turns; both Faros run the same rules.
"""

from collections import deque
from dataclasses import dataclass
import random

from faronet.dispositivo_luz_adaptador.frame import (
    MAX_SEQUENCE, PAYLOAD_SIZE, Frame, FrameType,
)
from faronet.dispositivo_luz_adaptador.simulation import (
    ACK_DEADLINE_UNITS, ACK_GAP_UNITS, FRAME_UNITS, MAX_ATTEMPTS,
)

# Every frame is preceded by ACK_GAP_UNITS of darkness (the guard). A receiver
# answers DATA after only that guard; DATA must first see DIFS of darkness, so
# an owed ACK always wins the medium over new DATA.
DIFS_UNITS = 64
SLOT_UNITS = 32
CONTENTION_SLOTS = (8, 16, 32)  # Backoff window for attempts 1-3.


@dataclass(frozen=True)
class Transmit:
    frame: Frame


@dataclass(frozen=True)
class Delivered:
    payload: bytes
    sequence: int


@dataclass(frozen=True)
class SendResult:
    sequence: int
    acknowledged: bool
    attempts: int


class CsmaLink:
    """One Faro's side of a two-Faro link: owed ACKs first, then contended DATA.

    Before DATA the peer's light must have been absent for DIFS plus a random
    backoff. A missing ACK (loss or collision) doubles the backoff window.
    Retry exhaustion fails sending for this session, as accepted; receiving
    and ACKing the peer continue.
    """

    def __init__(self, local: bytes, peer: bytes, session: bytes, half: float, rng=None):
        Frame(FrameType.DATA, local, peer, session, 0)
        if local == peer:
            raise ValueError("Local and peer addresses must differ")
        if not half > 0:
            raise ValueError("Half-bit duration must be positive")
        self.local, self.peer, self.session, self.half = local, peer, session, half
        self.rng = rng or random.SystemRandom()
        self.queue = deque()
        self.next_send = self.next_receive = 0
        self.outstanding = None
        self.attempts = 0
        self.failed = False
        self.ack_timeouts = self.deferrals = self.duplicates = self.ignored = 0
        self.attempts_total = 0
        self.wake_at = 0.0
        self._owed_ack = None
        self._deadline = None
        self._transmit_at = None
        self._quiet_since = None
        self._last_received = None

    @property
    def idle(self) -> bool:
        """Nothing queued, unacknowledged or owed to the peer."""
        return not self.queue and self.outstanding is None and self._owed_ack is None

    def offer(self, payload: bytes) -> None:
        if self.failed:
            raise ValueError("Sending failed for this session; start a fresh session")
        if not isinstance(payload, bytes) or len(payload) > PAYLOAD_SIZE:
            raise ValueError("Payload must be bytes, at most 86 bytes")
        self.queue.append(payload)

    def poll(self, now: float, idle_since: float, busy: bool) -> list:
        """Return what to do at `now` and set wake_at, the next time to poll."""
        unit = self.half
        self.wake_at = now + SLOT_UNITS * unit
        if self._owed_ack is not None:
            ack, self._owed_ack = self._owed_ack, None
            self.wake_at = now
            return [Transmit(ack)]
        actions = []
        if self._deadline is not None:
            if now < self._deadline:
                self.wake_at = self._deadline
                return actions
            self._deadline = None
            self.ack_timeouts += 1
            if self.attempts >= MAX_ATTEMPTS:
                actions.append(SendResult(self.outstanding.sequence, False, self.attempts))
                self.failed = True
                self.outstanding = None
                self.queue.clear()
                return actions
        if self.outstanding is None:
            if self.failed or not self.queue:
                return actions
            if self.next_send > MAX_SEQUENCE:
                raise ValueError("Sequence exhausted; use a fresh session")
            self.outstanding = Frame(
                FrameType.DATA, self.local, self.peer, self.session,
                self.next_send, self.queue.popleft(),
            )
            self.attempts = 0
        # Carrier sense: the peer's light must stay absent through DIFS and the backoff.
        if self._transmit_at is not None and idle_since != self._quiet_since:
            self.deferrals += 1
            self._transmit_at = None
        quiet_from = idle_since + DIFS_UNITS * unit
        if busy or now < quiet_from:
            self.wake_at = now + SLOT_UNITS * unit if busy else quiet_from
            return actions
        if self._transmit_at is None:
            slots = self.rng.randrange(CONTENTION_SLOTS[self.attempts])
            self._quiet_since = idle_since
            self._transmit_at = now + slots * SLOT_UNITS * unit
        if now < self._transmit_at:
            self.wake_at = self._transmit_at
            return actions
        self._transmit_at = None
        self.attempts += 1
        self.attempts_total += 1
        self._deadline = now + ACK_DEADLINE_UNITS * unit
        self.wake_at = self._deadline
        actions.append(Transmit(self.outstanding))
        return actions

    def on_frame(self, frame: Frame, now: float) -> list:
        """Accept a decoded frame; owe an ACK for sequential or retried DATA."""
        if frame.kind == FrameType.ACK:
            if self.outstanding is not None and frame.is_ack_for(self.outstanding):
                # A late ACK still proves the neighbor accepted this exact DATA.
                result = SendResult(self.outstanding.sequence, True, self.attempts)
                self.outstanding = self._deadline = self._transmit_at = None
                self.next_send += 1
                self.wake_at = now
                return [result]
            self.ignored += 1
            return []
        if (frame.source != self.peer or frame.destination != self.local
                or frame.session != self.session):
            self.ignored += 1
            return []
        duplicate = self.next_receive > 0 and frame.sequence == self.next_receive - 1
        if duplicate and frame != self._last_received or (
                not duplicate and frame.sequence != self.next_receive):
            self.ignored += 1
            return []
        self._owed_ack = frame.acknowledgment()
        self.wake_at = now
        if duplicate:
            self.duplicates += 1
            return []
        self._last_received = frame
        self.next_receive += 1
        return [Delivered(frame.payload, frame.sequence)]


class SimulatedMedium:
    """Two CsmaLinks on one optical path, in half-bit units (links use half=1).

    A transmission is ACK_GAP_UNITS of darkness and then FRAME_UNITS of light.
    A Faro misses every frame whose light overlaps its own transmission (the
    driver ignores RX while sending), so simultaneous starts lose both frames.
    `detect` delays when light is reported, `latency` when a frame is decoded,
    and `lose(sender, frame)` injects losses. No GPIO or wall-clock time.
    """

    def __init__(self, a: CsmaLink, b: CsmaLink, detect: float = 2, latency: float = 4,
                 lose=lambda sender, frame: False):
        self.links = (a, b)
        self.detect, self.latency, self.lose = detect, latency, lose
        self.sent = ([], [])  # Per Faro: (driver start, light start, light end, frame)
        self.events = []  # (time, Faro index, action) for every action taken
        self._arrivals = []  # (time, receiver, frame, light start, light end)
        self._offers = []  # (time, Faro index, payload)
        self.now = 0.0

    def offer(self, at: float, index: int, payload: bytes) -> None:
        self._offers.append((at, index, payload))

    def _view(self, index: int, now: float) -> tuple[float, bool]:
        light = [(start, end) for _, start, end, _ in self.sent[1 - index]]
        busy = any(start + self.detect <= now < end for start, end in light)
        return max((end for _, end in light if end <= now), default=0.0), busy

    def _driver_busy(self, index: int, now: float) -> bool:
        return any(begin <= now < end for begin, _, end, _ in self.sent[index])

    def _transmit(self, index: int, frame: Frame) -> None:
        start = self.now + ACK_GAP_UNITS
        end = start + FRAME_UNITS
        self.sent[index].append((self.now, start, end, frame))
        self._arrivals.append((end + self.latency, 1 - index, frame, start, end))

    def _received(self, receiver: int, frame: Frame, start: float, end: float) -> bool:
        overlapped = any(begin < end and start < finish
                         for begin, _, finish, _ in self.sent[receiver])
        return not overlapped and not self.lose(1 - receiver, frame)

    def run(self, until: float) -> float:
        """Advance until both Faros are idle or `until`; return the time reached."""
        while self.now <= until:
            for item in [o for o in self._offers if o[0] <= self.now]:
                self._offers.remove(item)
                self.links[item[1]].offer(item[2])
            for item in sorted((a for a in self._arrivals if a[0] <= self.now),
                               key=lambda a: a[0]):
                self._arrivals.remove(item)
                _, receiver, frame, start, end = item
                if self._received(receiver, frame, start, end):
                    for action in self.links[receiver].on_frame(frame, self.now):
                        self.events.append((self.now, receiver, action))
            for index, link in enumerate(self.links):
                if self._driver_busy(index, self.now):
                    continue
                for action in link.poll(self.now, *self._view(index, self.now)):
                    self.events.append((self.now, index, action))
                    if isinstance(action, Transmit):
                        self._transmit(index, action.frame)
            if (all(link.idle for link in self.links) and not self._arrivals
                    and not self._offers):
                return self.now
            upcoming = [a[0] for a in self._arrivals] + [o[0] for o in self._offers]
            upcoming += [end for sent in self.sent for _, _, end, _ in sent]
            upcoming += [link.wake_at for link in self.links]
            later = [t for t in upcoming if t > self.now]
            if not later:
                return self.now
            self.now = min(later)
        return self.now
