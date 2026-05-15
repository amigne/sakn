from app.tools.traceroute import (
    TracerouteTool,
    _parse_probes_from_tokens,
    _extract_ip_hostname_map,
    _group_probes_by_ip,
    _is_ip,
)

# Sample traceroute output with DNS resolution
SAMPLE_OUTPUT_WITH_DNS = """traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  router.home (192.168.1.1)  2.334 ms  2.123 ms  2.456 ms
 2  10.0.0.1 (10.0.0.1)  5.678 ms  5.432 ms  5.901 ms
 3  * * *
 4  142.251.37.1 (142.251.37.1)  15.234 ms  15.890 ms  15.567 ms
 5  dns.google (8.8.8.8)  20.456 ms  20.123 ms  20.789 ms
"""

# Sample traceroute output without DNS resolution (-n)
SAMPLE_OUTPUT_NO_DNS = """traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  2.334 ms  2.123 ms  2.456 ms
 2  10.0.0.1  5.678 ms  5.432 ms  5.901 ms
 3  * * *
 4  142.251.37.1  15.234 ms  15.890 ms  15.567 ms
 5  8.8.8.8  20.456 ms  20.123 ms  20.789 ms
"""

# Multipath routing sample
SAMPLE_MULTIPATH = """traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  2.334 ms  2.123 ms  2.456 ms
 2  10.0.0.1  5.678 ms  *  5.901 ms
 3  142.251.37.1  15.234 ms  142.251.37.2  16.123 ms  15.890 ms
 4  8.8.8.8  20.456 ms  20.123 ms  20.789 ms
"""

# Empty/error output
SAMPLE_EMPTY = ""


class TestTracerouteParsing:
    def test_parse_basic_output_with_dns(self):
        hops = TracerouteTool._parse_output(SAMPLE_OUTPUT_WITH_DNS)
        assert len(hops) == 5

        # Hop 1: router.home (192.168.1.1)
        h1 = hops[0]
        assert h1["hop"] == 1
        assert h1["data"]["ip"] == "192.168.1.1"
        assert h1["data"]["hostname"] == "router.home"
        assert len(h1["data"]["probes"]) == 3
        assert h1["data"]["probes"][0] == {"rtt_ms": 2.334, "status": "ok"}

        # Hop 3: all timeouts
        h3 = hops[2]
        assert h3["hop"] == 3
        assert h3["data"]["ip"] is None
        assert h3["data"]["hostname"] is None
        for p in h3["data"]["probes"]:
            assert p["status"] == "timeout"

    def test_parse_basic_output_no_dns(self):
        hops = TracerouteTool._parse_output(SAMPLE_OUTPUT_NO_DNS)
        assert len(hops) == 5

        h1 = hops[0]
        assert h1["data"]["ip"] == "192.168.1.1"
        assert h1["data"]["hostname"] is None

    def test_parse_multipath(self):
        hops = TracerouteTool._parse_output(SAMPLE_MULTIPATH)
        assert len(hops) == 4

        # Hop 2: mixed timeout
        h2 = hops[1]
        assert h2["hop"] == 2
        assert h2["data"]["ip"] == "10.0.0.1"
        statuses = [p["status"] for p in h2["data"]["probes"]]
        assert "ok" in statuses
        assert "timeout" in statuses

        # Hop 3: multipath
        h3 = hops[2]
        assert h3["hop"] == 3
        assert h3["data"]["multipath"] is True
        paths = h3["data"]["paths"]
        assert len(paths) == 2
        ips = {p["ip"] for p in paths}
        assert ips == {"142.251.37.1", "142.251.37.2"}

    def test_parse_empty_output(self):
        assert TracerouteTool._parse_output(SAMPLE_EMPTY) == []

    def test_build_args_udp(self):
        args = TracerouteTool._build_args("8.8.8.8", {
            "protocol": "udp", "port": 33434, "probes_per_hop": 3,
            "timeout": 5, "max_distance": 30, "dns_resolution": True,
        })
        assert args[0] == "traceroute"
        assert "-p" in args and "33434" in args
        assert "-q" in args and "3" in args
        assert "-w" in args and "5" in args
        assert "-m" in args and "30" in args
        assert "-n" not in args
        assert "8.8.8.8" in args

    def test_build_args_icmp(self):
        args = TracerouteTool._build_args("8.8.8.8", {
            "protocol": "icmp", "port": 33434, "probes_per_hop": 3,
            "timeout": 5, "max_distance": 30, "dns_resolution": True,
        })
        assert "-I" in args
        assert "-p" not in args

    def test_build_args_tcp(self):
        args = TracerouteTool._build_args("8.8.8.8", {
            "protocol": "tcp", "port": 80, "probes_per_hop": 3,
            "timeout": 5, "max_distance": 30, "dns_resolution": True,
        })
        assert "-T" in args
        assert "-p" in args and "80" in args

    def test_build_args_no_dns(self):
        args = TracerouteTool._build_args("8.8.8.8", {
            "protocol": "udp", "port": 33434, "probes_per_hop": 3,
            "timeout": 5, "max_distance": 30, "dns_resolution": False,
        })
        assert "-n" in args


class TestProbeParsing:
    def test_parse_simple_probes(self):
        tokens = "192.168.1.1 2.334 ms 2.123 ms 2.456 ms".split()
        probes = _parse_probes_from_tokens(tokens)
        assert len(probes) == 3
        assert all(p["status"] == "ok" for p in probes)

    def test_parse_timeouts(self):
        tokens = "* * *".split()
        probes = _parse_probes_from_tokens(tokens)
        assert len(probes) == 3
        assert all(p["status"] == "timeout" for p in probes)

    def test_parse_mixed(self):
        tokens = "10.0.0.1 5.678 ms * 5.901 ms".split()
        probes = _parse_probes_from_tokens(tokens)
        assert len(probes) == 3
        assert probes[0]["status"] == "ok"
        assert probes[1]["status"] == "timeout"
        assert probes[2]["status"] == "ok"

    def test_parse_with_hostname(self):
        tokens = "router.home (192.168.1.1) 2.334 ms 2.123 ms".split()
        probes = _parse_probes_from_tokens(tokens)
        assert len(probes) == 2

    def test_extract_ip_map(self):
        tokens = "router.home (192.168.1.1) 2.334 ms 2.123 ms".split()
        ip_map = _extract_ip_hostname_map(tokens)
        assert ip_map == {"192.168.1.1": "router.home"}

    def test_extract_ip_map_no_hostname(self):
        tokens = "192.168.1.1 2.334 ms 2.123 ms".split()
        ip_map = _extract_ip_hostname_map(tokens)
        assert ip_map == {"192.168.1.1": None}

    def test_is_ip(self):
        assert _is_ip("192.168.1.1")
        assert _is_ip("8.8.8.8")
        assert _is_ip("::1")
        assert _is_ip("fe80::1")
        assert not _is_ip("router.home")
        assert not _is_ip("*")
        assert not _is_ip("2.334")
