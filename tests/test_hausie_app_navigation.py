from hausie.hausie_addon import addon_server


def test_hausie_app_info_path_uses_supervisor_assigned_slug(monkeypatch):
    monkeypatch.setattr(addon_server, "_SELF_ADDON_SLUG", None)
    monkeypatch.setattr(
        addon_server,
        "_supervisor_request",
        lambda *_args, **_kwargs: {"data": {"slug": "c5bb2897_hausie"}},
    )

    assert (
        addon_server._resolve_hausie_app_info_path()
        == "/config/app/c5bb2897_hausie/info"
    )
