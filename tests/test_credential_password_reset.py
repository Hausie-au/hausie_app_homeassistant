import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon import addon_server  # noqa: E402


class CredentialPasswordResetTests(unittest.TestCase):
    @patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-token"}, clear=False)
    @patch.object(addon_server.requests, "request")
    def test_supervisor_password_reset_sends_username_and_password(self, request: Mock) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"result": "ok"}
        request.return_value = response

        addon_server._reset_local_ha_password("hausie_admin", "new-password")

        request.assert_called_once_with(
            "POST",
            "http://supervisor/auth/reset",
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
            json={"username": "hausie_admin", "password": "new-password"},
            timeout=15,
        )

    def test_existing_hausie_users_are_updated_without_deletion(self) -> None:
        ha = Mock()
        ha.fetch_users.return_value = [
            {"username": "hausie_admin", "isOwner": True, "isAdmin": True},
            {"username": "hausie_support_user", "isOwner": False, "isAdmin": True},
        ]
        validation = {"credentials_valid": True, "validation_error": ""}

        with (
            patch.object(
                addon_server,
                "resolve_ha_runtime_credentials",
                return_value=("existing-token", "hausie_support_user", "existing-password"),
            ),
            patch.object(addon_server, "load_device_state", return_value={}),
            patch.object(addon_server, "save_device_state"),
            patch.object(addon_server, "_resolve_ha_client", return_value=ha),
            patch.object(addon_server, "_reset_local_ha_password") as reset_password,
            patch.object(addon_server, "_supervisor_request"),
            patch.object(addon_server, "persist_ha_runtime_credentials"),
            patch.object(addon_server, "_validate_ha_credentials", return_value=validation),
            patch.object(addon_server, "_sync_local_config"),
            patch.object(addon_server, "_MQTT_LISTENER", object()),
            patch.object(addon_server, "_SUPPORT_MANAGER", object()),
            patch.object(addon_server, "_HEARTBEAT", object()),
            patch.object(addon_server, "_start_license_monitor"),
            patch.object(addon_server, "_start_inventory_monitor"),
        ):
            result = addon_server._save_ha_credentials(
                {
                    "ha_token": "new-token",
                    "admin_password": "new-admin-password",
                    "support_password": "new-support-password",
                }
            )

        self.assertEqual(result, validation)
        reset_password.assert_has_calls(
            [
                call("hausie_admin", "new-admin-password"),
                call("hausie_support_user", "new-support-password"),
            ]
        )
        self.assertEqual(reset_password.call_count, 2)
        ha.delete_auth_user_by_username.assert_not_called()
        ha.create_auth_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()
