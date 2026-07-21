from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from ..device_state import HAUSIE_ADMIN_USERNAME


SIDEBAR_POLICY_ALLOWED_PANELS = (
    "browser-mod",
    "history",
    "media-browser",
    "map",
    "energy",
    "logbook",
    "todo",
)


class WebSocketCaller(Protocol):
    def call(self, payload: dict) -> object: ...


@dataclass(frozen=True)
class SidebarPolicy:
    revision: int
    admin_only: tuple[str, ...]


class SidebarPolicyManager:
    """Apply the cloud sidebar policy through Browser Mod settings."""

    @staticmethod
    def normalize(payload: Any) -> SidebarPolicy:
        if not isinstance(payload, dict):
            raise RuntimeError("Sidebar policy is missing or invalid")
        try:
            revision = int(payload.get("revision") or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Sidebar policy revision is invalid") from exc
        if revision < 1:
            raise RuntimeError("Sidebar policy revision must be positive")
        if int(payload.get("schema_version") or 1) != 1:
            raise RuntimeError("Sidebar policy schema is unsupported")
        admin_username = str(payload.get("admin_username") or "").strip().lower()
        if admin_username != HAUSIE_ADMIN_USERNAME:
            raise RuntimeError("Sidebar policy administrator is invalid")
        requested = payload.get("admin_only")
        if not isinstance(requested, list):
            raise RuntimeError("Sidebar policy panel list is invalid")
        normalized: list[str] = []
        for value in requested:
            panel = str(value or "").strip().lower()
            if panel not in SIDEBAR_POLICY_ALLOWED_PANELS:
                raise RuntimeError(f"Sidebar policy panel is not allowed: {panel or value}")
            if panel not in normalized:
                normalized.append(panel)
        return SidebarPolicy(revision=revision, admin_only=tuple(normalized))

    @staticmethod
    def apply(ws: WebSocketCaller, policy: SidebarPolicy) -> int:
        users = ws.call({"type": "config/auth/list"}) or []
        if not isinstance(users, list):
            raise RuntimeError("Home Assistant did not return the user list")
        administrator = next(
            (
                user
                for user in users
                if isinstance(user, dict)
                and str(user.get("username") or "").strip().lower()
                == HAUSIE_ADMIN_USERNAME
            ),
            None,
        )
        if not isinstance(administrator, dict) or not administrator.get("id"):
            raise RuntimeError(f"Home Assistant user '{HAUSIE_ADMIN_USERNAME}' was not found")

        hidden = json.dumps(list(policy.admin_only), separators=(",", ":"))
        ws.call(
            {
                "type": "browser_mod/settings",
                "key": "sidebarHiddenPanels",
                "value": hidden,
            }
        )

        configured_users = 0
        for user in users:
            if (
                not isinstance(user, dict)
                or user.get("system_generated")
                or not str(user.get("id") or "").strip()
            ):
                continue
            is_hausie_admin = (
                str(user.get("username") or "").strip().lower()
                == HAUSIE_ADMIN_USERNAME
            )
            ws.call(
                {
                    "type": "browser_mod/settings",
                    "user": str(user["id"]),
                    "key": "sidebarHiddenPanels",
                    "value": "[]" if is_hausie_admin else hidden,
                }
            )
            configured_users += 1
        return configured_users
