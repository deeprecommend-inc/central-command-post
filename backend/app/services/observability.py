from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import statistics


class ActionType(str, Enum):
    ALERT = "alert"
    SLOW = "slow"
    FREEZE = "freeze"
    ABORT = "abort"


@dataclass
class ObservabilityThreshold:
    """16 categories observability thresholds"""

    # 1. IP Structure
    ip_ua_inconsistency_sigma: float = 2.5
    geo_mismatch_pct: float = 5.0
    asn_bias_pct: float = 60.0
    residential_ratio_min: float = 30.0

    # 2. Communication Rhythm
    interval_periodicity_score: float = 75.0
    persistent_conn_ratio_min: float = 40.0
    simul_conn_per_ip_max: int = 4

    # 3. TLS/Protocol
    tls_ja3_mismatch_pct: float = 3.0
    proto_error_rate_pct: float = 2.0

    # 4. User Agent
    ua_nonexistent_pct: float = 1.0
    ua_per_ip_diversity_min: int = 1

    # 5. Fingerprint
    canvas_hash_drift_sigma: float = 2.0
    viewport_ua_mismatch_pct: float = 5.0
    os_browser_consistency_score_min: float = 80.0
    font_plugin_presence_ratio_min: float = 70.0

    # 6. Cookie/Storage
    cookie_reset_rate_pct: float = 5.0
    localstorage_write_fail_pct: float = 1.0

    # 7. JavaScript
    js_exec_error_pct: float = 2.0
    dom_event_entropy_min: float = 2.0

    # 8. Mouse/Pointer
    pointer_curve_ratio_min: float = 30.0
    pre_action_delay_ms_min: int = 150
    micro_jitter_enabled: bool = True

    # 9. Tempo
    human_rxn_window_ms: tuple = (200, 500)
    page_dwell_time_var_pct: float = 35.0

    # 10. Navigation
    referrer_consistency_min: float = 80.0
    nav_back_forward_ratio_min: float = 5.0

    # 11. Headers
    header_order_mismatch_pct: float = 2.0
    origin_referer_mismatch_pct: float = 1.0
    content_encoding_error_pct: float = 1.0

    # 12. Data Transmission
    hidden_field_missing_pct: float = 1.0
    burst_api_ratio_pct: float = 10.0

    # 13. CAPTCHA
    post_captcha_hurry_click_ms: int = 800

    # 14. Consistency
    state_consistency_score_min: float = 85.0
    tz_clock_drift_sec_max: int = 120

    # 15. Distribution
    start_time_spread_minutes: int = 10
    burst_cluster_alert_pct: float = 15.0

    # 16. Auto-Learning
    rule_change_detect_window_min: int = 30
    auto_response_policy: str = "slowdown"  # alert, slowdown, freeze, abort

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ip_structure": {
                "ip_ua_inconsistency_sigma": self.ip_ua_inconsistency_sigma,
                "geo_mismatch_pct": self.geo_mismatch_pct,
                "asn_bias_pct": self.asn_bias_pct,
                "residential_ratio_min": self.residential_ratio_min,
            },
            "rhythm": {
                "interval_periodicity_score": self.interval_periodicity_score,
                "persistent_conn_ratio_min": self.persistent_conn_ratio_min,
                "simul_conn_per_ip_max": self.simul_conn_per_ip_max,
            },
            "tls_protocol": {
                "tls_ja3_mismatch_pct": self.tls_ja3_mismatch_pct,
                "proto_error_rate_pct": self.proto_error_rate_pct,
            },
            "user_agent": {
                "ua_nonexistent_pct": self.ua_nonexistent_pct,
                "ua_per_ip_diversity_min": self.ua_per_ip_diversity_min,
            },
            "fingerprint": {
                "canvas_hash_drift_sigma": self.canvas_hash_drift_sigma,
                "viewport_ua_mismatch_pct": self.viewport_ua_mismatch_pct,
                "os_browser_consistency_score_min": self.os_browser_consistency_score_min,
                "font_plugin_presence_ratio_min": self.font_plugin_presence_ratio_min,
            },
            "storage": {
                "cookie_reset_rate_pct": self.cookie_reset_rate_pct,
                "localstorage_write_fail_pct": self.localstorage_write_fail_pct,
            },
            "javascript": {
                "js_exec_error_pct": self.js_exec_error_pct,
                "dom_event_entropy_min": self.dom_event_entropy_min,
            },
            "pointer": {
                "pointer_curve_ratio_min": self.pointer_curve_ratio_min,
                "pre_action_delay_ms_min": self.pre_action_delay_ms_min,
                "micro_jitter_enabled": self.micro_jitter_enabled,
            },
            "tempo": {
                "human_rxn_window_ms": self.human_rxn_window_ms,
                "page_dwell_time_var_pct": self.page_dwell_time_var_pct,
            },
            "navigation": {
                "referrer_consistency_min": self.referrer_consistency_min,
                "nav_back_forward_ratio_min": self.nav_back_forward_ratio_min,
            },
            "headers": {
                "header_order_mismatch_pct": self.header_order_mismatch_pct,
                "origin_referer_mismatch_pct": self.origin_referer_mismatch_pct,
                "content_encoding_error_pct": self.content_encoding_error_pct,
            },
            "transmission": {
                "hidden_field_missing_pct": self.hidden_field_missing_pct,
                "burst_api_ratio_pct": self.burst_api_ratio_pct,
            },
            "captcha": {
                "post_captcha_hurry_click_ms": self.post_captcha_hurry_click_ms,
            },
            "consistency": {
                "state_consistency_score_min": self.state_consistency_score_min,
                "tz_clock_drift_sec_max": self.tz_clock_drift_sec_max,
            },
            "distribution": {
                "start_time_spread_minutes": self.start_time_spread_minutes,
                "burst_cluster_alert_pct": self.burst_cluster_alert_pct,
            },
            "auto_learning": {
                "rule_change_detect_window_min": self.rule_change_detect_window_min,
                "auto_response_policy": self.auto_response_policy,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservabilityThreshold":
        """Create from dictionary"""
        flat_data = {}
        for category, values in data.items():
            flat_data.update(values)
        return cls(**flat_data)


class ObservabilityMonitor:
    """Monitor observability metrics and enforce thresholds"""

    def __init__(self, thresholds: ObservabilityThreshold):
        self.thresholds = thresholds
        self.violations: List[Dict[str, Any]] = []

    def check_metric(
        self,
        category: str,
        metric_key: str,
        value: float,
        threshold: float,
        comparison: str = "greater"  # "greater" or "less"
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a metric violates threshold
        Returns violation details if violated, None otherwise
        """
        violated = False

        if comparison == "greater":
            violated = value > threshold
        elif comparison == "less":
            violated = value < threshold

        if violated:
            violation = {
                "category": category,
                "metric_key": metric_key,
                "value": value,
                "threshold": threshold,
                "comparison": comparison,
            }
            self.violations.append(violation)
            return violation

        return None

    def determine_action(self, violations: List[Dict[str, Any]]) -> ActionType:
        """
        Determine action based on violations
        """
        if not violations:
            return ActionType.ALERT

        # Count critical violations
        critical_categories = [
            "ua_nonexistent_pct",
            "hidden_field_missing_pct",
        ]

        critical_violations = [
            v for v in violations
            if v["metric_key"] in critical_categories
        ]

        if critical_violations:
            return ActionType.ABORT

        if len(violations) > 5:
            return ActionType.FREEZE

        if len(violations) > 2:
            return ActionType.SLOW

        return ActionType.ALERT

    def evaluate_ip_structure(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """Evaluate IP structure metrics"""
        violations = []

        if "ip_ua_inconsistency_sigma" in metrics:
            v = self.check_metric(
                "ip_structure",
                "ip_ua_inconsistency_sigma",
                metrics["ip_ua_inconsistency_sigma"],
                self.thresholds.ip_ua_inconsistency_sigma,
                "greater"
            )
            if v:
                violations.append(v)

        if "geo_mismatch_pct" in metrics:
            v = self.check_metric(
                "ip_structure",
                "geo_mismatch_pct",
                metrics["geo_mismatch_pct"],
                self.thresholds.geo_mismatch_pct,
                "greater"
            )
            if v:
                violations.append(v)

        return violations

    def evaluate_all(self, metrics: Dict[str, Dict[str, float]]) -> tuple[List[Dict[str, Any]], ActionType]:
        """
        Evaluate all metrics against thresholds
        Returns: (violations, recommended_action)
        """
        all_violations = []

        for category, category_metrics in metrics.items():
            if category == "ip_structure":
                all_violations.extend(self.evaluate_ip_structure(category_metrics))

        action = self.determine_action(all_violations)
        return all_violations, action
