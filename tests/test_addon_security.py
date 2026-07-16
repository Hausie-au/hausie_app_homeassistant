from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from email.message import Message
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

import yaml

ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon import addon_server  # noqa: E402
from hausie_addon.core.device_state import load_device_state, save_device_state  # noqa: E402


def _headers(**values: str) -> Message:
    headers = Message()
    for key, value in values.items():
        headers[key.replace("_", "-")] = value
    return headers


class AddonManifestSecurityTests(unittest.TestCase):
    def test_sensitive_supervisor_permissions_are_not_enabled(self) -> None:
        manifest_path = Path(__file__).resolve().parents[1] / "hausie" / "config.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        self.assertTrue(manifest["ingress"])
        self.assertEqual(manifest["hassio_role"], "manager")
        self.assertNotIn("auth_api", manifest)
        self.assertNotIn("ports", manifest)


class IngressSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_headers = _headers(
            X_Ingress_Path="/api/hassio_ingress/session-token",
            X_Remote_User_Id="home-assistant-user-id",
            X_Hausie_CSRF_Token=addon_server._UI_CSRF_TOKEN,
        )

    def test_authenticated_ingress_request_is_trusted(self) -> None:
        self.assertTrue(addon_server._is_trusted_ingress_request("172.30.32.2", self.valid_headers))
        self.assertTrue(addon_server._has_valid_ui_csrf_token(self.valid_headers))

    def test_direct_lan_request_is_rejected(self) -> None:
        self.assertFalse(addon_server._is_trusted_ingress_request("192.168.1.20", self.valid_headers))

    def test_ingress_request_without_authenticated_user_is_rejected(self) -> None:
        headers = _headers(X_Ingress_Path="/api/hassio_ingress/session-token")
        self.assertFalse(addon_server._is_trusted_ingress_request("172.30.32.2", headers))

    def test_invalid_csrf_token_is_rejected(self) -> None:
        headers = _headers(X_Hausie_CSRF_Token="wrong-token")
        self.assertFalse(addon_server._has_valid_ui_csrf_token(headers))


class AddonAccessLogTests(unittest.TestCase):
    def test_internal_status_polling_is_not_written_to_access_log(self) -> None:
        handler = addon_server._AddonHandler.__new__(addon_server._AddonHandler)
        handler.path = "/setup/status"

        with patch.object(BaseHTTPRequestHandler, "log_message") as parent_log:
            handler.log_message('"GET %s HTTP/1.1" 200 -', "/setup/status")

        parent_log.assert_not_called()

    def test_normal_requests_remain_visible_in_access_log(self) -> None:
        handler = addon_server._AddonHandler.__new__(addon_server._AddonHandler)
        handler.path = "/setup"

        with patch.object(BaseHTTPRequestHandler, "log_message") as parent_log:
            handler.log_message('"GET %s HTTP/1.1" 200 -', "/setup")

        parent_log.assert_called_once()


class SetupPageTests(unittest.TestCase):
    def test_initialized_installation_can_repair_invalid_credentials(self) -> None:
        status = {
            "credentials": {"credentials_valid": False},
        }
        with patch.object(addon_server, "_setup_status_payload", return_value=status):
            page = addon_server._render_setup_html("/api/hassio_ingress/session")

        self.assertIn('repairingCredentials ? "Save and verify credentials"', page)
        self.assertIn("currentStatus?.initialized && currentStatus?.credentials_valid", page)
        self.assertIn("currentStatus?.initializing ? 2000 : 15000", page)
        self.assertNotIn("setInterval(refreshStatus, 2000)", page)


class DeviceStateSecurityTests(unittest.TestCase):
    def test_state_is_saved_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hausie_device.json"
            save_device_state({"ha_token": "secret"}, path)

            self.assertEqual(load_device_state(path), {"ha_token": "secret"})
            self.assertFalse(path.with_name(f".{path.name}.tmp").exists())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are enforced on the Linux add-on host")
    def test_state_has_owner_only_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hausie_device.json"
            save_device_state({"ha_token": "secret"}, path)

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
