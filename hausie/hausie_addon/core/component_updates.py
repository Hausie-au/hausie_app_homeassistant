from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests

from .clients.ha_client import HAClient


_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COMPONENT_REPOSITORIES = {
    "browser_mod": "thomasloven/hass-browser_mod",
    "button_card": "custom-cards/button-card",
}
_UPDATE_ENTITY_IDS = {
    "browser_mod": ("update.browser_mod_update", "update.browser_mod"),
    "button_card": ("update.button_card_update", "update.button_card"),
}


def normalize_version(value: Any) -> str:
    version = str(value or "").strip().lower()
    if version.startswith("v") and len(version) > 1 and version[1].isdigit():
        version = version[1:]
    return version


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _hacs_repository(config_root: Path, component: str) -> dict[str, Any]:
    expected = _COMPONENT_REPOSITORIES.get(component)
    if not expected:
        return {}
    payload = _read_json(config_root / ".storage" / "hacs.repositories")
    repositories = payload.get("data")
    if not isinstance(repositories, dict):
        return {}
    for entry in repositories.values():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("full_name") or "").strip().lower() == expected.lower():
            return entry
    return {}


def _browser_mod_version(config_root: Path) -> tuple[str, str]:
    manifest = _read_json(config_root / "custom_components" / "browser_mod" / "manifest.json")
    version = str(manifest.get("version") or "").strip()
    if version:
        return version, "manifest"
    repository = _hacs_repository(config_root, "browser_mod")
    version = str(repository.get("version_installed") or "").strip()
    return (version, "hacs") if version else ("", "missing")


def _button_card_version(config_root: Path) -> tuple[str, str]:
    javascript_path = config_root / "www" / "community" / "button-card" / "button-card.js"
    try:
        javascript = javascript_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        javascript = ""
    for pattern in (
        r"BUTTON-CARD.{0,160}?concat\([\"']v?([0-9][A-Za-z0-9._-]*)[\"']",
        r"BUTTON-CARD.{0,160}?v([0-9]+(?:\.[0-9A-Za-z_-]+)+)",
    ):
        match = re.search(pattern, javascript, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1), "javascript"
    repository = _hacs_repository(config_root, "button_card")
    version = str(repository.get("version_installed") or "").strip()
    return (version, "hacs") if version else ("", "missing")


