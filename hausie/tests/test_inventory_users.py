from hausie_addon.core.clients.ha_client import HAClient


def test_normalize_users_marks_only_linked_people_as_configurable():
    users = [
        {"id": "mateo", "name": "Mateo", "group_ids": ["system-users"]},
        {"id": "hausie", "name": "hausie", "group_ids": ["system-admin"]},
    ]
    persons = {
        "storage": [{"id": "mateo-person", "name": "Mateo", "user_id": "mateo"}],
        "config": [],
    }

    normalized = HAClient._normalize_users(users, persons)

    assert normalized[0]["hasPerson"] is True
    assert normalized[1]["hasPerson"] is False
