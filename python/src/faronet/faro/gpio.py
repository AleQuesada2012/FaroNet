"""Optional Linux libgpiod v2 backend. Importing this module never opens GPIO."""

from collections import deque
import time

from faronet.dispositivo_luz_adaptador.frame import Frame
from faronet.dispositivo_luz_adaptador.manchester import encode
from faronet.faro.profile import CONTROLLER, LED_RX, LED_TX, PANIC, PINS, RX, TX, inspect_chip
from faronet.faro.waveform import EdgeDecoder, FRAME_SYMBOLS, GUARD_SYMBOLS


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
        self._panic = False
        self._last_seq = 0
        self._ignore_before = 0
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
        while (remaining := deadline_ns - time.monotonic_ns()) > 0:
            self.check_panic()
            time.sleep(min(remaining / 1e9, 0.01))
        self.check_panic()

    def guard(self):
        self.set_output(TX, False)
        self._wait_until(time.monotonic_ns() + GUARD_SYMBOLS * self.half_ns)

    def _events(self):
        if not self.request.wait_edge_events(0):
            return
        for event in self.request.read_edge_events(max_events=512):
            if event.global_seqno != self._last_seq + 1:
                self.overruns += 1
                self._decoder.lose_sync()
            self._last_seq = event.global_seqno
            if event.line_offset == PANIC:
                if event.event_type == event.Type.RISING_EDGE:
                    self._panic = True
                continue
            if event.timestamp_ns < self._ignore_before:
                continue
            level = int(event.event_type == event.Type.RISING_EDGE)
            frame = self._decoder.feed(event.timestamp_ns, level)
            if frame is not None:
                self._frames.append(frame)
        self.check_panic()

    def transmit(self, frame: Frame):
        self.check_panic()
        self.set_output(LED_TX, True)
        try:
            start = time.monotonic_ns()
            for index, level in enumerate(encode(frame.encode())):
                deadline = start + index * self.half_ns
                self._wait_until(deadline)
                self.set_output(TX, bool(level))
                lateness = time.monotonic_ns() - deadline
                self.max_lateness_ns = max(self.max_lateness_ns, lateness)
                if lateness > self.half_ns * 0.4:
                    raise TimingError("TX missed its timing budget; increase --half-bit-ms")
                # Drain self-reflections and latch short panic presses during TX.
                self._ignore_before = time.monotonic_ns() + self.half_ns
                self._events()
            self._wait_until(start + FRAME_SYMBOLS * self.half_ns)
        finally:
            self.set_output(TX, False)
            self.set_output(LED_TX, False)
            self._ignore_before = time.monotonic_ns()
            self._decoder = self._new_decoder()
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

    def sample_rx(self) -> tuple[int, int]:
        """Return the RX level and RX edges since the last call, without decoding."""
        edges = 0
        if self.request.wait_edge_events(0):
            for event in self.request.read_edge_events(max_events=4096):
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
        finally:
            self.request.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
