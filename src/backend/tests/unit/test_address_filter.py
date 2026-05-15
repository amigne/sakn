import pytest

from app.security.address_filter import is_ip_blocked, filter_target, BLOCKED_NETWORKS


class TestIsIPBlocked:
    @pytest.mark.parametrize("ip", [
        "127.0.0.1",
        "127.255.255.255",
        "10.0.0.1",
        "10.255.255.255",
        "192.168.1.1",
        "192.168.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "255.255.255.255",
        "169.254.1.1",
        "100.64.0.1",
        "172.17.0.1",
        "172.18.0.1",
        "192.0.2.1",
        "198.51.100.1",
        "203.0.113.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff00::1",
    ])
    def test_blocked_ips(self, ip):
        assert is_ip_blocked(ip) is True, f"{ip} should be blocked"

    @pytest.mark.parametrize("ip", [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",
        "208.67.222.222",
        "2001:4860:4860::8888",
        "2606:4700:4700::1111",
    ])
    def test_allowed_ips(self, ip):
        assert is_ip_blocked(ip) is False, f"{ip} should be allowed"

    def test_invalid_ip_is_blocked(self):
        assert is_ip_blocked("not-an-ip") is True


@pytest.mark.asyncio
async def test_filter_target_ip_direct():
    ip, error = await filter_target("8.8.8.8")
    assert ip == "8.8.8.8"
    assert error is None


@pytest.mark.asyncio
async def test_filter_target_private_ip():
    ip, error = await filter_target("127.0.0.1")
    assert ip == ""
    assert error == "errors.target_not_allowed"


@pytest.mark.asyncio
async def test_filter_target_loopback_ipv6():
    ip, error = await filter_target("::1")
    assert ip == ""
    assert error == "errors.target_not_allowed"


@pytest.mark.asyncio
async def test_filter_target_invalid():
    ip, error = await filter_target("not_a_valid_target_!!!")
    assert ip == ""
    assert error is not None


def test_blocked_networks_count():
    assert len(BLOCKED_NETWORKS) > 15
