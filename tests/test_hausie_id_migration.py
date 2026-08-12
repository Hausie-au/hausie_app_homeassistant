from __future__ import annotations

import json

from hausie.hausie_addon.orchestration.new_device_dashboard import build_new_device_popup_card


def test_new_device_popup_uses_canonical_setup_ids() -> None:
    card = build_new_device_popup_card("device-1", "sensor.device_1", "Device 1")
    rendered = json.dumps(card)

    assert "input_text.setup_device_name" in rendered
    assert "input_text.setup_device_id" in rendered
    assert "input_select.setup_device_label" in rendered
    assert "input_select.setup_device_area" in rendered
    assert "input_button.setup_device_save" in rendered
    assert "input_text.new_device_name" not in rendered
    assert "input_button.new_device_save" not in rendered

