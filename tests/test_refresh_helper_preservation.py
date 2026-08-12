from unittest.mock import Mock, patch

from hausie.hausie_addon import addon_server


def test_refresh_reload_restores_all_existing_generated_helper_values(tmp_path):
    ha = Mock()
    log = Mock()
    snapshot = {
        "input_boolean.auto_living_room_blinds_widget_3_enabled": {
            "domain": "input_boolean",
            "state": "on",
        },
        "input_text.auto_living_room_blinds_widget_3_days": {
            "domain": "input_text",
            "state": "mon,wed,fri",
        },
        "input_datetime.auto_living_room_blinds_widget_3_up": {
            "domain": "input_datetime",
            "state": "07:30:00",
        },
        "input_number.auto_living_room_lights_lux_threshold": {
            "domain": "input_number",
            "state": "125",
        },
        "input_select.auto_living_room_night_mode_behavior": {
            "domain": "input_select",
            "state": "Cautious",
        },
    }

    with (
        patch.object(addon_server, "_ha_config_root", return_value=tmp_path),
        patch.object(addon_server, "_snapshot_rebuild_helper_values", return_value=snapshot) as capture,
        patch.object(addon_server, "_reload_services") as reload_services,
        patch.object(addon_server, "_wait_for_helper_entities_ready", return_value=True) as wait_ready,
        patch.object(addon_server, "_restore_rebuild_helper_values", return_value=len(snapshot)) as restore,
    ):
        preserved = addon_server._reload_services_preserving_helper_values(ha, log)

    assert preserved is True
    capture.assert_called_once_with(ha, tmp_path, log)
    reload_services.assert_called_once_with(ha, log)
    wait_ready.assert_called_once_with(
        ha,
        snapshot,
        log,
        timeout_s=30,
        interval_s=1,
    )
    restore.assert_called_once_with(ha, snapshot, log)


def test_first_refresh_without_existing_helpers_can_apply_initial_defaults(tmp_path):
    ha = Mock()
    log = Mock()

    with (
        patch.object(addon_server, "_ha_config_root", return_value=tmp_path),
        patch.object(addon_server, "_snapshot_rebuild_helper_values", return_value={}),
        patch.object(addon_server, "_reload_services") as reload_services,
        patch.object(addon_server, "_restore_rebuild_helper_values") as restore,
    ):
        preserved = addon_server._reload_services_preserving_helper_values(ha, log)

    assert preserved is False
    reload_services.assert_called_once_with(ha, log)
    restore.assert_not_called()
