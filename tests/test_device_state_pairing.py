from __future__ import annotations

import tempfile
from pathlib import Path

from hausie_addon.core.device_state import (
    clear_device_credentials,
    load_device_state,
    save_device_state,
)


def test_clear_device_credentials_preserves_local_hausie_setup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory) / "hausie_device.json"
        save_device_state(
            {
                "hausie_device_id": "hsd_old",
                "device_token": "old-device-token",
                "bootstrap_setup": {"initialized": True},
                "ha_token": "local-ha-token",
                "ha_ui_username": "hausie_support_user",
                "ha_ui_password": "support-password",
                "hausie_admin_password_configured": True,
                "ha_credentials_validation": {"valid": True},
            },
            state_path,
        )

        clear_device_credentials(path=state_path)

        state = load_device_state(state_path)
        assert "hausie_device_id" not in state
        assert "device_token" not in state
        assert "bootstrap_setup" not in state
        assert state["ha_token"] == "local-ha-token"
        assert state["ha_ui_password"] == "support-password"
        assert state["hausie_admin_password_configured"] is True
