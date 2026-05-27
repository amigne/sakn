from app.tools.ping import PingTool

SAMPLE_PING_OUTPUT = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=10.3 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=119 time=10.5 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=119 time=10.2 ms
64 bytes from 8.8.8.8: icmp_seq=4 ttl=119 time=10.8 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3005ms
rtt min/avg/max/mdev = 10.200/10.450/10.800/0.238 ms
"""


class TestPingParsing:
    def test_parse_lines(self):
        lines = PingTool._parse_output(SAMPLE_PING_OUTPUT)
        assert len(lines) == 4
        assert lines[0] == {"bytes": 64, "from": "8.8.8.8", "seq": 1, "ttl": 119, "rtt_ms": 10.3, "status": "ok"}
        assert lines[3] == {"bytes": 64, "from": "8.8.8.8", "seq": 4, "ttl": 119, "rtt_ms": 10.8, "status": "ok"}

    def test_parse_summary(self):
        summary = PingTool._parse_summary(SAMPLE_PING_OUTPUT)
        assert summary["transmitted"] == 4
        assert summary["received"] == 4
        assert summary["lost"] == 0
        assert summary["loss_pct"] == 0.0
        assert summary["rtt_min_ms"] == 10.2
        assert summary["rtt_avg_ms"] == 10.45
        assert summary["rtt_max_ms"] == 10.8

    def test_parse_timeout_line(self):
        output = "Request timeout for icmp_seq 5\n"
        lines = PingTool._parse_output(output)
        assert len(lines) == 1
        assert lines[0]["status"] == "timeout"

    def test_parse_empty_output(self):
        assert PingTool._parse_output("") == []
        assert PingTool._parse_summary("")["transmitted"] == 0

    def test_parse_partial_loss(self):
        output = """PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=10.3 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 1 received, 75% packet loss, time 3005ms
"""
        lines = PingTool._parse_output(output)
        assert len(lines) == 1
        summary = PingTool._parse_summary(output)
        assert summary["transmitted"] == 4
        assert summary["received"] == 1
        assert summary["lost"] == 3
        assert summary["loss_pct"] == 75.0

    def test_build_args_basic(self):
        args = PingTool._build_args(
            "8.8.8.8",
            {"count": 4, "timeout": 10, "packet_size": 56, "df_bit": False,
             "dscp": 0, "max_duration": 30},
        )
        assert args[0] == "ping"
        assert "8.8.8.8" in args
        assert "-c" in args and "4" in args
        assert "-W" in args and "10" in args
        assert "-s" in args and "56" in args

    def test_build_args_df_bit(self):
        args = PingTool._build_args(
            "8.8.8.8",
            {"count": 4, "timeout": 10, "packet_size": 56, "df_bit": True,
             "dscp": 0, "max_duration": 30},
        )
        assert "-M" in args and "do" in args

    def test_build_args_dscp(self):
        args = PingTool._build_args(
            "8.8.8.8",
            {"count": 4, "timeout": 10, "packet_size": 56, "df_bit": False,
             "dscp": 46, "max_duration": 30},
        )
        assert "-Q" in args and "184" in args  # 46 << 2 = 184 (DSCP → TOS)

    def test_build_args_unlimited_count(self):
        args = PingTool._build_args(
            "8.8.8.8",
            {"count": 0, "timeout": 10, "packet_size": 56, "df_bit": False,
             "dscp": 0, "max_duration": 30},
        )
        assert "-c" not in args or args[args.index("-c") + 1] == "0"
