"""Manually directed physical smoke-test adapter using the accepted v1 frames.

The operator grants turns by running one sender and one listener. This is
not the final autonomous mesh medium-access protocol. Payloads stay opaque.
"""

from dataclasses import dataclass
import time
from typing import Protocol

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameType, MAX_SEQUENCE


class PhysicalLinkError(RuntimeError):
    """A physical transfer failed; delivery may be uncertain."""


class FrameIO(Protocol):
    frame_seconds: float

    def transmit(self, frame: Frame) -> None: ...
    def receive(self, timeout: float) -> Frame | None: ...
    def guard(self) -> None: ...
    def clear(self) -> None: ...


@dataclass(frozen=True)
class PhysicalTransfer:
    acknowledged: bool
    attempts: int
    elapsed_seconds: float


class PhysicalDispositivoLuzAdaptador:
    """One neighbor/session; bounded retries and stop-and-wait duplicate handling."""

    def __init__(self, io: FrameIO, local: bytes, peer: bytes, session: bytes):
        Frame(FrameType.DATA, local, peer, session, 0)
        if local == peer:
            raise ValueError("Local and peer addresses must differ")
        self.io, self.local, self.peer, self.session = io, local, peer, session
        self.next_send = 0
        self.next_receive = 0
        self.failed = False
        self.duplicates = 0
        self.ignored = 0
        self._last_received = None

    def send_frame(self, serialized: bytes) -> PhysicalTransfer:
        """Accept an external DATA frame; accept only its matching ACK."""
        frame = Frame.decode(serialized)
        if self.failed or frame != Frame(
            FrameType.DATA, self.local, self.peer, self.session,
            self.next_send, frame.payload,
        ):
            raise PhysicalLinkError("Wrong source, peer, session, sequence or failed session")
        start = time.monotonic()
        for attempt in range(1, 4):
            self.io.guard()
            attempt_start = time.monotonic()
            try:
                self.io.transmit(frame)
            except BaseException:
                self.failed = True
                raise
            deadline = attempt_start + 3 * self.io.frame_seconds
            while (remaining := deadline - time.monotonic()) > 0:
                ack = self.io.receive(remaining)
                if ack is None:
                    break
                if ack.is_ack_for(frame):
                    self.next_send += 1
                    return PhysicalTransfer(True, attempt, time.monotonic() - start)
                self.ignored += 1
        self.failed = True
        return PhysicalTransfer(False, 3, time.monotonic() - start)

    def send(self, payload: bytes) -> PhysicalTransfer:
        if self.failed:
            raise PhysicalLinkError("Session failed or cleared; start a fresh session")
        if self.next_send > MAX_SEQUENCE:
            raise PhysicalLinkError("Sequence exhausted; use a fresh session")
        return self.send_frame(Frame(
            FrameType.DATA, self.local, self.peer, self.session,
            self.next_send, payload,
        ).encode())

    def receive(self, timeout: float) -> bytes | None:
        """ACK sequential DATA; re-ACK exact retries without redelivery."""
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            frame = self.io.receive(remaining)
            if frame is None:
                return None
            if (frame.kind != FrameType.DATA or frame.source != self.peer
                    or frame.destination != self.local or frame.session != self.session):
                self.ignored += 1
                continue
            duplicate = self.next_receive > 0 and frame.sequence == self.next_receive - 1
            if duplicate:
                # Same sequence with changed content is not the original DATA retry.
                if frame != self._last_received:
                    self.ignored += 1
                    continue
            elif frame.sequence != self.next_receive:
                self.ignored += 1
                continue
            self.io.guard()
            self.io.transmit(frame.acknowledgment())
            if duplicate:
                self.duplicates += 1
                continue
            self._last_received = frame
            self.next_receive += 1
            return frame.payload
        return None

    def clear(self) -> None:
        """Drop local session state; this does not promise Python memory erasure."""
        self.failed = True
        self.local = self.peer = self.session = b""
        self._last_received = None
        self.io.clear()
