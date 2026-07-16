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


if __name__ == "__main__":
    unittest.main()
