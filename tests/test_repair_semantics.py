from pathlib import Path
from unittest.mock import patch

from hausie.hausie_addon import addon_server


def test_clean_repair_deletes_then_rebuilds_everything() -> None:
    with (
        patch.object(addon_server, "_cleanup_base_assets") as cleanup_base,
        patch.object(addon_server, "_cleanup_hausie_assets") as cleanup_hausie,
        patch.object(addon_server, "_run_create_base") as create_base,
        patch.object(addon_server, "_run_sync_inventory") as sync_inventory,
        patch.object(addon_server, "_normalize_plan_id", return_value="plan_2"),
    ):
        addon_server._execute_clean_repair(plan_override="plan_2")

    cleanup_base.assert_called_once_with(preserve_test_assets=False)
    cleanup_hausie.assert_called_once_with(
        destructive_reset=True,
        preserve_test_assets=False,
    )
    create_base.assert_called_once_with(
        force_full=True,
        plan_override="plan_2",
        manage_activity=False,
    )
    sync_inventory.assert_called_once_with(
        force_full=True,
        plan_override="plan_2",
        manage_activity=False,
    )


def test_refresh_does_not_use_destructive_cleanup() -> None:
    with (
        patch.object(addon_server, "_cleanup_base_assets") as cleanup_base,
        patch.object(addon_server, "_cleanup_hausie_assets") as cleanup_hausie,
        patch.object(addon_server, "Settings") as settings_type,
        patch.object(addon_server, "HAClient", side_effect=RuntimeError("stop after entry")),
    ):
        settings_type.return_value.HAUSIE_CLOUD_URL = "https://cloud.example"
        try:
            addon_server._run_sync_inventory()
        except RuntimeError as exc:
            assert str(exc) == "stop after entry"

    cleanup_base.assert_not_called()
    cleanup_hausie.assert_not_called()


def test_cleanup_only_deletes_hausie_prefixed_yaml_files(tmp_path: Path) -> None:
    for folder in ("automations", "groups", "covers", "scripts", "switches"):
        target = tmp_path / folder
        target.mkdir(parents=True)
        (target / "hausie_generated.yaml").write_text("generated: true\n", encoding="utf-8")
        (target / "customer_owned.yaml").write_text("keep: true\n", encoding="utf-8")

    helper_dir = tmp_path / "helpers" / "input_boolean"
    helper_dir.mkdir(parents=True)
    (helper_dir / "hausie_generated.yaml").write_text("generated: true\n", encoding="utf-8")
    (helper_dir / "customer_owned.yaml").write_text("keep: true\n", encoding="utf-8")

    with (
        patch.object(addon_server, "_ha_config_root", return_value=tmp_path),
        patch.object(addon_server, "ConfigManager"),
        patch.dict("os.environ", {"PI_CONFIG_PATH": ""}),
    ):
        addon_server._cleanup_base_assets()
        addon_server._cleanup_hausie_assets(destructive_reset=False)

    for folder in ("automations", "groups", "covers", "scripts", "switches"):
        assert not (tmp_path / folder / "hausie_generated.yaml").exists()
        assert (tmp_path / folder / "customer_owned.yaml").exists()
    assert not (helper_dir / "hausie_generated.yaml").exists()
    assert (helper_dir / "customer_owned.yaml").exists()
