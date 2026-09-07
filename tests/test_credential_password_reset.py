import sys
import unittest
import json
from pathlib import Path
from unittest.mock import Mock, call, patch


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon import addon_server  # noqa: E402
from hausie_addon.core.clients.ha_client import HAClient  # noqa: E402
from hausie_addon.settings import Settings  # noqa: E402


class CredentialPasswordResetTests(unittest.TestCase):
    def test_validation_repairs_missing_marker_when_users_still_exist(self) -> None:
        ha = Mock()
        ha.fetch_users.return_value = [
            {"username": "hausie_admin", "isAdmin": True},
            {"username": "hausie_support_user", "isAdmin": True},
        ]
        state = {}

        with (
            patch.object(
                addon_server,
                "resolve_ha_runtime_credentials",
                return_value=("administrator-token", "hausie_support_user", "support-password"),
            ),
            patch.object(addon_server, "load_device_state", return_value=state),
            patch.object(addon_server, "save_device_state") as save_state,
            patch.object(addon_server, "_resolve_ha_admin_client", return_value=ha),
        ):
            result = addon_server._validate_ha_credentials()

        self.assertTrue(result["credentials_valid"])
        self.assertTrue(state["hausie_admin_password_configured"])
        save_state.assert_called_once_with(state)

    def test_rejected_websocket_command_is_reported(self) -> None:
        class RejectedSocket:
            def send(self, _payload: str) -> None:
                return None

            def recv(self) -> str:
                return json.dumps(
                    {
                        "id": 1,
                        "type": "result",
                        "success": False,
                        "error": {"code": "unauthorized", "message": "Unauthorized"},
                    }
                )

        ha = HAClient.__new__(HAClient)

        with self.assertRaisesRegex(RuntimeError, "config/auth/list.*Unauthorized"):
            ha._send_and_wait(RejectedSocket(), 1, "config/auth/list")

    def test_rejected_auth_websocket_command_identifies_the_command(self) -> None:
        class RejectedSocket:
            def __init__(self) -> None:
                self._responses = iter(
                    [
                        {"type": "auth_required"},
                        {"type": "auth_ok"},
                        {
                            "id": 1,
                            "type": "result",
                            "success": False,
                            "error": {"code": "unauthorized", "message": "Unauthorized"},
                        },
                    ]
                )

            def send(self, _payload: str) -> None:
                return None

            def recv(self) -> str:
                return json.dumps(next(self._responses))

            def close(self) -> None:
                return None

        ha = HAClient("ws://example", "http://example", "token")
        with patch("hausie_addon.core.clients.ha_client.websocket.create_connection", return_value=RejectedSocket()):
            with self.assertRaisesRegex(RuntimeError, "config/auth/create.*Unauthorized"):
                ha._auth_ws_call("config/auth/create")

    def test_admin_client_uses_installer_token_directly_for_user_provisioning(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            ha = addon_server._resolve_ha_admin_client("administrator-token")

        self.assertIsNotNone(ha)
        self.assertEqual(ha.token, "administrator-token")
        self.assertEqual(ha.ha_url_ws, "ws://homeassistant:8123/api/websocket")
        self.assertEqual(ha.ha_url_rest, "http://homeassistant:8123/api")

    def test_settings_use_supervisor_proxy_when_running_as_an_addon(self) -> None:
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "supervisor-token"}, clear=True):
            settings = Settings()

        self.assertEqual(settings.HA_TOKEN, "supervisor-token")
        self.assertEqual(settings.HA_WS_URL, "ws://supervisor/core/websocket")
        self.assertEqual(settings.HA_REST_URL, "http://supervisor/core/api")

    def test_setup_explains_when_installer_token_is_not_an_administrator(self) -> None:
        ha = Mock()
        ha.fetch_current_user.return_value = {"name": "Guest", "is_admin": False}

        with (
            patch.object(
                addon_server,
                "resolve_ha_runtime_credentials",
                return_value=("administrator-token", "hausie_support_user", "support-password"),
            ),
            patch.object(addon_server, "load_device_state", return_value={}),
            patch.object(addon_server, "_resolve_ha_admin_client", return_value=ha),
        ):
            with self.assertRaisesRegex(RuntimeError, "Guest.*not an administrator"):
                addon_server._save_ha_credentials(
                    {
                        "ha_token": "administrator-token",
                        "admin_password": "administrator-password",
                        "support_password": "support-password",
                    }
                )

    def test_installer_can_persist_credentials_without_resetting_users_again(self) -> None:
        ha = Mock()
        ha.fetch_current_user.return_value = {"name": "Installer", "is_admin": True, "is_owner": True}
        ha.fetch_users.return_value = [
            {"id": "admin-user-id", "username": "hausie_admin", "isOwner": True, "isAdmin": True},
            {"id": "support-user-id", "username": "hausie_support_user", "isOwner": False, "isAdmin": True},
        ]
        state = {}
        validation = {"credentials_valid": True, "validation_error": ""}

        with (
            patch.object(
                addon_server,
                "resolve_ha_runtime_credentials",
                return_value=("", "hausie_support_user", ""),
            ),
            patch.object(addon_server, "load_device_state", return_value=state),
            patch.object(addon_server, "save_device_state") as save_state,
            patch.object(addon_server, "_resolve_ha_admin_client", return_value=ha),
            patch.object(addon_server, "_supervisor_request") as supervisor_request,
            patch.object(addon_server, "persist_ha_runtime_credentials") as persist_credentials,
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
                    "users_already_provisioned": True,
                }
            )

        self.assertEqual(result, validation)
        ha.change_auth_user_password.assert_not_called()
        ha.create_auth_user.assert_not_called()
        supervisor_request.assert_not_called()
        self.assertTrue(state["hausie_admin_password_configured"])
        save_state.assert_called_once_with(state)
        persist_credentials.assert_called_once_with(
            ha_token="new-token",
            ha_ui_username="hausie_support_user",
            ha_ui_password="new-support-password",
        )

    def test_password_change_uses_home_assistant_admin_websocket_command(self) -> None:
        ha = HAClient.__new__(HAClient)
        ha._auth_ws_call = Mock()

        ha.change_auth_user_password("existing-user-id", "new-password")

        ha._auth_ws_call.assert_called_once_with(
            "config/auth_provider/homeassistant/admin_change_password",
            {"user_id": "existing-user-id", "password": "new-password"},
        )

    def test_existing_hausie_users_are_updated_without_deletion(self) -> None:
        ha = Mock()
        ha.fetch_current_user.return_value = {"name": "Installer", "is_admin": True, "is_owner": True}
        ha.fetch_users.return_value = [
            {"id": "admin-user-id", "username": "hausie_admin", "isOwner": True, "isAdmin": True},
            {"id": "support-user-id", "username": "hausie_support_user", "isOwner": False, "isAdmin": True},
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
            patch.object(addon_server, "_resolve_ha_admin_client", return_value=ha),
            patch.object(addon_server, "_supervisor_request") as supervisor_request,
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
        ha.change_auth_user_password.assert_has_calls(
            [
                call("admin-user-id", "new-admin-password"),
                call("support-user-id", "new-support-password"),
            ]
        )
        self.assertEqual(ha.change_auth_user_password.call_count, 2)
        ha.delete_auth_user_by_username.assert_not_called()
        ha.create_auth_user.assert_not_called()
        for supervisor_call in supervisor_request.call_args_list:
            self.assertNotEqual(supervisor_call.args[:2], ("POST", "/auth/reset"))

    def test_home_assistant_os_resets_existing_managed_password_via_auth_api(self) -> None:
        ha = Mock()
        with (
            patch.dict("os.environ", {"SUPERVISOR_TOKEN": "supervisor-token"}, clear=True),
            patch.object(addon_server, "_supervisor_request") as supervisor_request,
        ):
            addon_server._set_local_hausie_password(
                ha,
                current_user={"name": "Installer", "is_admin": True, "is_owner": False},
                username="hausie_admin",
                user_id="admin-user-id",
                password="new-password",
            )

        supervisor_request.assert_called_once_with(
            "POST",
            "/auth/reset",
            {"username": "hausie_admin", "password": "new-password"},
            raise_on_error=True,
        )
        ha.change_auth_user_password.assert_not_called()


if __name__ == "__main__":
    unittest.main()
