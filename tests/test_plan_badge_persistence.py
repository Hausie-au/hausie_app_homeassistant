from pathlib import Path

import yaml

from hausie.hausie_addon import addon_server


def test_plan_badge_initial_values_are_updated_for_restart(tmp_path: Path) -> None:
    helper_dir = tmp_path / "helpers" / "input_text"
    helper_dir.mkdir(parents=True)
    helper_path = helper_dir / "hausie_input_text.dashboards.yaml"
    helper_path.write_text(
        yaml.safe_dump(
            {
                "hausie_plan_text": {
                    "name": "Hausie Plan",
                    "max": 255,
                    "initial": "Essential",
                    "icon": "mdi:home-heart",
                },
                "hausie_plan_details": {
                    "name": "Hausie Plan Details",
                    "max": 255,
                    "initial": "Old details",
                },
                "hausie_trial_until": {
                    "name": "Hausie Trial Until",
                    "max": 255,
                    "initial": "Old trial",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    addon_server._ensure_plan_text_helper(
        tmp_path,
        {
            "name": "Complete",
            "details": "Current plan details",
            "trial_until": "Aug 31, 2026",
        },
    )

    updated = yaml.safe_load(helper_path.read_text(encoding="utf-8"))
    assert updated["hausie_plan_text"]["initial"] == "Complete"
    assert updated["hausie_plan_text"]["icon"] == "mdi:home-heart"
    assert updated["hausie_plan_details"]["initial"] == "Current plan details"
    assert updated["hausie_trial_until"]["initial"] == "Aug 31, 2026"


def test_plan_badge_helpers_are_not_restored_from_pre_repair_snapshot() -> None:
    assert not addon_server._should_persist_rebuild_helper("input_text", "hausie_plan_text")
    assert not addon_server._should_persist_rebuild_helper("input_text", "hausie_plan_details")
    assert not addon_server._should_persist_rebuild_helper("input_text", "hausie_trial_until")
