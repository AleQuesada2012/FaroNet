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


class Value(IntEnum):
    INACTIVE = 0
    ACTIVE = 1


class FakeRequest:
    def __init__(self):
        self.values = {RX: Value.INACTIVE, PANIC: Value.INACTIVE}
        self.events = []
        self.released = False

    def get_value(self, pin):
        return self.values.get(pin, Value.INACTIVE)

    def set_value(self, pin, value):
        self.values[pin] = value

    def set_values(self, values):
        self.values.update(values)

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
        module = ModuleType("gpiod")
        line = ModuleType("gpiod.line")
        line.Value = Value
        line.Direction = SimpleNamespace(INPUT=0, OUTPUT=1)
        line.Edge = SimpleNamespace(BOTH=3)
        line.Clock = SimpleNamespace(MONOTONIC=0)
        module.LineSettings = lambda **kwargs: SimpleNamespace(**kwargs)

        def request_lines(path, **kwargs):
            self.config = kwargs["config"]
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
        with GpioFrameIO("/dev/fake", rgb=True) as backend:
            outputs = self.config[tuple(backend.outputs)]
            self.assertEqual(outputs.output_value, Value.INACTIVE)
            self.assertTrue(self.config[PANIC].active_low)
            self.assertEqual(self.config[RX].edge_detection, 3)
            self.assertNotIn(RX, backend.outputs)
            self.assertNotIn(PANIC, backend.outputs)
        self.assertTrue(self.request.released)
        self.assertTrue(all(self.request.values[pin] == 0 for pin in backend.outputs))

    def test_already_pressed_panic_cleans_up_constructor(self):
        self.request.values[PANIC] = Value.ACTIVE
        with self.assertRaises(PanicStop):
            GpioFrameIO("/dev/fake", rgb=True)
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
                    with GpioFrameIO("/dev/fake", rgb=True) as backend:
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

    def test_preflight_only_reads_metadata(self):
        class FakeChip:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def get_info(self): return SimpleNamespace(label="pinctrl-bcm2835")
            def get_line_info(self, pin):
                return SimpleNamespace(name=f"GPIO{pin}", used=False, consumer=None)

        import gpiod
        gpiod.Chip = FakeChip
        report = inspect_chip("/dev/fake")
        self.assertTrue(report["controller_matches"])
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
