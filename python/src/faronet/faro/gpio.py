"""Optional Linux libgpiod v2 backend. Importing this module never opens GPIO."""

from collections import deque
from contextlib import contextmanager
import gc
import os
import time

from faronet.dispositivo_luz_adaptador.frame import Frame
from faronet.dispositivo_luz_adaptador.manchester import encode
from faronet.faro.profile import CONTROLLER, LED_RX, LED_TX, PANIC, PINS, RX, TX, inspect_chip
from faronet.faro.waveform import EdgeDecoder, FRAME_SYMBOLS, GUARD_SYMBOLS


# Sleep until this close to each TX deadline, then busy-wait: sleep overshoot,
# not the GPIO write, is what makes symbols late.
SPIN_NS = 1_000_000
# Visible sign of a panic (RFC FN-1 4.8): both indicator LEDs blink together, the IR stays off.
PANIC_BLINKS = 3
PANIC_BLINK_SECONDS = 0.15
REALTIME_PRIORITY = 50


@contextmanager
def _on_air():
    """Best effort while a waveform is on air: SCHED_FIFO (needs root) and no GC pauses.

    Yields whether SCHED_FIFO actually took effect.
    """
    previous = None
    try:
        previous = os.sched_getscheduler(0), os.sched_getparam(0)
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(REALTIME_PRIORITY))
    except (AttributeError, OSError):  # Not Linux, or not running as root.
        previous = None
    collecting = gc.isenabled()
    gc.disable()
    try:
        yield previous is not None and os.sched_getscheduler(0) == os.SCHED_FIFO
    finally:
        if collecting:
            gc.enable()
        if previous is not None:
            os.sched_setscheduler(0, *previous)


PANIC_EXIT = 3  # Exit status of an optical command stopped by panic; the chat erases its Node on it.


class PanicStop(RuntimeError):
    """The physical active-low panic input was pressed; restart explicitly."""


class TimingError(RuntimeError):
    """Linux could not maintain the configured waveform timing."""


