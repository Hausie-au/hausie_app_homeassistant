from __future__ import annotations

import sys
import unittest
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon.core.managers.config_manager import ConfigManager  # noqa: E402


class DashboardRegistrationTests(unittest.TestCase):
    def test_main_dashboard_is_never_registered_as_yaml(self) -> None:
        config = {
            "lovelace": {
                "dashboards": {
                    "hausie-dashboard": {
                        "mode": "yaml",
                        "title": "Hausie",
                        "filename": "dashboards/hausie_dashboard.yaml",
                    },
                    "customer-dashboard": {
                        "mode": "yaml",
                        "title": "Customer dashboard",
                        "filename": "dashboards/customer.yaml",
                    },
                }
            }
        }

        updated = ConfigManager._ensure_config_dashboard(config)
        dashboards = updated["lovelace"]["dashboards"]

        self.assertNotIn("hausie-dashboard", dashboards)
        self.assertEqual(dashboards["config-dashboard"]["mode"], "yaml")
        self.assertIn("customer-dashboard", dashboards)

    def test_repair_removes_all_hausie_config_entries_before_clean_rewrite(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "configuration.yaml"
            config_path.write_text(
                """lovelace:
  dashboards:
    config-dashboard:
      mode: yaml
      filename: dashboards/hausie_configuration_dashboard.yaml
    customer-dashboard:
      mode: yaml
      filename: dashboards/customer.yaml
rest_command:
  rebuild_hausie:
    url: http://hausie/run/rebuild_hausie
  core_system_repair:
    url: http://hausie/run/rebuild_hausie
  create_test:
    url: http://hausie/run/create_test
  customer_command:
    url: http://customer/action
shell_command:
  hausie_update_new_device: echo hausie
  customer_command: echo customer
cloud: {}
recorder: {}
history: {}
""",
                encoding="utf-8",
            )
            manager = ConfigManager(
                pi_sender=None,
                config_path=str(config_path),
                require_remote=False,
            )
            manager.local_config_path = Path(temp_dir) / "generated_configuration.yaml"

            changed = manager.remove_hausie_entries(
                keep_test_dashboard=False,
                keep_test_assets=False,
            )
            cleaned = config_path.read_text(encoding="utf-8")

            self.assertTrue(changed)
            self.assertNotIn("config-dashboard:", cleaned)
            self.assertNotIn("rebuild_hausie:", cleaned)
            self.assertNotIn("core_system_repair:", cleaned)
            self.assertNotIn("create_test:", cleaned)
            self.assertNotIn("hausie_update_new_device:", cleaned)
            self.assertNotIn("cloud:", cleaned)
            self.assertNotIn("recorder:", cleaned)
            self.assertNotIn("history:", cleaned)
            self.assertIn("customer-dashboard:", cleaned)
            self.assertIn("customer_command:", cleaned)

            manager.sync_config_dashboard()
            rebuilt = config_path.read_text(encoding="utf-8")
            self.assertIn("config-dashboard:", rebuilt)
            self.assertIn("core_system_repair:", rebuilt)
            self.assertIn("test_system_create_test:", rebuilt)
            self.assertNotIn("\n  create_test:", rebuilt)
            self.assertIn("cloud:", rebuilt)
            self.assertIn("recorder:", rebuilt)
            self.assertIn("history:", rebuilt)
            self.assertIn("customer-dashboard:", rebuilt)
            self.assertIn("customer_command:", rebuilt)


if __name__ == "__main__":
    unittest.main()
