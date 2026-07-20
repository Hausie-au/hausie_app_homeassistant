from __future__ import annotations

import sys
import unittest
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon.core.managers.portal_dashboard_manager import (  # noqa: E402
    PORTAL_DASHBOARD_URL_PATH,
    PORTAL_URL,
    PortalDashboardManager,
)


class FakeWebSocket:
    def __init__(self, dashboards: list[dict], config: dict | None = None) -> None:
        self.dashboards = dashboards
        self.config = config
        self.calls: list[dict] = []

    def call(self, payload: dict) -> object:
        self.calls.append(payload)
        message_type = payload["type"]
        if message_type == "lovelace/dashboards/list":
            return self.dashboards
        if message_type == "lovelace/dashboards/create":
            return {"id": "portal-dashboard", **payload}
        if message_type == "lovelace/dashboards/update":
            return payload
        if message_type == "lovelace/config":
            if self.config is None:
                raise RuntimeError("Dashboard config does not exist")
            return self.config
        if message_type == "lovelace/config/save":
            self.config = payload["config"]
            return None
        raise AssertionError(f"Unexpected WebSocket call: {payload}")


class PortalDashboardManagerTests(unittest.TestCase):
    def test_creates_portal_webpage_dashboard_when_missing(self) -> None:
        ws = FakeWebSocket([])

        action = PortalDashboardManager().ensure(ws)

        self.assertEqual(action, "created")
        create_call = next(
            call for call in ws.calls if call["type"] == "lovelace/dashboards/create"
        )
        self.assertEqual(create_call["url_path"], PORTAL_DASHBOARD_URL_PATH)
        self.assertEqual(create_call["mode"], "storage")
        self.assertTrue(create_call["show_in_sidebar"])
        self.assertFalse(create_call["require_admin"])
        save_call = next(
            call for call in ws.calls if call["type"] == "lovelace/config/save"
        )
        self.assertEqual(
            save_call["config"],
            {"strategy": {"type": "iframe", "url": PORTAL_URL}},
        )

    def test_updates_existing_dashboard_without_creating_duplicate(self) -> None:
        ws = FakeWebSocket(
            [
                {
                    "id": "portal-dashboard",
                    "url_path": PORTAL_DASHBOARD_URL_PATH,
                    "mode": "storage",
                    "title": "Old portal",
                    "icon": "mdi:web",
                    "show_in_sidebar": False,
                    "require_admin": True,
                }
            ],
            {"strategy": {"type": "iframe", "url": "https://old.example.com"}},
        )

        action = PortalDashboardManager().ensure(ws)

        self.assertEqual(action, "updated")
        self.assertFalse(
            any(call["type"] == "lovelace/dashboards/create" for call in ws.calls)
        )
        self.assertTrue(
            any(call["type"] == "lovelace/dashboards/update" for call in ws.calls)
        )
        self.assertEqual(ws.config["strategy"]["url"], PORTAL_URL)

    def test_leaves_matching_portal_dashboard_unchanged(self) -> None:
        ws = FakeWebSocket(
            [
                {
                    "id": "portal-dashboard",
                    "url_path": PORTAL_DASHBOARD_URL_PATH,
                    "mode": "storage",
                    "title": "Hausie Portal",
                    "icon": "mdi:account-circle",
                    "show_in_sidebar": True,
                    "require_admin": False,
                }
            ],
            {"strategy": {"type": "iframe", "url": PORTAL_URL}},
        )

        action = PortalDashboardManager().ensure(ws)

        self.assertEqual(action, "unchanged")
        self.assertFalse(
            any(
                call["type"]
                in {"lovelace/dashboards/create", "lovelace/dashboards/update", "lovelace/config/save"}
                for call in ws.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
