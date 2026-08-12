"""Canonical Home Assistant IDs owned by the Hausie add-on.

Keep these values synchronized with ``hausie_cloud.core.utils.hausie_ids``.
HTTP endpoint paths are intentionally unchanged; these constants name Home
Assistant objects and services, not the add-on's public API routes.
"""

CORE_SYSTEM_REPAIR = "core_system_repair"
CORE_SYSTEM_REFRESH = "core_system_refresh"
CORE_SYSTEM_RESTART = "core_system_restart"
CORE_SYSTEM_BUSY = "core_system_busy"
CORE_SYSTEM_STATUS = "core_system_status"
CORE_PLAN_NAME = "core_plan_name"
CORE_PLAN_DETAILS = "core_plan_details"
CORE_PLAN_TRIAL_UNTIL = "core_plan_trial_until"
CORE_REMOTE_SUPPORT_ENABLED = "core_remote_support_enabled"

SETUP_DEVICE_START = "setup_device_start"
SETUP_DEVICE_SAVE = "setup_device_save"
SETUP_DEVICE_FOUND = "setup_device_found"
SETUP_DEVICE_NAME = "setup_device_name"
SETUP_DEVICE_ID = "setup_device_id"
SETUP_DEVICE_LABEL = "setup_device_label"
SETUP_DEVICE_AREA = "setup_device_area"

AUTO_SETUP_DEVICE_CREATED = "auto_setup_device_created"
AUTO_SETUP_DEVICE_SAVED = "auto_setup_device_saved"
AUTO_SETUP_DEVICES_DAILY_SCAN = "auto_setup_devices_daily_scan"
AUTO_SYSTEM_REPAIR_REQUESTED = "auto_system_repair_requested"
AUTO_SYSTEM_REFRESH_REQUESTED = "auto_system_refresh_requested"
AUTO_SYSTEM_RESTART_REQUESTED = "auto_system_restart_requested"

REST_SETUP_DEVICE_CREATE = "core_setup_device_create"
REST_SETUP_DEVICE_SAVE = "core_setup_device_save"
REST_SETUP_DEVICES_SCAN = "core_setup_devices_scan"
REST_NOTIFICATIONS_PUBLISH = "core_notifications_publish"
REST_UI_HELP_ROTATE = "core_ui_help_rotate"

TEST_SYSTEM_CLEANUP_BASE = "test_system_cleanup_base"
TEST_SYSTEM_CLEANUP_HAUSIE = "test_system_cleanup_hausie"
TEST_SYSTEM_CREATE_BASE = "test_system_create_base"
TEST_SYSTEM_CREATE_HAUSIE = "test_system_create_hausie"
TEST_SYSTEM_CREATE_TEST = "test_system_create_test"
TEST_SYSTEM_REBUILD_ALL = "test_system_rebuild_all"
TEST_UI_POPUP_UPDATE = "test_ui_popup_update"
TEST_UI_POPUP_WAIT = "test_ui_popup_wait"


def entity_id(domain: str, object_id: str) -> str:
    """Return a fully-qualified Home Assistant entity ID."""
    return f"{domain}.{object_id}"
