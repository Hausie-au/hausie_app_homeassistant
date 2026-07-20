from __future__ import annotations

from typing import Protocol


PORTAL_DASHBOARD_TITLE = "Hausie Portal"
PORTAL_DASHBOARD_URL_PATH = "hausie-portal"
PORTAL_DASHBOARD_ICON = "mdi:account-circle"
PORTAL_URL = "https://portal.hausiehome.com/auth"


class WebSocketCaller(Protocol):
    def call(self, payload: dict) -> object: ...


class PortalDashboardManager:
    """Keep the storage-managed Hausie Portal webpage dashboard in sync."""

    _metadata = {
        "title": PORTAL_DASHBOARD_TITLE,
        "icon": PORTAL_DASHBOARD_ICON,
        "show_in_sidebar": True,
        "require_admin": False,
    }
    _config = {
        "strategy": {
            "type": "iframe",
            "url": PORTAL_URL,
        }
    }

    def ensure(self, ws: WebSocketCaller) -> str:
        dashboards = ws.call({"type": "lovelace/dashboards/list"}) or []
        if not isinstance(dashboards, list):
            raise RuntimeError("Home Assistant did not return the dashboard list")

        dashboard = next(
            (
                item
                for item in dashboards
                if isinstance(item, dict)
                and str(item.get("url_path") or "").strip() == PORTAL_DASHBOARD_URL_PATH
            ),
            None,
        )
        changed = False

        if dashboard is None:
            dashboard = ws.call(
                {
                    "type": "lovelace/dashboards/create",
                    "url_path": PORTAL_DASHBOARD_URL_PATH,
                    "mode": "storage",
                    **self._metadata,
                }
            )
            if not isinstance(dashboard, dict) or not dashboard.get("id"):
                raise RuntimeError("Home Assistant did not return the created portal dashboard")
            changed = True
        else:
            if str(dashboard.get("mode") or "storage").strip() != "storage":
                raise RuntimeError(
                    f"Dashboard path '{PORTAL_DASHBOARD_URL_PATH}' is not storage-managed"
                )
            dashboard_id = str(dashboard.get("id") or "").strip()
            if not dashboard_id:
                raise RuntimeError("Existing Hausie Portal dashboard has no id")
            if any(dashboard.get(key) != value for key, value in self._metadata.items()):
                ws.call(
                    {
                        "type": "lovelace/dashboards/update",
                        "dashboard_id": dashboard_id,
                        **self._metadata,
                    }
                )
                changed = True

        try:
            current_config = ws.call(
                {
                    "type": "lovelace/config",
                    "url_path": PORTAL_DASHBOARD_URL_PATH,
                }
            )
        except RuntimeError:
            current_config = None

        current_strategy = (
            current_config.get("strategy") if isinstance(current_config, dict) else None
        )
        if current_strategy != self._config["strategy"]:
            ws.call(
                {
                    "type": "lovelace/config/save",
                    "url_path": PORTAL_DASHBOARD_URL_PATH,
                    "config": self._config,
                }
            )
            changed = True

        return "created" if dashboard not in dashboards else "updated" if changed else "unchanged"
