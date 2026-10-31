"""Exercise libgpiod ownership and cleanup with a fake request, never physical pins."""

from enum import IntEnum
import io
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from faronet.dispositivo_luz_adaptador.frame import Frame, FrameType
from faronet.faro import commands
from faronet.faro.gpio import GpioFrameIO, PanicStop, TimingError
from faronet.faro.profile import PANIC, RX, TX, inspect_chip

# Former RGB lines; the Faro must never inspect, claim or drive them.
UNRELATED = {5, 6, 13}


class Value(IntEnum):
    INACTIVE = 0
    ACTIVE = 1


class FakeRequest:
    def __init__(self):
        self.values = {RX: Value.INACTIVE, PANIC: Value.INACTIVE}
        self.events = []
        self.released = False
        self.writes = []

    def get_value(self, pin):
        return self.values.get(pin, Value.INACTIVE)

    def set_value(self, pin, value):
        self.values[pin] = value
        self.writes.append((pin, value))

    def set_values(self, values):
        self.values.update(values)
        self.writes.extend(values.items())

    def wait_edge_events(self, _):
        return bool(self.events)

    def read_edge_events(self, max_events):
        events, self.events = self.events[:max_events], self.events[max_events:]
        return events

    def release(self):
        self.released = True


class GpioBackendTests(unittest.TestCase):
    def setUp(self):
        self.request = FakeRequest()
        self.config = None
        self.occupied = set()
        module = ModuleType("gpiod")
        line = ModuleType("gpiod.line")
        line.Value = Value
        line.Direction = SimpleNamespace(INPUT=0, OUTPUT=1)
        line.Edge = SimpleNamespace(BOTH=3)
        line.Clock = SimpleNamespace(MONOTONIC=0)
        module.LineSettings = lambda **kwargs: SimpleNamespace(**kwargs)

        def request_lines(path, **kwargs):
            self.config = kwargs["config"]
            requested = {pin for key in self.config
                         for pin in (key if isinstance(key, tuple) else (key,))}
            if requested & self.occupied:
                raise OSError("GPIO line already owned")
            return self.request

        module.request_lines = request_lines
        self.modules = patch.dict("sys.modules", {"gpiod": module, "gpiod.line": line})
        self.metadata = patch("faronet.faro.gpio.inspect_chip",
                              return_value={"controller": "pinctrl-bcm2835"})
        self.modules.start()
        self.metadata.start()
        self.addCleanup(self.modules.stop)
        self.addCleanup(self.metadata.stop)

    def test_outputs_initialized_low_and_inputs_never_driven(self):
        with GpioFrameIO("/dev/fake") as backend:
            outputs = self.config[tuple(backend.outputs)]
            self.assertEqual(outputs.output_value, Value.INACTIVE)
            self.assertFalse(outputs.active_low)
            self.assertTrue(self.config[PANIC].active_low)
            self.assertEqual(self.config[RX].edge_detection, 3)
            self.assertFalse(self.config[RX].active_low)
            self.assertNotIn(RX, backend.outputs)
            self.assertNotIn(PANIC, backend.outputs)
        self.assertTrue(self.request.released)
        self.assertTrue(all(self.request.values[pin] == 0 for pin in backend.outputs))

    def test_faro_transmits_and_cleans_up_with_unrelated_lines_busy(self):
        self.occupied = set(UNRELATED)
        frame = Frame(FrameType.DATA, b"a" * 8, b"b" * 8, b"s" * 8, 0)
        with GpioFrameIO("/dev/fake") as backend:
            self.assertEqual(set(backend.outputs), {17, 22, 23})
            with patch.object(backend, "_wait_until"), patch(
                "faronet.faro.gpio.time.monotonic_ns", return_value=0,
            ):
                backend.guard()
                backend.transmit(frame)
            backend.input_levels()
            self.assertIsNone(backend.receive(0))
            backend.clear()
        self.assertTrue(self.request.released)
        self.assertFalse({pin for pin, _ in self.request.writes} & self.occupied)

    def test_busy_faro_line_refuses_the_request(self):
        self.occupied = {TX}
        with self.assertRaises(OSError):
            GpioFrameIO("/dev/fake")

    def test_already_pressed_panic_cleans_up_constructor(self):
        self.request.values[PANIC] = Value.ACTIVE
        with self.assertRaises(PanicStop):
            GpioFrameIO("/dev/fake")
        self.assertTrue(self.request.released)
        self.assertEqual(self.request.values[TX], Value.INACTIVE)

    def test_short_panic_press_is_latched_from_event_even_after_release(self):
        with GpioFrameIO("/dev/fake") as backend:
            self.request.events.append(SimpleNamespace(
                global_seqno=1, line_offset=PANIC, timestamp_ns=1,
                event_type=1, Type=SimpleNamespace(RISING_EDGE=1),
            ))
            with self.assertRaises(PanicStop):
                backend.input_levels()
            with self.assertRaises(PanicStop):
                backend.check_panic()
            self.assertEqual(self.request.values[TX], Value.INACTIVE)

    def test_tx_timing_failure_and_interrupt_turn_everything_off(self):
        frame = Frame(FrameType.DATA, b"a" * 8, b"b" * 8, b"s" * 8, 0)
        for error in (TimingError("late"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    with GpioFrameIO("/dev/fake") as backend:
                        with patch.object(backend, "_wait_until", side_effect=error):
                            backend.transmit(frame)
                self.assertTrue(all(self.request.values[p] == 0 for p in backend.outputs))

    def test_wrong_controller_and_clock_refuse_line_request(self):
        for clock in (0, 1, 21, float("nan")):
            with self.assertRaises(ValueError):
                GpioFrameIO("/dev/fake", clock)
        with patch("faronet.faro.gpio.inspect_chip", return_value={"controller": "different"}):
            with self.assertRaises(ValueError):
                GpioFrameIO("/dev/fake")
        self.assertIsNone(self.config)

    def test_preflight_inspects_only_faro_lines_and_never_requests_them(self):
        inspected = []
        occupied = set(UNRELATED)

        class FakeChip:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def get_info(self): return SimpleNamespace(label="pinctrl-bcm2835")
            def get_line_info(self, pin):
                inspected.append(pin)
                return SimpleNamespace(name=f"GPIO{pin}", used=pin in occupied,
                                       consumer="another-program" if pin in occupied else None)

        import gpiod
        gpiod.Chip = FakeChip
        report = inspect_chip("/dev/fake")
        self.assertTrue(report["controller_matches"])
        self.assertEqual(set(inspected), {17, 27, 22, 23, 24})
        self.assertFalse(any(line["used"] for line in report["lines"]))
        for busy, expected_exit in ((UNRELATED, 0), ({PANIC}, 1)):
            occupied.clear()
            occupied.update(busy)
            with self.subTest(busy=busy), patch("sys.stdout", io.StringIO()):
                self.assertEqual(commands.run(SimpleNamespace(
                    command="gpio-preflight", profile_only=False, chip="/dev/fake",
                )), expected_exit)
        self.assertIsNone(self.config)

    def test_cli_requires_hardware_ready_and_profile_runs_without_gpio(self):
        from faronet.cli import main

        with patch("sys.argv", ["faronet", "gpio-monitor"]), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                main()
        with patch("sys.stdout", io.StringIO()) as output:
            self.assertEqual(commands.run(SimpleNamespace(
                command="gpio-preflight", profile_only=True,
            )), 0)
            self.assertIn('"bcm": 17', output.getvalue())
        self.assertIsNone(self.config)


if __name__ == "__main__":
    unittest.main()
