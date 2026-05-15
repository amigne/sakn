import pytest

from app.tools.traceroute import TracerouteTool


class TestTracerouteValidation:
    def setup_method(self):
        self.tool = TracerouteTool()

    def test_valid_params_defaults(self):
        result = self.tool.validate_params({"target": "8.8.8.8"})
        assert result["target"] == "8.8.8.8"
        assert result["protocol"] == "udp"
        assert result["port"] == 33434
        assert result["probes_per_hop"] == 3
        assert result["timeout"] == 1
        assert result["max_distance"] == 30
        assert result["dns_resolution"] is True

    def test_empty_target(self):
        with pytest.raises(ValueError, match="Target is required"):
            self.tool.validate_params({"target": ""})

    def test_invalid_protocol(self):
        with pytest.raises(ValueError, match="Protocol must be"):
            self.tool.validate_params({"target": "8.8.8.8", "protocol": "http"})

    def test_port_out_of_range(self):
        with pytest.raises(ValueError, match="Port must be 1-65535"):
            self.tool.validate_params({"target": "8.8.8.8", "port": 0})
        with pytest.raises(ValueError, match="Port must be 1-65535"):
            self.tool.validate_params({"target": "8.8.8.8", "port": 65536})

    def test_probes_per_hop_out_of_range(self):
        with pytest.raises(ValueError, match="Probes per hop must be 1-10"):
            self.tool.validate_params({"target": "8.8.8.8", "probes_per_hop": 0})
        with pytest.raises(ValueError, match="Probes per hop must be 1-10"):
            self.tool.validate_params({"target": "8.8.8.8", "probes_per_hop": 11})

    def test_timeout_out_of_range(self):
        with pytest.raises(ValueError, match="Timeout must be 1-30"):
            self.tool.validate_params({"target": "8.8.8.8", "timeout": 0})
        with pytest.raises(ValueError, match="Timeout must be 1-30"):
            self.tool.validate_params({"target": "8.8.8.8", "timeout": 31})

    def test_max_distance_out_of_range(self):
        with pytest.raises(ValueError, match="Max distance must be 1-64"):
            self.tool.validate_params({"target": "8.8.8.8", "max_distance": 0})
        with pytest.raises(ValueError, match="Max distance must be 1-64"):
            self.tool.validate_params({"target": "8.8.8.8", "max_distance": 65})

    def test_protocol_modes(self):
        for proto in ("udp", "icmp", "tcp"):
            result = self.tool.validate_params({"target": "8.8.8.8", "protocol": proto})
            assert result["protocol"] == proto

    def test_dns_resolution_false(self):
        result = self.tool.validate_params({"target": "8.8.8.8", "dns_resolution": False})
        assert result["dns_resolution"] is False
