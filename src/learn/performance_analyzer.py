"""
Performance Analyzer - Analyze and report on system performance
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import timedelta
from loguru import logger

from ..sense import MetricsCollector, StateSnapshot


@dataclass
class PerformanceReport:
    """Performance analysis report"""
    timestamp: float = field(default_factory=time.time)
    period_seconds: float = 3600
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    proxy_performance: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "period_seconds": self.period_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "error_rate": self.error_rate,
            "throughput": self.throughput,
            "proxy_performance": self.proxy_performance,
            "recommendations": self.recommendations,
        }


class PerformanceAnalyzer:
    """
    Analyzes system performance and generates reports.

    Example:
        analyzer = PerformanceAnalyzer(metrics, snapshot)
        report = analyzer.generate_report(timedelta(hours=1))
        print(f"Success rate: {report.success_rate}")
        print(f"Recommendations: {report.recommendations}")
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        state_snapshot: Optional[StateSnapshot] = None,
    ):
        self._metrics = metrics_collector
        self._snapshot = state_snapshot
        self._reports: list[PerformanceReport] = []
        self._max_reports = 100

    def generate_report(
        self,
        period: timedelta = timedelta(hours=1),
    ) -> PerformanceReport:
        """
        Generate a performance report for the specified period.

        Args:
            period: Time period to analyze

        Returns:
            PerformanceReport
        """
        report = PerformanceReport(period_seconds=period.total_seconds())

        if self._metrics:
            self._analyze_metrics(report, period)

        if self._snapshot:
            self._analyze_state(report)

        self._generate_recommendations(report)
        self._store_report(report)

        logger.info(
            f"Generated performance report: "
            f"{report.total_requests} requests, "
            f"{report.success_rate:.1%} success rate"
        )
        return report

    def _analyze_metrics(self, report: PerformanceReport, period: timedelta) -> None:
        """Analyze metrics data"""
        duration_stats = self._metrics.get_aggregated(
            "request.duration", period
        )
        if duration_stats:
            report.avg_response_time = duration_stats.avg

        success_stats = self._metrics.get_aggregated(
            "request.success", period
        )
        if success_stats:
            report.successful_requests = int(success_stats.sum)

        error_stats = self._metrics.get_aggregated(
            "request.error", period
        )
        if error_stats:
            report.failed_requests = int(success_stats.sum if success_stats else 0)

        report.total_requests = report.successful_requests + report.failed_requests
        if report.total_requests > 0:
            report.error_rate = report.failed_requests / report.total_requests
            report.throughput = report.total_requests / period.total_seconds()

        durations = self._metrics.get_latest("request.duration", 100)
        if durations:
            values = sorted([m.value for m in durations])
            n = len(values)
            report.p95_response_time = values[int(n * 0.95)] if n > 0 else 0
            report.p99_response_time = values[int(n * 0.99)] if n > 0 else 0

    def _analyze_state(self, report: PerformanceReport) -> None:
        """Analyze state snapshot data"""
        state = self._snapshot.get_current_state()
        report.successful_requests = max(
            report.successful_requests,
            state.success_count
        )
        report.failed_requests = max(
            report.failed_requests,
            state.error_count
        )
        report.total_requests = report.successful_requests + report.failed_requests

        if state.proxy_stats:
            report.proxy_performance = state.proxy_stats

    def _generate_recommendations(self, report: PerformanceReport) -> None:
        """Generate performance recommendations"""
        recommendations = []

        if report.error_rate > 0.1:
            recommendations.append(
                f"High error rate ({report.error_rate:.1%}). "
                "Consider increasing retry count or checking proxy health."
            )

        if report.avg_response_time > 5.0:
            recommendations.append(
                f"Slow response time ({report.avg_response_time:.1f}s). "
                "Consider using faster proxy regions or reducing parallel load."
            )

        if report.success_rate < 0.8:
            recommendations.append(
                f"Low success rate ({report.success_rate:.1%}). "
                "Review error patterns and adjust retry strategy."
            )

        if report.throughput > 10:
            recommendations.append(
                "High throughput detected. Monitor rate limits to avoid blocks."
            )

        if not recommendations:
            recommendations.append("System performing within normal parameters.")

        report.recommendations = recommendations

    def _store_report(self, report: PerformanceReport) -> None:
        """Store report in history"""
        self._reports.append(report)
        if len(self._reports) > self._max_reports:
            self._reports = self._reports[-self._max_reports:]

    def get_reports(self, limit: int = 10) -> list[PerformanceReport]:
        """Get recent reports"""
        return self._reports[-limit:]

    def compare_reports(
        self,
        report1: PerformanceReport,
        report2: PerformanceReport,
    ) -> dict[str, Any]:
        """
        Compare two reports.

        Returns:
            Dictionary with comparison metrics
        """
        def safe_change(v1: float, v2: float) -> float:
            if v1 == 0:
                return 0 if v2 == 0 else float("inf")
            return (v2 - v1) / v1

        return {
            "success_rate_change": safe_change(
                report1.success_rate, report2.success_rate
            ),
            "response_time_change": safe_change(
                report1.avg_response_time, report2.avg_response_time
            ),
            "throughput_change": safe_change(
                report1.throughput, report2.throughput
            ),
            "error_rate_change": safe_change(
                report1.error_rate, report2.error_rate
            ),
            "improved": (
                report2.success_rate >= report1.success_rate and
                report2.avg_response_time <= report1.avg_response_time
            ),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get overall performance summary"""
        if not self._reports:
            return {"status": "no_data", "reports": 0}

        latest = self._reports[-1]
        avg_success = sum(r.success_rate for r in self._reports) / len(self._reports)
        avg_response = sum(r.avg_response_time for r in self._reports) / len(self._reports)

        trend = "stable"
        if len(self._reports) >= 2:
            recent = self._reports[-1]
            previous = self._reports[-2]
            if recent.success_rate > previous.success_rate + 0.05:
                trend = "improving"
            elif recent.success_rate < previous.success_rate - 0.05:
                trend = "degrading"

        return {
            "status": "healthy" if avg_success > 0.9 else "degraded",
            "reports": len(self._reports),
            "latest_success_rate": latest.success_rate,
            "avg_success_rate": avg_success,
            "avg_response_time": avg_response,
            "trend": trend,
        }
