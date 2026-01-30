"""
Pattern Detector - Detect patterns and anomalies in data
"""
import time
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from ..sense import Event, Metric


@dataclass
class Pattern:
    """Detected pattern"""
    pattern_type: str
    description: str
    confidence: float
    occurrences: int
    first_seen: float
    last_seen: float
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "data": self.data,
        }


@dataclass
class Anomaly:
    """Detected anomaly"""
    anomaly_type: str
    severity: str  # "low", "medium", "high", "critical"
    metric_name: str
    expected_value: float
    actual_value: float
    deviation: float
    timestamp: float = field(default_factory=time.time)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "metric_name": self.metric_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "deviation": self.deviation,
            "timestamp": self.timestamp,
            "description": self.description,
        }


class PatternDetector:
    """
    Detects patterns and anomalies in events and metrics.

    Example:
        detector = PatternDetector()
        patterns = detector.analyze_events(event_history)
        anomaly = detector.detect_metric_anomaly(metrics, "response_time")
    """

    def __init__(
        self,
        anomaly_threshold: float = 2.0,
        min_occurrences: int = 3,
    ):
        self._anomaly_threshold = anomaly_threshold
        self._min_occurrences = min_occurrences
        self._pattern_cache: dict[str, Pattern] = {}

    def analyze_events(self, events: list[Event]) -> list[Pattern]:
        """
        Analyze events to find patterns.

        Args:
            events: List of events to analyze

        Returns:
            List of detected patterns
        """
        if not events:
            return []

        patterns = []
        event_types: dict[str, list[Event]] = {}
        for event in events:
            if event.event_type not in event_types:
                event_types[event.event_type] = []
            event_types[event.event_type].append(event)

        for event_type, type_events in event_types.items():
            if len(type_events) >= self._min_occurrences:
                pattern = self._detect_frequency_pattern(event_type, type_events)
                if pattern:
                    patterns.append(pattern)

        patterns.extend(self._detect_sequence_patterns(events))

        return patterns

    def _detect_frequency_pattern(
        self,
        event_type: str,
        events: list[Event],
    ) -> Optional[Pattern]:
        """Detect high-frequency event patterns"""
        if len(events) < self._min_occurrences:
            return None

        timestamps = [e.timestamp for e in events]
        if len(timestamps) < 2:
            return None

        intervals = [
            timestamps[i+1] - timestamps[i]
            for i in range(len(timestamps) - 1)
        ]
        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        if avg_interval > 0 and avg_interval < 1.0:
            pattern_key = f"high_frequency:{event_type}"
            confidence = min(1.0, len(events) / 10)

            pattern = Pattern(
                pattern_type="high_frequency",
                description=f"High frequency of '{event_type}' events",
                confidence=confidence,
                occurrences=len(events),
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                data={
                    "event_type": event_type,
                    "avg_interval": avg_interval,
                    "events_per_second": 1.0 / avg_interval if avg_interval > 0 else 0,
                },
            )
            self._pattern_cache[pattern_key] = pattern
            return pattern

        return None

    def _detect_sequence_patterns(self, events: list[Event]) -> list[Pattern]:
        """Detect event sequence patterns"""
        patterns = []
        if len(events) < 2:
            return patterns

        sequences: dict[tuple, int] = {}
        for i in range(len(events) - 1):
            seq = (events[i].event_type, events[i+1].event_type)
            sequences[seq] = sequences.get(seq, 0) + 1

        for seq, count in sequences.items():
            if count >= self._min_occurrences:
                pattern = Pattern(
                    pattern_type="sequence",
                    description=f"'{seq[0]}' often followed by '{seq[1]}'",
                    confidence=min(1.0, count / 5),
                    occurrences=count,
                    first_seen=events[0].timestamp,
                    last_seen=events[-1].timestamp,
                    data={"sequence": list(seq), "count": count},
                )
                patterns.append(pattern)

        return patterns

    def detect_metric_anomaly(
        self,
        metrics: list[Metric],
        baseline_avg: Optional[float] = None,
        baseline_std: Optional[float] = None,
    ) -> Optional[Anomaly]:
        """
        Detect anomalies in metric values.

        Args:
            metrics: List of metric data points
            baseline_avg: Expected average (calculated if not provided)
            baseline_std: Expected std deviation (calculated if not provided)

        Returns:
            Anomaly if detected, None otherwise
        """
        if len(metrics) < 3:
            return None

        values = [m.value for m in metrics]
        metric_name = metrics[0].name

        if baseline_avg is None:
            baseline_avg = sum(values[:-1]) / (len(values) - 1)
        if baseline_std is None:
            variance = sum((v - baseline_avg) ** 2 for v in values[:-1]) / (len(values) - 1)
            baseline_std = variance ** 0.5

        if baseline_std == 0:
            baseline_std = 0.1

        latest = values[-1]
        deviation = abs(latest - baseline_avg) / baseline_std

        if deviation >= self._anomaly_threshold:
            severity = self._calculate_severity(deviation)
            anomaly = Anomaly(
                anomaly_type="deviation",
                severity=severity,
                metric_name=metric_name,
                expected_value=baseline_avg,
                actual_value=latest,
                deviation=deviation,
                description=f"{metric_name} deviated {deviation:.1f} std from mean",
            )
            logger.warning(f"Anomaly detected: {anomaly.description}")
            return anomaly

        return None

    def _calculate_severity(self, deviation: float) -> str:
        """Calculate anomaly severity based on deviation"""
        if deviation >= 5.0:
            return "critical"
        elif deviation >= 4.0:
            return "high"
        elif deviation >= 3.0:
            return "medium"
        return "low"

    def detect_trend_anomaly(
        self,
        metrics: list[Metric],
        expected_direction: str = "stable",
    ) -> Optional[Anomaly]:
        """
        Detect unexpected trend changes.

        Args:
            metrics: List of metrics
            expected_direction: "up", "down", or "stable"

        Returns:
            Anomaly if unexpected trend detected
        """
        if len(metrics) < 5:
            return None

        values = [m.value for m in metrics]
        metric_name = metrics[0].name

        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_first == 0:
            return None

        change_rate = (avg_second - avg_first) / abs(avg_first)
        actual_direction = "up" if change_rate > 0.1 else "down" if change_rate < -0.1 else "stable"

        if actual_direction != expected_direction:
            return Anomaly(
                anomaly_type="trend",
                severity="medium",
                metric_name=metric_name,
                expected_value=avg_first,
                actual_value=avg_second,
                deviation=abs(change_rate),
                description=f"Expected {expected_direction} trend but got {actual_direction}",
            )

        return None

    def clear_cache(self) -> None:
        """Clear pattern cache"""
        self._pattern_cache.clear()

    def get_cached_patterns(self) -> list[Pattern]:
        """Get all cached patterns"""
        return list(self._pattern_cache.values())
