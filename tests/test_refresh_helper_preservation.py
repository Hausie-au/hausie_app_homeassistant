from unittest.mock import Mock, patch

import yaml

from hausie.hausie_addon import addon_server


def test_refresh_reload_restores_all_existing_generated_helper_values(tmp_path):
    ha = Mock()
    log = Mock()
    snapshot = {
        "input_boolean.core_remote_support_enabled": {
            "domain": "input_boolean",
            "state": "on",
        },
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


def test_refresh_restores_missing_remote_support_helper_without_erasing_other_booleans(tmp_path):
    helper = tmp_path / "helpers" / "input_boolean" / "hausie_input_boolean_general.yaml"
    helper.parent.mkdir(parents=True)
    helper.write_text("other_toggle:\n  name: Other Toggle\n", encoding="utf-8")

    assert addon_server._ensure_remote_support_helper(tmp_path) is True
    doc = yaml.safe_load(helper.read_text(encoding="utf-8"))
    assert doc["other_toggle"] == {"name": "Other Toggle"}
    assert doc["core_remote_support_enabled"] == {"name": "Remote Support", "initial": "off"}
    assert addon_server._ensure_remote_support_helper(tmp_path) is False


def test_refresh_confirms_remote_support_is_loaded_after_reload():
    ha = Mock()
    log = Mock()
    ha.get_states.side_effect = [[], [{"entity_id": "input_boolean.core_remote_support_enabled", "state": "off"}]]

    addon_server._confirm_remote_support_entity(ha, log, attempts=2)

    ha.call_service.assert_not_called()


def test_refresh_fails_if_remote_support_stays_unavailable():
    ha = Mock()
    log = Mock()
    ha.get_states.return_value = [{"entity_id": "input_boolean.core_remote_support_enabled", "state": "unavailable"}]

    with patch.object(addon_server.time, "sleep"):
        try:
            addon_server._confirm_remote_support_entity(ha, log, attempts=2)
        except RuntimeError as exc:
            assert "input_boolean.core_remote_support_enabled" in str(exc)
        else:
            raise AssertionError("Refresh must fail when the toggle is unavailable")


def test_remote_support_ready_recovers_after_final_restart(tmp_path):
    ha = Mock()
    log = Mock()
    ha.get_states.side_effect = [
        [{"entity_id": "input_boolean.core_remote_support_enabled", "state": "unavailable"}],
        [{"entity_id": "input_boolean.core_remote_support_enabled", "state": "off"}],
    ]

    with (
        patch.object(addon_server, "_ha_config_root", return_value=tmp_path),
        patch.object(addon_server, "_ensure_remote_support_helper") as ensure_helper,
        patch.object(addon_server, "_reload_services") as reload_services,
        patch.dict("os.environ", {"PI_CONFIG_PATH": ""}),
    ):
        addon_server._ensure_remote_support_entity_ready(ha, log, attempts=1)

    ensure_helper.assert_called_once_with(tmp_path)
    reload_services.assert_called_once_with(ha, log)
