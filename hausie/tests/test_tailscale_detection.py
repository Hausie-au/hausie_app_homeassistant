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
