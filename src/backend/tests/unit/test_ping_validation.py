import pytest

from app.tools.ping import PingTool


class TestPingValidation:
    def setup_method(self):
        self.tool = PingTool()

    def test_valid_params(self):
        params = {"target": "8.8.8.8"}
        result = self.tool.validate_params(params)
        assert result["target"] == "8.8.8.8"
        assert result["count"] == 4
        assert result["timeout"] == 10

    def test_default_values(self):
        result = self.tool.validate_params({"target": "1.1.1.1"})
        assert result["count"] == 4
        assert result["timeout"] == 10
        assert result["packet_size"] == 56
        assert result["df_bit"] is False
        assert result["dscp"] == 0
        assert result["max_duration"] == 30

    def test_empty_target(self):
        with pytest.raises(ValueError, match="Target is required"):
            self.tool.validate_params({"target": ""})

    def test_count_out_of_range(self):
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "count": 101})
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "count": -1})

    def test_timeout_out_of_range(self):
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "timeout": 0})
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "timeout": 61})

    def test_packet_size_out_of_range(self):
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "packet_size": 7})
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "packet_size": 65508})

    def test_dscp_out_of_range(self):
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "dscp": -1})
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "dscp": 64})

    def test_max_duration_out_of_range(self):
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "max_duration": 0})
        with pytest.raises(ValueError):
            self.tool.validate_params({"target": "8.8.8.8", "max_duration": 301})
