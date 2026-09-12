from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from playwright.sync_api import TimeoutError


ADDON_ROOT = Path(__file__).resolve().parents[1] / "hausie"
sys.path.insert(0, str(ADDON_ROOT))

from hausie_addon.orchestration.dashboard_updater import DashboardUpdater  # noqa: E402


class DashboardLoginTests(unittest.TestCase):
    def test_login_wait_failure_is_reported(self) -> None:
        updater = DashboardUpdater.__new__(DashboardUpdater)
        updater.page = Mock()
        updater.page.url = "http://homeassistant:8123/"
        updater.page.wait_for_selector.side_effect = TimeoutError("timed out")
        updater._log = Mock()

        with patch.object(updater, "_is_logged_in", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "login did not become available within 30s"):
                updater._check_and_login()

        updater._log.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
