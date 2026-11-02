"""Link address rotation and panic erasure (RFC FN-1 4.4, 4.8 and 10)."""

import asyncio
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from faronet.faro import commands
from faronet.faro.address import ROTATE_SECONDS, AddressStore
from faronet.faro.profile import PANIC
from faronet.node import chat
from faronet.node.identity import Identity
from faronet.node.lan import LanNode
from tests import test_gpio_backend as backend
from tests.test_gpio_backend import FakeRequest, Value


class StateDir(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.state = Path(folder.name) / "state"
        env = patch.dict(os.environ, {"FARONET_STATE_DIR": str(self.state)})
        env.start()
        self.addCleanup(env.stop)


class AddressStoreTests(StateDir):
    def test_address_is_random_private_persistent_and_rotates_daily(self):
        now = [1_000_000.0]
        store = AddressStore(clock=lambda: now[0])
        first = store.current()
        self.assertEqual(len(first), 8)
        self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(store.path.parent.stat().st_mode), 0o700)
        now[0] += ROTATE_SECONDS - 1
        self.assertEqual(AddressStore(clock=lambda: now[0]).current(), first)
        now[0] += 1
        second = store.current()
        self.assertNotEqual(second, first)
        self.assertNotIn(first.hex(), store.path.read_text())

    def test_damaged_or_future_files_are_replaced(self):
        store = AddressStore(clock=lambda: 100.0)
        store.path.parent.mkdir(parents=True)
        for text in ("not json", '{"address": "00", "created_at": 1}',
                     '{"address": "0102030405060708", "created_at": 999999}'):
            store.path.write_text(text)
            self.assertNotEqual(store.current().hex(), "0102030405060708")
            self.assertEqual(json.loads(store.path.read_text())["created_at"], 100.0)

    def test_cli_shows_and_rotates_without_touching_gpio(self):
        def run(rotate):
            with patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(commands.run(SimpleNamespace(command="optical-address", rotate=rotate)), 0)
            return json.loads(out.getvalue())

        shown = run(False)
        self.assertEqual(run(False)["local"], shown["local"])
        self.assertNotEqual(run(True)["local"], shown["local"])
        self.assertLessEqual(shown["rotates_in_hours"], 24)

    def test_cli_reports_an_unwritable_state_dir_without_a_traceback(self):
        self.state.parent.mkdir(exist_ok=True)
        self.state.write_text("not a folder")  # mkdir and the address file both fail.
        with patch("sys.stderr", io.StringIO()) as err:
            self.assertEqual(commands.run(SimpleNamespace(command="optical-address", rotate=True)), 2)
        self.assertIn("No se pudo leer o guardar la dirección física", err.getvalue())

    def test_link_commands_default_to_the_stored_address(self):
        stored = AddressStore().current()
        args = SimpleNamespace(command="optical-send", chip="/dev/fake", half_bit_ms=5, rx_inverted=False,
                               local=None, peer=stored, session=b"s" * 8, count=1, timeout=1)
        with patch("sys.stderr", io.StringIO()) as err:
            self.assertEqual(commands.run(args), 2)
        self.assertIn("must differ", err.getvalue())


class PanicRotationTests(unittest.TestCase):
    """Reuses the fake libgpiod of the backend tests."""

    setUp = backend.GpioBackendTests.setUp

    def test_panic_turns_off_releases_and_rotates_the_address(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.dict(os.environ, {"FARONET_STATE_DIR": folder}):
            before = AddressStore().current()
            self.request.values[PANIC] = Value.ACTIVE
            args = SimpleNamespace(command="gpio-calibrate", chip="/dev/fake", half_bit_ms=5,
                                   rx_inverted=False, seconds=1, blink=False, blink_ms=1000)
            with patch("sys.stderr", io.StringIO()) as err:
                self.assertEqual(commands.run(args), 3)
            self.assertIn("dirección física rotada", err.getvalue())
            self.assertNotEqual(AddressStore().current(), before)
        self.assertTrue(self.request.released)
        self.assertTrue(all(v == Value.INACTIVE for p, v in self.request.values.items() if p != PANIC
                            and p in (17, 22, 23)))


class ChatPanicTests(StateDir, unittest.IsolatedAsyncioTestCase):
    async def test_panic_erases_keys_links_directory_and_messages(self):
        a, b = (LanNode(Identity.generate(), alias, forward_delay_ms=0) for alias in ("a", "b"))
        port = await b.listen("127.0.0.1", 0)
        self.addAsyncCleanup(b.close)
        a.dial("127.0.0.1", port)
        for _ in range(200):
            if a.neighbors() and len(a.directory) == 2:
                break
            await asyncio.sleep(0.01)
        session = chat.ChatSession(a, lambda text: None)
        session.handle("/to b")
        self.assertFalse(session.handle("/panic"))
        self.assertTrue(session.panicked)
        with patch("sys.stdout", io.StringIO()) as out, patch("sys.stderr", io.StringIO()):
            self.assertEqual(await chat._panic(a), 3)
        self.assertIn("\033[3J", out.getvalue())
        self.assertIsNone(a.identity._signing_key)
        self.assertIsNone(a.identity._box_key)
        self.assertEqual((len(a.directory), a.links, a.neighbors(), a.node.inbox), (0, {}, (), []))
        self.assertTrue(AddressStore().path.exists())
        for _ in range(200):
            if not b.neighbors():
                break
            await asyncio.sleep(0.01)
        self.assertEqual(b.neighbors(), ())

    def test_gpio_watcher_fires_on_a_press(self):
        request = FakeRequest()
        request.events = [SimpleNamespace(event_type=1, Type=SimpleNamespace(RISING_EDGE=1))]
        module, line = ModuleType("gpiod"), ModuleType("gpiod.line")
        line.Value = Value
        line.Direction = SimpleNamespace(INPUT=0)
        line.Edge = SimpleNamespace(BOTH=3)
        module.LineSettings = lambda **kwargs: SimpleNamespace(**kwargs)
        module.request_lines = lambda chip, **kwargs: request
        pressed = []
        with patch.dict("sys.modules", {"gpiod": module, "gpiod.line": line}):
            chat.watch_panic("/dev/fake", lambda: pressed.append(True))
        self.assertEqual(pressed, [True])
        self.assertTrue(request.released)


    def test_panic_gpio_failures_are_reported_before_the_node_starts(self):
        with patch.dict("sys.modules", {"gpiod": None}):
            with self.assertRaisesRegex(OSError, "necesita gpiod"):
                chat.open_panic("/dev/gpiochip0")
        module, line = ModuleType("gpiod"), ModuleType("gpiod.line")
        line.Direction = SimpleNamespace(INPUT=0)
        line.Edge = SimpleNamespace(BOTH=3)
        module.LineSettings = lambda **kwargs: SimpleNamespace(**kwargs)

        def missing(chip, **kwargs):
            raise FileNotFoundError(2, "No such file or directory")

        module.request_lines = missing
        with patch.dict("sys.modules", {"gpiod": module, "gpiod.line": line}):
            with self.assertRaisesRegex(OSError, "No se pudo abrir el botón de pánico"):
                chat.open_panic("/dev/nope")

    def test_input_that_is_not_utf8_keeps_the_reader_going(self):
        lines = []
        loop = SimpleNamespace(call_soon_threadsafe=lambda put, item: put(item))
        queue = SimpleNamespace(put_nowait=lines.append)
        chat._stdin_lines(loop, queue, [b"\xff\xfe hola\n", "adiós\n".encode()])
        self.assertEqual(lines, ["\ufffd\ufffd hola\n", "adiós\n", None])


if __name__ == "__main__":
    unittest.main()
