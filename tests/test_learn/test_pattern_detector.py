"""Tests for PatternDetector"""
import pytest
import time
from src.learn import PatternDetector, Pattern, Anomaly
from src.sense import Event, Metric


class TestPattern:
    """Tests for Pattern dataclass"""

    def test_pattern_creation(self):
        pattern = Pattern(
            pattern_type="high_frequency",
            description="Test pattern",
            confidence=0.8,
            occurrences=5,
            first_seen=time.time() - 10,
            last_seen=time.time(),
        )
        assert pattern.pattern_type == "high_frequency"
        assert pattern.confidence == 0.8

    def test_pattern_to_dict(self):
        pattern = Pattern(
            pattern_type="test",
            description="desc",
            confidence=0.9,
            occurrences=3,
            first_seen=1.0,
            last_seen=2.0,
        )
        d = pattern.to_dict()
        assert d["pattern_type"] == "test"
        assert d["occurrences"] == 3


class TestAnomaly:
    """Tests for Anomaly dataclass"""

    def test_anomaly_creation(self):
        anomaly = Anomaly(
            anomaly_type="deviation",
            severity="high",
            metric_name="response_time",
            expected_value=1.0,
            actual_value=5.0,
            deviation=4.0,
        )
        assert anomaly.anomaly_type == "deviation"
        assert anomaly.severity == "high"

    def test_anomaly_to_dict(self):
        anomaly = Anomaly(
            anomaly_type="test",
            severity="low",
            metric_name="metric",
            expected_value=1.0,
            actual_value=2.0,
            deviation=1.0,
        )
        d = anomaly.to_dict()
        assert d["severity"] == "low"


class TestPatternDetector:
    """Tests for PatternDetector"""

    def test_initialization(self):
        detector = PatternDetector()
        assert detector.get_cached_patterns() == []

    def test_analyze_events_empty(self):
        detector = PatternDetector()
        patterns = detector.analyze_events([])
        assert patterns == []

    def test_analyze_events_high_frequency(self):
        detector = PatternDetector(min_occurrences=3)
        now = time.time()
        events = [
            Event("error", "test", timestamp=now),
            Event("error", "test", timestamp=now + 0.1),
            Event("error", "test", timestamp=now + 0.2),
            Event("error", "test", timestamp=now + 0.3),
        ]

        patterns = detector.analyze_events(events)
        freq_patterns = [p for p in patterns if p.pattern_type == "high_frequency"]
        assert len(freq_patterns) > 0

    def test_analyze_events_sequence_pattern(self):
        detector = PatternDetector(min_occurrences=2)
        now = time.time()
        events = [
            Event("login", "test", timestamp=now),
            Event("error", "test", timestamp=now + 1),
            Event("login", "test", timestamp=now + 2),
            Event("error", "test", timestamp=now + 3),
            Event("login", "test", timestamp=now + 4),
            Event("error", "test", timestamp=now + 5),
        ]

        patterns = detector.analyze_events(events)
        seq_patterns = [p for p in patterns if p.pattern_type == "sequence"]
        assert len(seq_patterns) > 0

    def test_detect_metric_anomaly_not_enough_data(self):
        detector = PatternDetector()
        metrics = [
            Metric("test", 1.0),
            Metric("test", 2.0),
        ]
        anomaly = detector.detect_metric_anomaly(metrics)
        assert anomaly is None

    def test_detect_metric_anomaly_normal(self):
        detector = PatternDetector(anomaly_threshold=2.0)
        metrics = [
            Metric("test", 1.0),
            Metric("test", 1.1),
            Metric("test", 0.9),
            Metric("test", 1.0),
            Metric("test", 1.05),
        ]
        anomaly = detector.detect_metric_anomaly(metrics)
        assert anomaly is None

    def test_detect_metric_anomaly_detected(self):
        detector = PatternDetector(anomaly_threshold=2.0)
        metrics = [
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 10.0),
        ]
        anomaly = detector.detect_metric_anomaly(metrics)
        assert anomaly is not None
        assert anomaly.anomaly_type == "deviation"

    def test_detect_metric_anomaly_severity(self):
        detector = PatternDetector()
        metrics = [
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 100.0),
        ]
        anomaly = detector.detect_metric_anomaly(metrics)
        assert anomaly is not None
        assert anomaly.severity in ["low", "medium", "high", "critical"]

    def test_detect_trend_anomaly_not_enough_data(self):
        detector = PatternDetector()
        metrics = [Metric("test", 1.0)]
        anomaly = detector.detect_trend_anomaly(metrics)
        assert anomaly is None

    def test_detect_trend_anomaly_detected(self):
        detector = PatternDetector()
        metrics = [
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 1.0),
            Metric("test", 2.0),
            Metric("test", 3.0),
            Metric("test", 4.0),
        ]
        anomaly = detector.detect_trend_anomaly(metrics, expected_direction="stable")
        assert anomaly is not None
        assert anomaly.anomaly_type == "trend"

    def test_clear_cache(self):
        detector = PatternDetector(min_occurrences=2)
        now = time.time()
        events = [
            Event("e", "test", timestamp=now + i * 0.1)
            for i in range(5)
        ]
        detector.analyze_events(events)
        detector.clear_cache()
        assert detector.get_cached_patterns() == []
