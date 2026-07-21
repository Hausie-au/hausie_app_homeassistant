from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon import addon_server  # noqa: E402
from hausie_addon.core.device_state import load_device_state  # noqa: E402
from hausie_addon.core.managers.sidebar_policy_manager import (  # noqa: E402
    SidebarPolicyManager,
)


class _FakeWebSocket:
    def __init__(self, *_args, **_kwargs) -> None:
        self.calls: list[dict] = []
        self.closed = False

    def call(self, payload: dict) -> object:
        self.calls.append(payload)
        if payload["type"] == "config/auth/list":
            return [
                {
                    "id": "admin-id",
                    "username": "hausie_admin",
                    "system_generated": False,
                },
                {
                    "id": "customer-id",
                    "username": "mateo",
                    "system_generated": False,
                },
                {
                    "id": "system-id",
                    "username": None,
                    "system_generated": True,
                },
            ]
        return None

    def close(self) -> None:
        self.closed = True


class SidebarPolicyManagerTests(unittest.TestCase):
    def test_applies_global_restriction_and_admin_exception(self) -> None:
        policy = SidebarPolicyManager.normalize(
            {
                "schema_version": 1,
                "revision": 4,
                "admin_username": "hausie_admin",
                "admin_only": ["history", "map"],
            }
        )
        ws = _FakeWebSocket()

        configured_users = SidebarPolicyManager.apply(ws, policy)

        self.assertEqual(configured_users, 2)
        settings_calls = [call for call in ws.calls if call["type"] == "browser_mod/settings"]
        self.assertEqual(settings_calls[0]["value"], '["history","map"]')
        self.assertEqual(settings_calls[1]["user"], "admin-id")
        self.assertEqual(settings_calls[1]["value"], "[]")
        self.assertEqual(settings_calls[2]["user"], "customer-id")
        self.assertEqual(settings_calls[2]["value"], '["history","map"]')

    def test_rejects_panels_outside_the_allowlist(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            SidebarPolicyManager.normalize(
                {
                    "revision": 1,
                    "admin_username": "hausie_admin",
                    "admin_only": ["settings"],
                }
            )

    def test_heartbeat_applies_each_revision_only_once(self) -> None:
        payload = {
            "sidebar_policy": {
                "schema_version": 1,
                "revision": 2,
                "admin_username": "hausie_admin",
                "admin_only": ["history"],
            }
        }
        log = Mock()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "device.json"
            ws = _FakeWebSocket()
            with (
                patch.dict(
                    os.environ,
                    {
                        "HAUSIE_DEVICE_STATE_PATH": str(state_path),
                        "SUPERVISOR_TOKEN": "supervisor-token",
                    },
                ),
                patch.object(addon_server, "_WSClient", return_value=ws),
            ):
                first = addon_server._sync_sidebar_policy_from_heartbeat(payload, log)
                call_count = len(ws.calls)
                second = addon_server._sync_sidebar_policy_from_heartbeat(payload, log)

            state = load_device_state(state_path)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(ws.calls), call_count)
        self.assertEqual(state["applied_sidebar_policy_revision"], 2)
        log.ok.assert_called_once()


if __name__ == "__main__":
    unittest.main()
