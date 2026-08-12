from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hausie_addon.core.system_updates import (
    SystemUpdateManager,
    clear_update_result,
    get_supervisor_inventory,
)


class _Log:
    def start(self, _message: str) -> None:
        pass

    def ok(self, _message: str) -> None:
        pass

    def error(self, _message: str) -> None:
        pass


class SystemUpdateTests(unittest.TestCase):
    def test_inventory_reports_pending_host_reboot(self) -> None:
        def request(_method, path, payload=None, **kwargs):
            responses = {
                "/info": {"data": {"hassos": "17.0", "homeassistant": "2026.8.1"}},
                "/os/info": {"data": {"version_latest": "17.1", "update_pending": True}},
                "/supervisor/info": {"data": {"version": "2026.08.0", "healthy": True}},
                "/addons": {"data": {"addons": []}},
                "/addons/self/info": {"data": {"slug": "hausie"}},
            }
            return responses[path]

        inventory = get_supervisor_inventory(request)

        self.assertTrue(inventory["system"]["haos_update_pending"])
        self.assertTrue(inventory["system"]["reboot_required"])

    def test_addon_uses_latest_update_endpoint(self) -> None:
        calls = []

        def request(method, path, payload=None, **kwargs):
            calls.append((method, path, payload, kwargs))
            if path == "/supervisor/info":
                return {"data": {"healthy": True}}
            return {"data": {}}

        with tempfile.TemporaryDirectory() as directory:
            manager = SystemUpdateManager(
                request=request,
                log=_Log(),
                state_path=Path(directory) / "updates.json",
            )
            result = manager.apply(
                {
                    "id": "action-1",
                    "type": "update_addon",
                    "payload": {"slug": "core_mosquitto", "mode": "latest"},
                }
            )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(any(call[1] == "/addons/core_mosquitto/update" for call in calls))

    def test_daily_limit_survives_result_acknowledgement(self) -> None:
        def request(method, path, payload=None, **kwargs):
            if path == "/supervisor/info":
                return {"data": {"healthy": True}}
            return {"data": {}}

        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "updates.json"
            manager = SystemUpdateManager(request=request, log=_Log(), state_path=state_path)
            manager.apply(
                {"id": "action-1", "type": "update_addon", "payload": {"slug": "core_ssh"}}
            )
            clear_update_result(state_path)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("latest_result", state)
            self.assertEqual(state["last_action_id"], "action-1")
            result = manager.apply(
                {"id": "action-2", "type": "update_addon", "payload": {"slug": "core_mosquitto"}}
            )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "daily_update_limit")


if __name__ == "__main__":
    unittest.main()
