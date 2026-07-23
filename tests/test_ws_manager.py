import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.ws_manager import ConnectionManager, notify_clients, set_main_loop


# ===================================================================
# ConnectionManager
# ===================================================================
class TestConnectionManager(unittest.IsolatedAsyncioTestCase):
    """Tests for gui.ws_manager.ConnectionManager."""

    async def asyncSetUp(self):
        self.manager = ConnectionManager()

    async def test_init_empty(self):
        """A new ConnectionManager should have an empty active_connections list."""
        self.assertEqual(self.manager.active_connections, [])

    async def test_connect_adds_websocket(self):
        """connect() should accept the websocket and add it to active_connections."""
        ws = AsyncMock()
        await self.manager.connect(ws)
        self.assertIn(ws, self.manager.active_connections)
        ws.accept.assert_awaited_once()

    async def test_disconnect_removes_websocket(self):
        """disconnect() should remove a websocket from active_connections."""
        ws = AsyncMock()
        await self.manager.connect(ws)
        self.manager.disconnect(ws)
        self.assertEqual(self.manager.active_connections, [])

    async def test_disconnect_non_existent(self):
        """disconnect() on a websocket not in active_connections should not raise."""
        ws = AsyncMock()
        # Should not raise any exception
        self.manager.disconnect(ws)

    async def test_broadcast_sends_to_all(self):
        """broadcast() should send the message dict to every connected websocket."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)
        msg = {"event_type": "test", "status": "ok"}
        await self.manager.broadcast(msg)
        ws1.send_json.assert_awaited_once_with(msg)
        ws2.send_json.assert_awaited_once_with(msg)

    async def test_broadcast_removes_dead_connections(self):
        """broadcast() should disconnect websockets that raise on send_json."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_json.side_effect = Exception("connection dead")
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)
        msg = {"event_type": "test", "status": "ok"}
        await self.manager.broadcast(msg)
        # ws1 should still have been called
        ws1.send_json.assert_awaited_once_with(msg)
        # ws2 should have been called once (and then disconnected)
        ws2.send_json.assert_awaited_once_with(msg)
        # Only ws1 should remain
        self.assertEqual(self.manager.active_connections, [ws1])


# ===================================================================
# Module-level notify_clients
# ===================================================================
class TestNotifyClients(unittest.TestCase):
    """Tests for gui.ws_manager.notify_clients() and set_main_loop()."""

    def setUp(self):
        """Reset _main_loop to None before each test."""
        import gui.ws_manager as ws_manager_mod

        ws_manager_mod._main_loop = None

    def test_notify_clients_when_main_loop_is_none(self):
        """notify_clients() should return silently when _main_loop is None."""
        # Should not raise any exception
        notify_clients("test_event", "ok", "test message")
        notify_clients("test_event", "ok", "test message", level="warning")
        notify_clients("test_event", "ok", "test message", metadata={"key": "val"})

    def test_set_main_loop(self):
        """set_main_loop() should set the global loop; notify_clients uses it."""
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False
        set_main_loop(mock_loop)

        with patch("gui.ws_manager.asyncio.run_coroutine_threadsafe") as mock_run:
            notify_clients("test_event", "ok", "test message")
            mock_run.assert_called_once()
            # First arg should be a coroutine (the broadcast call), second arg the loop
            args = mock_run.call_args[0]
            self.assertEqual(len(args), 2)
            self.assertIs(args[1], mock_loop)


if __name__ == "__main__":
    unittest.main()
