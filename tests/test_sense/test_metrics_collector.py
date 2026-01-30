"""Tests for MetricsCollector"""
import pytest
from datetime import timedelta
from src.sense import MetricsCollector, Metric


class TestMetric:
    """Tests for Metric dataclass"""

    def test_metric_creation(self):
        metric = Metric(name="test", value=1.5)
        assert metric.name == "test"
        assert metric.value == 1.5
        assert metric.timestamp > 0
        assert metric.tags == {}

    def test_metric_with_tags(self):
        metric = Metric(name="test", value=1.0, tags={"env": "prod"})
        assert metric.tags == {"env": "prod"}


class TestMetricsCollector:
    """Tests for MetricsCollector"""

    def test_initialization(self):
        collector = MetricsCollector()
        assert collector.get_all_names() == []

    def test_record_metric(self):
        collector = MetricsCollector()
        collector.record("request.duration", 0.5)
        collector.record("request.duration", 0.3)

        latest = collector.get_latest("request.duration", 2)
        assert len(latest) == 2
        assert latest[-1].value == 0.3

    def test_record_with_tags(self):
        collector = MetricsCollector()
        collector.record("api.calls", 1.0, {"endpoint": "/api"})

        latest = collector.get_latest("api.calls", 1)
        assert latest[0].tags == {"endpoint": "/api"}

    def test_increment_counter(self):
        collector = MetricsCollector()
        collector.increment("requests")
        collector.increment("requests")
        collector.increment("requests", 3.0)

        assert collector.get_counter("requests") == 5.0

    def test_reset_counter(self):
        collector = MetricsCollector()
        collector.increment("test", 10.0)
        collector.reset_counter("test")
        assert collector.get_counter("test") == 0.0

    def test_get_aggregated(self):
        collector = MetricsCollector()
        collector.record("test", 1.0)
        collector.record("test", 2.0)
        collector.record("test", 3.0)

        agg = collector.get_aggregated("test", timedelta(hours=1))
        assert agg is not None
        assert agg.count == 3
        assert agg.sum == 6.0
        assert agg.avg == 2.0
        assert agg.min == 1.0
        assert agg.max == 3.0

    def test_get_aggregated_not_found(self):
        collector = MetricsCollector()
        agg = collector.get_aggregated("nonexistent", timedelta(hours=1))
        assert agg is None

    def test_get_aggregated_with_tag_filter(self):
        collector = MetricsCollector()
        collector.record("api", 1.0, {"env": "prod"})
        collector.record("api", 2.0, {"env": "dev"})
        collector.record("api", 3.0, {"env": "prod"})

        agg = collector.get_aggregated("api", timedelta(hours=1), {"env": "prod"})
        assert agg.count == 2
        assert agg.sum == 4.0

    def test_get_latest_empty(self):
        collector = MetricsCollector()
        latest = collector.get_latest("nonexistent")
        assert latest == []

    def test_get_all_names(self):
        collector = MetricsCollector()
        collector.record("metric1", 1.0)
        collector.record("metric2", 2.0)

        names = collector.get_all_names()
        assert "metric1" in names
        assert "metric2" in names

    def test_cleanup_old_metrics(self):
        collector = MetricsCollector(retention_seconds=0)
        collector.record("old", 1.0)

        removed = collector.cleanup()
        assert removed >= 0

    def test_clear(self):
        collector = MetricsCollector()
        collector.record("test", 1.0)
        collector.increment("counter")
        collector.clear()

        assert collector.get_all_names() == []
        assert collector.get_counter("counter") == 0.0

    def test_get_stats(self):
        collector = MetricsCollector()
        collector.record("m1", 1.0)
        collector.record("m2", 2.0)
        collector.increment("c1")

        stats = collector.get_stats()
        assert stats["metric_names"] == 2
        assert stats["counters"] == 1

    def test_max_points_limit(self):
        collector = MetricsCollector(max_points=5)
        for i in range(10):
            collector.record("test", float(i))

        latest = collector.get_latest("test", 10)
        assert len(latest) == 5

    def test_aggregated_rate(self):
        collector = MetricsCollector()
        collector.record("test", 1.0)
        collector.record("test", 2.0)

        agg = collector.get_aggregated("test", timedelta(seconds=10))
        assert agg.rate == 0.2