class GpioFrameIO:
    """One exclusive line request; outputs start LOW and turn off on close."""

    def __init__(self, path: str, half_bit_ms: float = 5, rx_inverted: bool = False):
        if not 2 <= half_bit_ms <= 20:
            raise ValueError("Bring-up half-bit must be between 2 and 20 ms")
        import gpiod
        from gpiod.line import Clock, Direction, Edge, Value

        metadata = inspect_chip(path)
        if metadata["controller"] != CONTROLLER:
            raise ValueError("Unexpected GPIO controller; confirm BCM mapping before use")
        self.outputs = [pin.bcm for pin in PINS if pin.output]
        self._value = Value
        self.half_ns = round(half_bit_ms * 1_000_000)
        self.frame_seconds = FRAME_SYMBOLS * self.half_ns / 1e9
        self.max_lateness_ns = 0
        self.rejected = 0
        self.overruns = 0
        # A TxTiming here records each symbol's lateness instead of stopping at the budget.
        self.timing = None
        self._panic = False
        self.last_rejected_raw = None  # Bytes of the last reflection that failed to decode.
        self._last_seq = 0
        self._ignore_before = 0
        self._last_rx_ns = time.monotonic_ns()
        self._frames = deque(maxlen=4)
        config = {
            tuple(self.outputs): gpiod.LineSettings(
                direction=Direction.OUTPUT, active_low=False, output_value=Value.INACTIVE,
            ),
            RX: gpiod.LineSettings(
                direction=Direction.INPUT, edge_detection=Edge.BOTH,
                active_low=rx_inverted, event_clock=Clock.MONOTONIC,
            ),
            PANIC: gpiod.LineSettings(
                direction=Direction.INPUT, edge_detection=Edge.BOTH,
                active_low=True, event_clock=Clock.MONOTONIC,
            ),
        }
        # Both inputs already have external pull-ups in the approved circuit.
        self.request = gpiod.request_lines(
            path, consumer="faronet-optical-test", config=config, event_buffer_size=4096,
        )
        try:
            self._decoder = self._new_decoder()
            self.check_panic()
        except BaseException:
            self.close()
            raise

    def _new_decoder(self):
        return EdgeDecoder(
            self.half_ns, time.monotonic_ns(),
            int(self.request.get_value(RX) == self._value.ACTIVE),
        )

    def set_output(self, pin: int, value: bool):
        self.request.set_value(pin, self._value.ACTIVE if value else self._value.INACTIVE)

    def check_panic(self):
        if self._panic or self.request.get_value(PANIC) == self._value.ACTIVE:
            self._panic = True
            self.clear()
            raise PanicStop("Panic pressed: outputs off; start a fresh session to resume")

    def _wait_until(self, deadline_ns: int):
        while (remaining := deadline_ns - time.monotonic_ns()) > SPIN_NS:
            self.check_panic()
            time.sleep(min((remaining - SPIN_NS) / 1e9, 0.01))
        self.check_panic()
        while time.monotonic_ns() < deadline_ns:
            pass

    def guard(self):
        self.set_output(TX, False)
        self._wait_until(time.monotonic_ns() + GUARD_SYMBOLS * self.half_ns)

    def _events(self):
        if not self.request.wait_edge_events(0):
            return
        for event in self.request.read_edge_events(max_events=512):
            if event.global_seqno != self._last_seq + 1:
                # A gap is a lost event or edges merged by the kernel (a fast glitch
                # reported once, with the final level). Keep the capture: Manchester
                # and CRC validation decide whether the frame survived.
                self.overruns += 1
            self._last_seq = event.global_seqno
            if event.line_offset == PANIC:
                if event.event_type == event.Type.RISING_EDGE:
                    self._panic = True
                continue
            if event.timestamp_ns < self._ignore_before:
                continue
            level = int(event.event_type == event.Type.RISING_EDGE)
            self._last_rx_ns = max(self._last_rx_ns, event.timestamp_ns)
            frame = self._decoder.feed(event.timestamp_ns, level)
            if frame is not None:
                self._frames.append(frame)
        self.check_panic()

    def transmit(self, frame: Frame, loopback: bool = False) -> Frame | None:
        """Send one frame. With loopback, decode its own reflection and return it."""
        self.check_panic()
        # Encoding takes about 2.5 ms on a Pi 3; finish it before the first deadline.
        levels = encode(frame.encode())
        self.set_output(LED_TX, True)
        try:
            try:
                with _on_air() as realtime:
                    if self.timing is not None:
                        self.timing.realtime = realtime
                    start = time.monotonic_ns()
                    for index, level in enumerate(levels):
                        deadline = start + index * self.half_ns
                        self._wait_until(deadline)
                        woke = time.monotonic_ns()
                        self.set_output(TX, bool(level))
                        written = time.monotonic_ns()
                        lateness = written - deadline
                        self.max_lateness_ns = max(self.max_lateness_ns, lateness)
                        if lateness > self.half_ns * 0.4 and self.timing is None:
                            raise TimingError("TX missed its timing budget; increase --half-bit-ms")
                        if loopback:
                            self.set_output(LED_RX, self._decoder.start is not None)
                        else:
                            # Drain self-reflections; panic presses still latch below.
                            self._ignore_before = time.monotonic_ns() + self.half_ns
                        self._events()
                        if self.timing is not None:
                            self.timing.record(index, woke - deadline, written - woke,
                                               time.monotonic_ns() - written)
                    self._wait_until(start + FRAME_SYMBOLS * self.half_ns)
            finally:
                self.set_output(TX, False)
                self.set_output(LED_TX, False)
            if not loopback:
                return None
            # Let the final reflected edges arrive, then complete the capture.
            self._wait_until(time.monotonic_ns() + self.half_ns)
            self._events()
            echo = self._decoder.advance(time.monotonic_ns())
            if echo is not None:
                self._frames.append(echo)
            return self._frames.popleft() if self._frames else None
        finally:
            if loopback:
                self.set_output(LED_RX, False)
                self.rejected += self._decoder.rejected
                self.last_rejected_raw = self._decoder.last_raw
            # Our reflection's tail is not peer light; peer frames start after a guard.
            self._ignore_before = time.monotonic_ns() + self.half_ns
            self._decoder = self._new_decoder()
            if loopback:
                self._frames.clear()

    def receive(self, timeout: float) -> Frame | None:
        deadline = time.monotonic() + timeout
        try:
            while (remaining := deadline - time.monotonic()) > 0:
                self.check_panic()
                self.request.wait_edge_events(min(remaining, 0.02))
                # Empty the kernel queue before completing a timestamped frame.
                self._events()
                self.set_output(LED_RX, self._decoder.start is not None)
                if self.request.wait_edge_events(0):
                    continue
                frame = self._decoder.advance(time.monotonic_ns())
                if frame is not None:
                    self._frames.append(frame)
                if self._frames:
                    return self._frames.popleft()
            return None
        finally:
            self.rejected += self._decoder.rejected
            self._decoder.rejected = 0
            self.set_output(LED_RX, False)

    def input_levels(self) -> dict:
        self.check_panic()
        self._events()
        return {"light": int(self.request.get_value(RX) == self._value.ACTIVE),
                "panic_pressed": self._panic}

    def channel(self) -> tuple[float, bool]:
        """Carrier sense: (monotonic seconds of the last peer RX edge, light arriving now)."""
        self._events()
        busy = (self._decoder.start is not None
                or self.request.get_value(RX) == self._value.ACTIVE)
        return self._last_rx_ns / 1e9, busy

    def sample_rx(self) -> tuple[int, int]:
        """Return the RX level and RX edges since the last call, without decoding."""
        edges = 0
        if self.request.wait_edge_events(0):
            for event in self.request.read_edge_events(max_events=4096):
                self.overruns += event.global_seqno != self._last_seq + 1
                self._last_seq = event.global_seqno
                if event.line_offset == PANIC:
                    self._panic |= event.event_type == event.Type.RISING_EDGE
                else:
                    edges += 1
        self.check_panic()
        return int(self.request.get_value(RX) == self._value.ACTIVE), edges

    def clear(self):
        self._frames.clear()
        if hasattr(self, "_decoder"):
            self._decoder.lose_sync()
        self.request.set_values({pin: self._value.INACTIVE for pin in self.outputs})

    def close(self):
        try:
            self.clear()
            if self._panic:
                self._show_panic()
        finally:
            self.request.release()

    def _show_panic(self):
        """Blink LED_TX and LED_RX together, then leave every output off before release."""
        try:
            for _ in range(PANIC_BLINKS):
                self.request.set_values({LED_TX: self._value.ACTIVE, LED_RX: self._value.ACTIVE})
                time.sleep(PANIC_BLINK_SECONDS)
                self.request.set_values({LED_TX: self._value.INACTIVE, LED_RX: self._value.INACTIVE})
                time.sleep(PANIC_BLINK_SECONDS)
        finally:
            # A released line keeps its last value, so end with everything off even after Ctrl+C.
            self.request.set_values({pin: self._value.INACTIVE for pin in self.outputs})

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