def get_component_versions(config_root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    root = Path(config_root or os.getenv("PI_HA_CONFIG_DIR", "/homeassistant")).resolve()
    browser_version, browser_source = _browser_mod_version(root)
    button_version, button_source = _button_card_version(root)
    return {
        "browser_mod": {
            "installed": bool(browser_version),
            "version": browser_version,
            "source": browser_source,
        },
        "button_card": {
            "installed": bool(button_version),
            "version": button_version,
            "source": button_source,
        },
    }


def _validate_target_version(value: Any) -> str:
    version = str(value or "").strip()
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid component version: {value!r}")
    return version


def _state_search_text(state: dict[str, Any]) -> str:
    attributes = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
    values = [
        state.get("entity_id"),
        attributes.get("friendly_name"),
        attributes.get("title"),
        attributes.get("name"),
        attributes.get("repository"),
        attributes.get("release_url"),
    ]
    return " ".join(str(value or "").lower().replace("_", "-") for value in values)


def _find_update_entity(states: list[dict[str, Any]], component: str) -> dict[str, Any] | None:
    exact_ids = _UPDATE_ENTITY_IDS.get(component, ())
    repository = _COMPONENT_REPOSITORIES.get(component, "").lower()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        entity_id = str(state.get("entity_id") or "").strip().lower()
        if not entity_id.startswith("update."):
            continue
        text = _state_search_text(state)
        score = 0
        if entity_id in exact_ids:
            score += 100
        if repository and repository in text:
            score += 80
        if component == "browser_mod" and ("browser-mod" in text or "browser mod" in text):
            score += 30
        if component == "button_card":
            if "slider-button-card" in text or "slider button card" in text:
                continue
            if "button-card" in text or "button card" in text:
                score += 30
        if score:
            candidates.append((score, state))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _service_target_version(state: dict[str, Any], target: str) -> str:
    attributes = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
    known = str(attributes.get("installed_version") or attributes.get("latest_version") or "")
    normalized = normalize_version(target)
    return f"v{normalized}" if known.strip().lower().startswith("v") else normalized


class ComponentUpdateManager:
    def __init__(
        self,
        *,
        ha_client: HAClient,
        log: Any,
        config_root: str | Path | None = None,
        state_path: str | Path = "/data/hausie_component_updates.json",
    ) -> None:
        self._ha = ha_client
        self._log = log
        self._root = Path(
            config_root or os.getenv("PI_HA_CONFIG_DIR", "/homeassistant")
        ).resolve()
        self._state_path = Path(state_path)

    def _load_state(self) -> dict[str, Any]:
        return _read_json(self._state_path)

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporary, self._state_path)

    def _retry_allowed(self, state: dict[str, Any], component: str, target: str) -> bool:
        failure = (state.get("failures") or {}).get(component)
        if not isinstance(failure, dict):
            return True
        if normalize_version(failure.get("target")) != normalize_version(target):
            return True
        try:
            retry_after = int(failure.get("retry_after") or 0)
        except Exception:
            retry_after = 0
        return retry_after <= int(time.time())

    def _record_failure(
        self,
        state: dict[str, Any],
        component: str,
        target: str,
        error: Exception,
    ) -> None:
        failures = state.setdefault("failures", {})
        previous = failures.get(component) if isinstance(failures.get(component), dict) else {}
        if normalize_version(previous.get("target")) == normalize_version(target):
            count = int(previous.get("count") or 0) + 1
        else:
            count = 1
        delay = min(3600, 300 * (2 ** min(count - 1, 3)))
        failures[component] = {
            "target": target,
            "count": count,
            "retry_after": int(time.time()) + delay,
            "error": str(error)[:500],
        }
        self._save_state(state)

    def _clear_failure(self, state: dict[str, Any], component: str) -> None:
        failures = state.get("failures")
        if isinstance(failures, dict) and component in failures:
            failures.pop(component, None)
            self._save_state(state)

    def _wait_for_version(self, component: str, target: str, timeout_s: int = 120) -> None:
        deadline = time.time() + max(5, timeout_s)
        while time.time() < deadline:
            current = get_component_versions(self._root).get(component, {}).get("version")
            if normalize_version(current) == normalize_version(target):
                return
            time.sleep(2)
        current = get_component_versions(self._root).get(component, {}).get("version")
        raise RuntimeError(
            f"{component} update did not reach {target}; installed version is {current or 'missing'}"
        )

    def _update_with_home_assistant(
        self,
        component: str,
        target: str,
        update_entity: dict[str, Any],
    ) -> None:
        entity_id = str(update_entity.get("entity_id") or "").strip()
        service_version = _service_target_version(update_entity, target)
        self._log.start(
            f"Installing {component} {target} through Home Assistant entity {entity_id}."
        )
        self._ha.call_service(
            "update",
            "install",
            {
                "entity_id": entity_id,
                "version": service_version,
                "backup": False,
            },
            timeout_s=180,
        )
        self._wait_for_version(component, target)

    def _download(self, url: str, *, max_bytes: int) -> bytes:
        response = requests.get(
            url,
            headers={"User-Agent": "Hausie-HomeAssistant-Addon"},
            timeout=(10, 120),
        )
        response.raise_for_status()
        content = response.content
        if not content or len(content) > max_bytes:
            raise RuntimeError(f"Unexpected download size from {url}: {len(content)} bytes")
        return content

    def _install_browser_mod_direct(self, target: str) -> None:
        tag = target if target.lower().startswith("v") else f"v{target}"
        url = (
            "https://github.com/thomasloven/hass-browser_mod/archive/refs/tags/"
            f"{tag}.zip"
        )
        archive_bytes = self._download(url, max_bytes=25 * 1024 * 1024)
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            manifest_members = [
                name
                for name in archive.namelist()
                if name.endswith("/custom_components/browser_mod/manifest.json")
            ]
            if len(manifest_members) != 1:
                raise RuntimeError("Browser Mod archive has an unexpected structure.")
            prefix = manifest_members[0][: -len("manifest.json")]
            target_dir = self._root / "custom_components" / "browser_mod"
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target_dir.parent) as temp_dir:
                staged = Path(temp_dir) / "browser_mod"
                for member in archive.infolist():
                    if member.is_dir() or not member.filename.startswith(prefix):
                        continue
                    relative = Path(member.filename[len(prefix) :])
                    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                        raise RuntimeError("Browser Mod archive contains an unsafe path.")
                    destination = staged / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(member))
                manifest = _read_json(staged / "manifest.json")
                if normalize_version(manifest.get("version")) != normalize_version(target):
                    raise RuntimeError(
                        "Browser Mod archive version does not match the requested version."
                    )
                backup = target_dir.with_name(".browser_mod.hausie-backup")
                if backup.exists():
                    shutil.rmtree(backup)
                try:
                    if target_dir.exists():
                        os.replace(target_dir, backup)
                    os.replace(staged, target_dir)
                except Exception:
                    if not target_dir.exists() and backup.exists():
                        os.replace(backup, target_dir)
                    raise
                finally:
                    if backup.exists():
                        shutil.rmtree(backup)

    def _install_button_card_direct(self, target: str) -> None:
        tag = target if target.lower().startswith("v") else f"v{target}"
        url = f"https://github.com/custom-cards/button-card/releases/download/{tag}/button-card.js"
        content = self._download(url, max_bytes=5 * 1024 * 1024)
        target_dir = self._root / "www" / "community" / "button-card"
        target_dir.mkdir(parents=True, exist_ok=True)
        temporary = target_dir / ".button-card.js.hausie.tmp"
        temporary.write_bytes(content)
        text = content.decode("utf-8", errors="ignore")
        if not re.search(
            rf"BUTTON-CARD.{{0,160}}?{re.escape(normalize_version(target))}",
            text,
            re.I | re.S,
        ):
            temporary.unlink(missing_ok=True)
            raise RuntimeError("Button Card asset version does not match the requested version.")
        os.replace(temporary, target_dir / "button-card.js")

    def _update_direct(self, component: str, target: str) -> None:
        self._log.start(f"Installing unmanaged {component} {target} from its official release.")
        if component == "browser_mod":
            self._install_browser_mod_direct(target)
        elif component == "button_card":
            self._install_button_card_direct(target)
        else:
            raise ValueError(f"Unsupported component: {component}")
        self._wait_for_version(component, target, timeout_s=5)

    def apply(self, requested: dict[str, Any]) -> list[str]:
        targets: dict[str, str] = {}
        for component in ("browser_mod", "button_card"):
            entry = requested.get(component)
            value = entry.get("version") if isinstance(entry, dict) else entry
            if value:
                targets[component] = _validate_target_version(value)
        if not targets:
            return []

        state = self._load_state()
        installed = get_component_versions(self._root)
        states: list[dict[str, Any]] | None = None
        updated: list[str] = []
        for component, target in targets.items():
            current = installed.get(component, {}).get("version")
            if normalize_version(current) == normalize_version(target):
                self._clear_failure(state, component)
                continue
            if not self._retry_allowed(state, component, target):
                self._log.warn(f"Component update retry delayed: {component} {target}.")
                continue
            try:
                if states is None:
                    states = self._ha.get_states()
                update_entity = _find_update_entity(states, component)
                hacs_repository = _hacs_repository(self._root, component)
                if update_entity:
                    self._update_with_home_assistant(component, target, update_entity)
                elif hacs_repository.get("installed") or (
                    self._root / "custom_components" / "hacs"
                ).exists():
                    raise RuntimeError(
                        f"HACS manages {component}, but its Home Assistant update entity is unavailable."
                    )
                else:
                    self._update_direct(component, target)
                self._clear_failure(state, component)
                updated.append(component)
                self._log.ok(f"Updated {component} to {target}.")
            except Exception as exc:
                self._record_failure(state, component, target, exc)
                self._log.error(f"Failed to update {component} to {target}: {exc}")
        return updated
