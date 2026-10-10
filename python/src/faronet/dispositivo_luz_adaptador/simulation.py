"""Two simulated Faros, scripted turns and bounded stop-and-wait retries.

All traffic passes through the Manchester codec. A duplicate fault repeats
the observation of a captured waveform; it does not model physical echoes.
There are no wall-clock sleeps, GPIO operations or network connections.
"""

from dataclasses import dataclass
from enum import Enum

from faronet.dispositivo_luz_adaptador.frame import (
    FRAME_SIZE, MAX_SEQUENCE, Frame, FrameError, FrameType,
)
from faronet.dispositivo_luz_adaptador import manchester

FRAME_UNITS = FRAME_SIZE * 16
ACK_GAP_UNITS = 16
ACK_DEADLINE_UNITS = 3 * FRAME_UNITS
MAX_ATTEMPTS = 3


class LinkError(ValueError):
    """A transmission violates the simulated link's current state."""


class Fault(Enum):
    PASS = "pass"
    DROP = "drop"
    CORRUPT = "corrupt"
    DUPLICATE = "duplicate"
    STALE_SESSION = "stale-session"
    WRONG_SEQUENCE = "wrong-sequence"


@dataclass(frozen=True)
class FaultPlan:
    """One fault per attempt/direction; unspecified attempts pass normally."""

    data: tuple[Fault, ...] = ()
    ack: tuple[Fault, ...] = ()

    def __post_init__(self) -> None:
        for faults in (self.data, self.ack):
            if len(faults) > MAX_ATTEMPTS or any(not isinstance(f, Fault) for f in faults):
                raise LinkError("Fault plans allow at most three faults per direction")

    def at(self, direction: str, attempt: int) -> Fault:
        faults = self.data if direction == "data" else self.ack
        return faults[attempt] if attempt < len(faults) else Fault.PASS


@dataclass(frozen=True)
class TransferResult:
    """Test evidence. Receiver observations are not knowledge of the sender."""

    acknowledged: bool
    attempts: int
    deliveries: tuple[bytes, ...]
    duplicate_observations: int
    elapsed_half_bits: int


@dataclass
class _Endpoint:
    next_send: int = 0
    next_receive: int = 0
    last_received: Frame | None = None


def _waveforms(frame: Frame, fault: Fault) -> tuple[tuple[int, ...], ...]:
    if fault == Fault.DROP:
        return ()
    if fault == Fault.STALE_SESSION:
        session = bytes([frame.session[0] ^ 1]) + frame.session[1:]
        frame = Frame(
            frame.kind, frame.source, frame.destination, session,
            frame.sequence, frame.payload,
        )
    elif fault == Fault.WRONG_SEQUENCE:
        frame = Frame(
            frame.kind, frame.source, frame.destination, frame.session,
            frame.sequence ^ 1, frame.payload,
        )
    waveform = manchester.encode(frame.encode())
    if fault == Fault.CORRUPT:
        damaged = list(waveform)
        # Flip a complete encoded bit: Manchester remains valid; CRC fails.
        damaged[700] ^= 1
        damaged[701] ^= 1
        waveform = tuple(damaged)
    return (waveform, waveform) if fault == Fault.DUPLICATE else (waveform,)


def _read_waveform(waveform: tuple[int, ...]) -> Frame | None:
    if len(waveform) != FRAME_UNITS:
        return None
    try:
        return Frame.decode(manchester.decode(waveform))
    except (FrameError, manchester.ManchesterError):
        return None


