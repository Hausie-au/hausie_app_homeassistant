import json
import tempfile
import unittest
from pathlib import Path

from hausie_addon.core.component_updates import (
    ComponentUpdateManager,
    _find_update_entity,
    get_component_versions,
    normalize_version,
)


class ComponentUpdateTests(unittest.TestCase):
    def test_reports_versions_from_installed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "custom_components" / "browser_mod" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"version": "3.0.2"}), encoding="utf-8")
            button = root / "www" / "community" / "button-card" / "button-card.js"
            button.parent.mkdir(parents=True)
            button.write_text(
                'console.info("BUTTON-CARD ", "v".concat("7.0.1", " "));',
                encoding="utf-8",
            )

            versions = get_component_versions(root)

            self.assertEqual(versions["browser_mod"]["version"], "3.0.2")
            self.assertEqual(versions["button_card"]["version"], "7.0.1")

    def test_finds_exact_hacs_update_entities(self) -> None:
        states = [
            {
                "entity_id": "update.slider_button_card_update",
                "attributes": {"friendly_name": "Slider Button Card"},
            },
            {
                "entity_id": "update.button_card_update",
                "attributes": {
                    "friendly_name": "Button Card update",
                    "repository": "custom-cards/button-card",
                },
            },
        ]

        selected = _find_update_entity(states, "button_card")

        self.assertIsNotNone(selected)
        self.assertEqual(selected["entity_id"], "update.button_card_update")

    def test_version_comparison_ignores_release_v_prefix(self) -> None:
        self.assertEqual(normalize_version("v7.0.1"), normalize_version("7.0.1"))

    def test_direct_button_card_install_replaces_asset_atomically(self) -> None:
        class NoopLog:
            def start(self, _message: str) -> None:
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ComponentUpdateManager(
                ha_client=object(),
                log=NoopLog(),
                config_root=root,
                state_path=root / "state.json",
            )
            manager._download = lambda *_args, **_kwargs: (
                b'console.info("BUTTON-CARD", "v7.0.1");'
            )

            manager._install_button_card_direct("7.0.1")

            installed = root / "www" / "community" / "button-card" / "button-card.js"
            self.assertTrue(installed.exists())
            self.assertIn("7.0.1", installed.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
