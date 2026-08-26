from hausie_addon.core import heartbeat
from hausie_addon.core.heartbeat import _supervisor_tailscale_ip


def test_supervisor_network_finds_tailscale_ip_from_interface_map():
    def request(method, path, payload):
        assert method == "GET"
        assert path == "/network/info"
        assert payload is None
        return {
            "result": "ok",
            "data": {
                "interfaces": {
                    "tailscale0": {
                        "ip_address": "100.101.102.103/32",
                    },
                },
            },
        }

    assert _supervisor_tailscale_ip(request) == (
        "100.101.102.103",
        "supervisor-network",
    )


def test_supervisor_network_ignores_non_tailscale_addresses():
    def request(method, path, payload):
        return {
            "data": {
                "interfaces": {
                    "eth0": {"ip_address": "192.168.1.20/24"},
                    "docker0": {"ip_address": "172.30.32.1/23"},
                },
            },
        }

    assert _supervisor_tailscale_ip(request) == ("", "missing")


def test_proc_network_finds_tailscale_ip_without_iproute2(monkeypatch):
    monkeypatch.setattr(
        heartbeat.Path,
        "read_text",
        lambda *args, **kwargs: """
Main:
    192.168.150.136
        /32 host LOCAL
    100.66.164.86
        /32 host LOCAL
""",
    )

    assert heartbeat._proc_tailscale_ip() == "100.66.164.86"


def test_resolver_ignores_manual_tailscale_option(monkeypatch):
    """The address must never come from an add-on option or environment var."""

    monkeypatch.setenv("HAUSIE_TAILSCALE_IP", "100.99.88.77")
    monkeypatch.setattr(heartbeat, "_run_command", lambda command: "")
    monkeypatch.setattr(heartbeat, "_proc_tailscale_ip", lambda: "")

    assert heartbeat._resolve_tailscale_ip() == ("", "missing")
