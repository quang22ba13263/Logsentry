"""Explainable HDFS trace Rule baseline with no label, type, or BlockId input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from evaluation.detectors.log_only_rule import FORBIDDEN_INPUT_TOKENS, RuleConfig, RulePrediction, _percentile


REQUIRED_HDFS_RULE_FEATURES = (
    "trace_length",
    "event_entropy",
    "top_event_ratio",
    "unseen_event_ratio",
)


class HdfsLogOnlyRuleDetector:
    """Fit transparent trace-shape thresholds only on normal training traces."""

    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self.thresholds: dict[str, float] | None = None

    @staticmethod
    def _validate_row(row: Mapping[str, object]) -> None:
        forbidden = [
            name for name in row if any(token in name.casefold() for token in FORBIDDEN_INPUT_TOKENS)
        ]
        if forbidden:
            raise ValueError(f"Forbidden leakage-prone feature columns: {forbidden}")
        missing = [name for name in REQUIRED_HDFS_RULE_FEATURES if name not in row]
        if missing:
            raise ValueError(f"Missing required HDFS log-only features: {missing}")
        for name in REQUIRED_HDFS_RULE_FEATURES:
            try:
                float(row[name])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Feature {name!r} must be numeric") from exc

    @classmethod
    def _validate_rows(cls, rows: Sequence[Mapping[str, object]]) -> None:
        if not rows:
            raise ValueError("At least one normal training sample is required")
        for row in rows:
            cls._validate_row(row)

    def fit(self, train_normal_features: Sequence[Mapping[str, object]]) -> "HdfsLogOnlyRuleDetector":
        self._validate_rows(train_normal_features)
        lower = 100.0 - self.config.normal_percentile
        values = {
            name: [float(row[name]) for row in train_normal_features]
            for name in REQUIRED_HDFS_RULE_FEATURES
        }
        self.thresholds = {
            "trace_length_upper": _percentile(values["trace_length"], self.config.normal_percentile),
            "event_entropy_lower": _percentile(values["event_entropy"], lower),
            "event_entropy_upper": _percentile(values["event_entropy"], self.config.normal_percentile),
            "top_event_ratio_upper": _percentile(values["top_event_ratio"], self.config.normal_percentile),
            "unseen_event_ratio_upper": _percentile(values["unseen_event_ratio"], self.config.normal_percentile),
        }
        return self

    def detect(self, features: Sequence[Mapping[str, object]]) -> list[RulePrediction]:
        if self.thresholds is None:
            raise RuntimeError("HdfsLogOnlyRuleDetector must be fitted before detect()")
        self._validate_rows(features)
        predictions: list[RulePrediction] = []
        for row in features:
            numeric = {name: float(row[name]) for name in REQUIRED_HDFS_RULE_FEATURES}
            triggered: list[str] = []
            if numeric["trace_length"] > self.thresholds["trace_length_upper"]:
                triggered.append("trace_length_above_train_normal_percentile")
            if numeric["event_entropy"] < self.thresholds["event_entropy_lower"]:
                triggered.append("event_entropy_below_train_normal_range")
            if numeric["event_entropy"] > self.thresholds["event_entropy_upper"]:
                triggered.append("event_entropy_above_train_normal_range")
            if numeric["top_event_ratio"] > self.thresholds["top_event_ratio_upper"]:
                triggered.append("top_event_ratio_above_train_normal_percentile")
            if numeric["unseen_event_ratio"] > self.thresholds["unseen_event_ratio_upper"]:
                triggered.append("unseen_event_ratio_above_train_normal_percentile")
            score = len(triggered) / 5.0
            predictions.append(
                RulePrediction(
                    raw_score=len(triggered),
                    normalized_score=score,
                    prediction=int(score >= self.config.score_threshold),
                    reason="; ".join(triggered) if triggered else "no_hdfs_log_only_rule_triggered",
                )
            )
        return predictions