class SimulatedLink:
    """Single-threaded link between two neighbors; its controller grants turns."""

    def __init__(self, address_a: bytes, address_b: bytes, session: bytes) -> None:
        Frame(FrameType.DATA, address_a, address_b, session, 0)
        if address_a == address_b:
            raise LinkError("The two neighbors need distinct local addresses")
        self._addresses = (address_a, address_b)
        self._endpoints = {address: _Endpoint() for address in self._addresses}
        self.session = session
        self._used_sessions = {session}
        self.turn = address_a
        self.clock_units = 0
        self._busy = False
        self._needs_reset = False

    def grant_turn(self, address: bytes) -> None:
        """Scripted controller operation, not an autonomous token exchange."""
        if self._busy or self._needs_reset:
            raise LinkError("Finish the exchange or reset the failed session first")
        if address not in self._endpoints:
            raise LinkError("Turn holder must be a link neighbor")
        self.turn = address

    def reset_session(self, session: bytes) -> None:
        if self._busy:
            raise LinkError("Cannot reset an outstanding exchange")
        Frame(FrameType.DATA, *self._addresses, session, 0)
        if session in self._used_sessions:
            raise LinkError("Session reset must not reuse a previous session ID")
        self.session = session
        self._used_sessions.add(session)
        self._endpoints = {address: _Endpoint() for address in self._addresses}
        self.turn = self._addresses[0]
        self._needs_reset = False

    def make_data(self, source: bytes, payload: bytes) -> Frame:
        """Convenience only: transmit() also accepts externally built frames."""
        if source not in self._endpoints:
            raise LinkError("Source must be a link neighbor")
        sequence = self._endpoints[source].next_send
        if sequence > MAX_SEQUENCE:
            raise LinkError("Sequence exhausted; reset the session")
        destination = self._addresses[1] if source == self._addresses[0] else self._addresses[0]
        return Frame(FrameType.DATA, source, destination, self.session, sequence, payload)

    def _receive(self, frame: Frame) -> tuple[Frame, bytes | None, bool] | None:
        if (
            frame.kind != FrameType.DATA
            or frame.session != self.session
            or (frame.source, frame.destination) not in (
                self._addresses, self._addresses[::-1],
            )
        ):
            return None
        receiver = self._endpoints[frame.destination]
        if frame.sequence == receiver.next_receive:
            receiver.last_received = frame
            receiver.next_receive += 1
            return frame.acknowledgment(), frame.payload, False
        if frame == receiver.last_received:
            return frame.acknowledgment(), None, True
        return None

    def transmit(self, serialized: bytes, faults: FaultPlan | None = None) -> TransferResult:
        """Send one validated external DATA frame through encoded waveforms."""
        if self._busy or self._needs_reset:
            raise LinkError("An exchange is outstanding or the session needs reset")
        frame = Frame.decode(serialized)
        if frame != self.make_data(frame.source, frame.payload) or frame.source != self.turn:
            raise LinkError("DATA must match the granted turn, session and next sequence")
        plan = faults or FaultPlan()
        start = self.clock_units
        deliveries = []
        duplicates = 0
        self._busy = True
        try:
            for attempt in range(MAX_ATTEMPTS):
                attempt_start = self.clock_units
                acknowledgments = []
                for waveform in _waveforms(frame, plan.at("data", attempt)):
                    received = _read_waveform(waveform)
                    reception = self._receive(received) if received else None
                    if reception is not None:
                        ack, payload, duplicate = reception
                        acknowledgments.append(ack)
                        duplicates += int(duplicate)
                        if payload is not None:
                            deliveries.append(payload)
                for ack in acknowledgments:
                    for waveform in _waveforms(ack, plan.at("ack", attempt)):
                        received_ack = _read_waveform(waveform)
                        if received_ack is not None and received_ack.is_ack_for(frame):
                            self.clock_units = attempt_start + 2 * FRAME_UNITS + ACK_GAP_UNITS
                            self._endpoints[frame.source].next_send += 1
                            return TransferResult(
                                True, attempt + 1, tuple(deliveries), duplicates,
                                self.clock_units - start,
                            )
                self.clock_units = attempt_start + ACK_DEADLINE_UNITS
            self._needs_reset = True
            return TransferResult(
                False, MAX_ATTEMPTS, tuple(deliveries), duplicates,
                self.clock_units - start,
            )
        finally:
            self._busy = False


class DispositivoLuzAdaptador:
    """A local simulated Node/Faro boundary. No GPIO backend is selected."""

    def __init__(self, link: SimulatedLink, address: bytes) -> None:
        link.make_data(address, b"")
        self._link = link
        self._address = address

    def send_frame(self, serialized: bytes, faults: FaultPlan | None = None) -> TransferResult:
        """Accept a frame constructed by the caller, as the assignment requires."""
        if Frame.decode(serialized).source != self._address:
            raise LinkError("Frame source does not match this adapter")
        return self._link.transmit(serialized, faults)

    def send(self, payload: bytes, faults: FaultPlan | None = None) -> TransferResult:
        return self.send_frame(self._link.make_data(self._address, payload).encode(), faults)
