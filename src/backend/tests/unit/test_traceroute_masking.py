from app.websocket.handlers.traceroute_ws import mask_private_hops


class TestMaskPrivateHops:
    """Issue #212: _mask_private preserves probes when collapsing multipath hops."""

    def test_show_private_true_returns_unchanged(self):
        """When show_private is True, data passes through unmodified."""
        data = {"ip": "192.168.1.1", "hostname": "router.home", "probes": [
            {"rtt_ms": 2.334, "status": "ok"},
        ], "reached": False}
        result = mask_private_hops(dict(data), show_private=True)
        assert result == data

    def test_single_ip_public_unchanged(self):
        """Public IP in a regular hop is not masked."""
        data = {"ip": "8.8.8.8", "hostname": "dns.google", "probes": [
            {"rtt_ms": 20.456, "status": "ok"},
        ], "reached": False}
        result = mask_private_hops(dict(data), show_private=False)
        assert result["ip"] == "8.8.8.8"
        assert result["hostname"] == "dns.google"
        assert len(result["probes"]) == 1

    def test_single_ip_private_masked(self):
        """Private IP in a regular hop is masked to [hidden]."""
        data = {"ip": "192.168.1.1", "hostname": "router.home", "probes": [
            {"rtt_ms": 2.334, "status": "ok"},
            {"rtt_ms": 2.123, "status": "ok"},
        ], "reached": False}
        result = mask_private_hops(data, show_private=False)
        assert result["ip"] == "[hidden]"
        assert result["hostname"] is None
        # Probes ARE preserved for regular hops
        assert len(result["probes"]) == 2
        assert result["probes"][0]["rtt_ms"] == 2.334

    def test_single_ip_null_unchanged(self):
        """Timeout hop (ip=None) is not affected by masking."""
        data = {"ip": None, "hostname": None, "probes": [
            {"rtt_ms": None, "status": "timeout"},
        ], "reached": False}
        result = mask_private_hops(data, show_private=False)
        assert result["ip"] is None
        assert result["hostname"] is None
        assert len(result["probes"]) == 1

    def test_multipath_mixed_public_private(self):
        """Multipath with public+private IPs: private paths masked, structure kept."""
        data = {
            "multipath": True,
            "paths": [
                {"ip": "192.168.1.1", "hostname": "router.home", "probes": [
                    {"rtt_ms": 2.334, "status": "ok"},
                ]},
                {"ip": "8.8.8.8", "hostname": "dns.google", "probes": [
                    {"rtt_ms": 15.234, "status": "ok"},
                ]},
            ],
            "reached": False,
        }
        result = mask_private_hops(data, show_private=False)
        assert result["multipath"] is True
        assert len(result["paths"]) == 2
        # Private path masked
        assert result["paths"][0]["ip"] == "[hidden]"
        assert result["paths"][0]["hostname"] is None
        assert result["paths"][0]["probes"][0]["rtt_ms"] == 2.334
        # Public path unchanged
        assert result["paths"][1]["ip"] == "8.8.8.8"
        assert result["paths"][1]["hostname"] == "dns.google"

    def test_multipath_all_private_collapsed_with_probes(self):
        """Issue #212: when all paths are private, hop is collapsed AND probes are preserved."""
        data = {
            "multipath": True,
            "paths": [
                {"ip": "192.168.1.1", "hostname": "router.home", "probes": [
                    {"rtt_ms": 2.334, "status": "ok"},
                    {"rtt_ms": 2.123, "status": "ok"},
                ]},
                {"ip": "10.0.0.1", "hostname": "core.local", "probes": [
                    {"rtt_ms": 5.678, "status": "ok"},
                ]},
            ],
            "reached": False,
        }
        result = mask_private_hops(data, show_private=False)
        # Collapsed
        assert result["multipath"] is False
        assert result["ip"] == "[hidden]"
        assert result["hostname"] is None
        # Paths removed
        assert "paths" not in result
        # Probes merged from all paths
        assert "probes" in result, "probes must be present after collapse"
        assert len(result["probes"]) == 3
        assert result["probes"][0]["rtt_ms"] == 2.334
        assert result["probes"][1]["rtt_ms"] == 2.123
        assert result["probes"][2]["rtt_ms"] == 5.678

    def test_multipath_all_private_with_timeout_probes(self):
        """Collapse preserves timeout probes from all paths."""
        data = {
            "multipath": True,
            "paths": [
                {"ip": "10.0.0.1", "hostname": None, "probes": [
                    {"rtt_ms": None, "status": "timeout"},
                ]},
                {"ip": "172.16.0.1", "hostname": None, "probes": [
                    {"rtt_ms": 1.234, "status": "ok"},
                ]},
            ],
            "reached": False,
        }
        result = mask_private_hops(data, show_private=False)
        assert result["multipath"] is False
        assert "probes" in result
        assert len(result["probes"]) == 2
        assert result["probes"][0]["status"] == "timeout"
        assert result["probes"][1]["status"] == "ok"

    def test_multipath_no_private_noop(self):
        """Multipath with all public IPs: no masking happens."""
        data = {
            "multipath": True,
            "paths": [
                {"ip": "8.8.8.8", "hostname": "dns.google", "probes": [
                    {"rtt_ms": 20.456, "status": "ok"},
                ]},
                {"ip": "1.1.1.1", "hostname": "one.one.one.one", "probes": [
                    {"rtt_ms": 15.234, "status": "ok"},
                ]},
            ],
            "reached": False,
        }
        result = mask_private_hops(data, show_private=False)
        assert result["multipath"] is True
        assert result["paths"][0]["ip"] == "8.8.8.8"
        assert result["paths"][1]["ip"] == "1.1.1.1"
