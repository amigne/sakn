"""Unit tests for Prometheus metrics (ADR-015)."""

from __future__ import annotations

import pytest


class TestMetricsDefinitions:
    """Verify all metric objects exist with correct types and labels."""

    def test_oui_sync_runs_total(self):
        from app.monitoring.metrics import oui_sync_runs_total

        from prometheus_client import Counter

        assert isinstance(oui_sync_runs_total, Counter)
        # prometheus_client strips the _total suffix from _name
        assert oui_sync_runs_total._name == "oui_sync_runs"
        assert set(oui_sync_runs_total._labelnames) == {"trigger", "status"}

    def test_oui_sync_duration_seconds(self):
        from app.monitoring.metrics import oui_sync_duration_seconds

        from prometheus_client import Histogram

        assert isinstance(oui_sync_duration_seconds, Histogram)
        assert oui_sync_duration_seconds._name == "oui_sync_duration_seconds"
        assert set(oui_sync_duration_seconds._labelnames) == {"trigger"}

    def test_oui_sync_records_total(self):
        from app.monitoring.metrics import oui_sync_records_total

        from prometheus_client import Counter

        assert isinstance(oui_sync_records_total, Counter)
        assert set(oui_sync_records_total._labelnames) == {"change_type"}

    def test_oui_sync_files_failed(self):
        from app.monitoring.metrics import oui_sync_files_failed

        from prometheus_client import Gauge

        assert isinstance(oui_sync_files_failed, Gauge)
        assert set(oui_sync_files_failed._labelnames) == {"file"}

    def test_oui_sync_consecutive_failures(self):
        from app.monitoring.metrics import oui_sync_consecutive_failures

        from prometheus_client import Gauge

        assert isinstance(oui_sync_consecutive_failures, Gauge)
        assert set(oui_sync_consecutive_failures._labelnames) == {"file"}

    def test_oui_sync_lock_acquisition_total(self):
        from app.monitoring.metrics import oui_sync_lock_acquisition_total

        from prometheus_client import Counter

        assert isinstance(oui_sync_lock_acquisition_total, Counter)
        assert set(oui_sync_lock_acquisition_total._labelnames) == {"outcome"}

    def test_mac_oui_lookup_requests_total(self):
        from app.monitoring.metrics import mac_oui_lookup_requests_total

        from prometheus_client import Counter

        assert isinstance(mac_oui_lookup_requests_total, Counter)
        assert set(mac_oui_lookup_requests_total._labelnames) == {"result"}

    def test_mac_oui_lookup_duration_seconds(self):
        from app.monitoring.metrics import mac_oui_lookup_duration_seconds

        from prometheus_client import Histogram

        assert isinstance(mac_oui_lookup_duration_seconds, Histogram)
        assert mac_oui_lookup_duration_seconds._name == "mac_oui_lookup_duration_seconds"


class TestMetricBehaviour:
    """Verify counters, gauges, and histograms behave correctly."""

    def test_counter_increments(self):
        from prometheus_client import Counter

        c = Counter("test_counter_total", "Test", ["label"])
        c.labels(label="a").inc()
        c.labels(label="a").inc(2)
        c.labels(label="b").inc()

        samples = {s.labels["label"]: s.value for s in c.collect()[0].samples if s.name == "test_counter_total"}
        assert samples["a"] == 3.0
        assert samples["b"] == 1.0

    def test_gauge_sets(self):
        from prometheus_client import Gauge

        g = Gauge("test_gauge", "Test", ["label"])
        g.labels(label="x").set(5)
        g.labels(label="x").set(0)

        samples = {s.labels["label"]: s.value for s in g.collect()[0].samples if s.name == "test_gauge"}
        assert samples["x"] == 0.0

    def test_histogram_observes(self):
        from prometheus_client import Histogram

        h = Histogram("test_histogram_seconds", "Test", buckets=(0.1, 0.5, 1.0))
        h.observe(0.3)
        h.observe(0.7)

        samples = {s.name: s.value for s in h.collect()[0].samples}
        assert samples["test_histogram_seconds_count"] == 2.0
        assert samples["test_histogram_seconds_sum"] == 1.0


class TestMetricsEndpoint:
    """Integration: /metrics endpoint is mounted and returns Prometheus format."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_accessible(self, client):
        response = await client.get("/metrics", follow_redirects=True)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_expected_metrics(self, client):
        response = await client.get("/metrics", follow_redirects=True)
        text = response.text

        # OUI sync metrics should be registered (even if zero)
        assert "oui_sync_runs_total" in text
        assert "oui_sync_duration_seconds" in text
        assert "oui_sync_records_total" in text
        assert "oui_sync_files_failed" in text
        assert "oui_sync_consecutive_failures" in text
        assert "oui_sync_lock_acquisition_total" in text

        # MAC OUI lookup metrics should be registered
        assert "mac_oui_lookup_requests_total" in text
        assert "mac_oui_lookup_duration_seconds" in text

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_auth_required(self, client):
        """Metrics endpoint is accessible without authentication (secure at proxy)."""
        response = await client.get("/metrics", follow_redirects=True)
        assert response.status_code == 200
