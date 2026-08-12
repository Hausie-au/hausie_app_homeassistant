from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote


_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


def _body(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else response


def get_supervisor_inventory(
    request: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    info = _body(request("GET", "/info"))
    os_info = _body(request("GET", "/os/info"))
    supervisor = _body(request("GET", "/supervisor/info"))
    addons_body = _body(request("GET", "/addons"))
    self_info = _body(request("GET", "/addons/self/info"))
    addons = addons_body.get("addons") if isinstance(addons_body.get("addons"), list) else []
    normalized_addons = []
    for addon in addons:
        if not isinstance(addon, dict) or not addon.get("installed"):
            continue
        normalized_addons.append({
            "slug": str(addon.get("slug") or "").strip(),
            "name": str(addon.get("name") or addon.get("slug") or "").strip(),
            "version": str(addon.get("version") or "").strip(),
            "version_latest": str(addon.get("version_latest") or "").strip(),
            "update_available": bool(addon.get("update_available", False)),
            "state": str(addon.get("state") or "").strip(),
        })
    return {
        "system": {
            "haos": str(info.get("hassos") or "").strip(),
            "haos_latest": str(os_info.get("version_latest") or "").strip(),
            "haos_update_pending": bool(os_info.get("update_pending", False)),
            "reboot_required": bool(os_info.get("update_pending", False)),
            "home_assistant": str(info.get("homeassistant") or "").strip(),
            "supervisor": str(info.get("supervisor") or supervisor.get("version") or "").strip(),
            "supervisor_latest": str(supervisor.get("version_latest") or "").strip(),
            "healthy": bool(supervisor.get("healthy", False)),
            "supported": bool(supervisor.get("supported", False)),
        },
        "addons": normalized_addons,
        "hausie_addon_slug": str(self_info.get("slug") or "").strip(),
    }


class SystemUpdateManager:
    def __init__(
        self,
        *,
        request: Callable[..., dict[str, Any]],
        log: Any,
        state_path: str | Path = "/data/hausie_system_updates.json",
    ) -> None:
        self._request = request
        self._log = log
        self._state_path = Path(state_path)

    def _load_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_result(self, result: dict[str, Any]) -> None:
        state = self._load_state()
        state["latest_result"] = result
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporary, self._state_path)

    def _mark_started(self, action_id: str) -> None:
        state = self._load_state()
        state["last_started_at"] = int(time.time())
        state["last_action_id"] = action_id
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporary, self._state_path)

    def _record(self, action_id: str, component: str, status: str, **extra: Any) -> dict[str, Any]:
        result = {
            "id": action_id,
            "component": component,
            "status": status,
            "timestamp": int(time.time()),
            **extra,
        }
        self._save_result(result)
        return result

    def _require_healthy(self) -> None:
        info = _body(self._request("GET", "/supervisor/info", raise_on_error=True))
        if not info.get("healthy", False):
            raise RuntimeError("Supervisor reports that the installation is not healthy.")

    def _backup(self, component: str) -> None:
        self._log.start(f"Creating a backup before updating {component}.")
        self._request(
            "POST",
            "/backups/new/partial",
            {
                "name": f"Hausie before {component} update",
                "homeassistant": True,
                "addons": [],
                "folders": ["homeassistant"],
                "background": False,
            },
            raise_on_error=True,
            timeout=900,
        )

    def apply(self, action: dict[str, Any]) -> dict[str, Any]:
        action_id = str(action.get("id") or "").strip()
        action_type = str(action.get("type") or "").strip().lower()
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        component = action_type.removeprefix("update_")
        state = self._load_state()
        last_action_id = str(state.get("last_action_id") or "").strip()
        try:
            last_started_at = int(state.get("last_started_at") or 0)
        except (TypeError, ValueError):
            last_started_at = 0
        now = int(time.time())
        if action_id and action_id == last_action_id:
            return self._record(action_id, component, "skipped", reason="duplicate_action")
        if last_started_at and now - last_started_at < 20 * 60 * 60:
            return self._record(action_id, component, "skipped", reason="daily_update_limit")
        self._mark_started(action_id)
        self._record(action_id, component, "installing", target=payload.get("version"))
        try:
            self._require_healthy()
            if action_type == "update_haos":
                version = str(payload.get("version") or "").strip()
                if not _VERSION_PATTERN.fullmatch(version):
                    raise ValueError("Invalid HA OS target version.")
                self._backup("Home Assistant OS")
                self._request("POST", "/os/update", {"version": version}, raise_on_error=True, timeout=900)
            elif action_type == "update_home_assistant":
                version = str(payload.get("version") or "").strip()
                if not _VERSION_PATTERN.fullmatch(version):
                    raise ValueError("Invalid Home Assistant target version.")
                self._request(
                    "POST",
                    "/core/update",
                    {"version": version, "backup": True},
                    raise_on_error=True,
                    timeout=900,
                )
            elif action_type == "update_addon":
                slug = str(payload.get("slug") or "").strip()
                if not _SLUG_PATTERN.fullmatch(slug):
                    raise ValueError("Invalid add-on slug.")
                self._request(
                    "POST",
                    f"/addons/{quote(slug, safe='')}/update",
                    {"backup": True, "background": False},
                    raise_on_error=True,
                    timeout=900,
                )
            else:
                raise ValueError(f"Unsupported system update action: {action_type}")
            result = self._record(action_id, component, "completed", target=payload.get("version"))
            self._log.ok(f"Completed {component} update.")
            return result
        except Exception as exc:
            result = self._record(
                action_id,
                component,
                "failed",
                target=payload.get("version"),
                error=str(exc)[:500],
            )
            self._log.error(f"Failed {component} update: {exc}")
            return result


def load_update_result(path: str | Path = "/data/hausie_system_updates.json") -> dict[str, Any] | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    result = data.get("latest_result") if isinstance(data, dict) else None
    return result if isinstance(result, dict) else None


def clear_update_result(path: str | Path = "/data/hausie_system_updates.json") -> None:
    state_path = Path(path)
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    data.pop("latest_result", None)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, state_path)
