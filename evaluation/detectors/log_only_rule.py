"""Explainable rule baseline for log-only evaluation.

This detector is intentionally separate from ``src.detectors.rule_based``:
the production detector consumes infrastructure metrics, while this baseline
must operate solely on benchmark log features.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Mapping, Sequence


REQUIRED_LOG_ONLY_FEATURES = (
    "total_logs",
    "template_entropy",
    "top_template_ratio",
    "unseen_template_ratio",
)
FORBIDDEN_INPUT_TOKENS = ("label", "ground_truth", "type", "blockid", "block_id")


@dataclass(frozen=True)
class RuleConfig:
    """Configuration supplied by a versioned benchmark YAML file."""

    normal_percentile: float = 99.0
    score_threshold: float = 0.25

    def __post_init__(self) -> None:
        if not 0.0 < self.normal_percentile < 100.0:
            raise ValueError("normal_percentile must be between 0 and 100")
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("score_threshold must be between 0 and 1")


@dataclass(frozen=True)
class RulePrediction:
    """Normalized score and transparent explanations for one sample."""

    raw_score: int
    normalized_score: float
    prediction: int
    reason: str


def _percentile(values: Sequence[float], percentile: float) -> float:
    """Deterministic nearest-rank percentile without a numerical dependency."""

    if not values:
        raise ValueError("Cannot calculate thresholds from an empty training set")
    ordered = sorted(values)
    index = max(0, ceil(percentile / 100.0 * len(ordered)) - 1)
    return ordered[index]


class LogOnlyRuleDetector:
    """Rule baseline fitted from normal training data only.

    The detector uses five transparent conditions: unusually high log volume,
    unusually low/high template entropy, a dominant template ratio, and any
    unseen-template ratio above the normal-training percentile.  Its score is
    the fraction of triggered conditions, already normalized to ``[0, 1]``.
    """

    def __init__(self, config: RuleConfig | None = None) -> None:
        self.config = config or RuleConfig()
        self.thresholds: dict[str, float] | None = None

    @staticmethod
    def _validate_row(row: Mapping[str, object]) -> None:
        forbidden = [
            name
            for name in row
            if any(token in name.casefold() for token in FORBIDDEN_INPUT_TOKENS)
        ]
        if forbidden:
            raise ValueError(f"Forbidden leakage-prone feature columns: {forbidden}")

        missing = [name for name in REQUIRED_LOG_ONLY_FEATURES if name not in row]
        if missing:
            raise ValueError(f"Missing required log-only features: {missing}")

        for name in REQUIRED_LOG_ONLY_FEATURES:
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

    def fit(self, train_normal_features: Sequence[Mapping[str, object]]) -> "LogOnlyRuleDetector":
        """Fit all reference thresholds exclusively on normal train samples."""

        self._validate_rows(train_normal_features)
        lower_percentile = 100.0 - self.config.normal_percentile
        values = {
            name: [float(row[name]) for row in train_normal_features]
            for name in REQUIRED_LOG_ONLY_FEATURES
        }
        self.thresholds = {
            "total_logs_upper": _percentile(values["total_logs"], self.config.normal_percentile),
            "template_entropy_lower": _percentile(values["template_entropy"], lower_percentile),
            "template_entropy_upper": _percentile(values["template_entropy"], self.config.normal_percentile),
            "top_template_ratio_upper": _percentile(
                values["top_template_ratio"], self.config.normal_percentile
            ),
            "unseen_template_ratio_upper": _percentile(
                values["unseen_template_ratio"], self.config.normal_percentile
            ),
        }
        return self

    def detect(self, features: Sequence[Mapping[str, object]]) -> list[RulePrediction]:
        """Predict anomalies from valid log-only features and report reasons."""

        if self.thresholds is None:
            raise RuntimeError("LogOnlyRuleDetector must be fitted before detect()")
        self._validate_rows(features)

        predictions: list[RulePrediction] = []
        for row in features:
            numeric = {name: float(row[name]) for name in REQUIRED_LOG_ONLY_FEATURES}
            triggered: list[str] = []
            if numeric["total_logs"] > self.thresholds["total_logs_upper"]:
                triggered.append("total_logs_above_train_normal_percentile")
            if numeric["template_entropy"] < self.thresholds["template_entropy_lower"]:
                triggered.append("template_entropy_below_train_normal_range")
            if numeric["template_entropy"] > self.thresholds["template_entropy_upper"]:
                triggered.append("template_entropy_above_train_normal_range")
            if numeric["top_template_ratio"] > self.thresholds["top_template_ratio_upper"]:
                triggered.append("top_template_ratio_above_train_normal_percentile")
            if numeric["unseen_template_ratio"] > self.thresholds["unseen_template_ratio_upper"]:
                triggered.append("unseen_template_ratio_above_train_normal_percentile")

            score = len(triggered) / 5.0
            predictions.append(
                RulePrediction(
                    raw_score=len(triggered),
                    normalized_score=score,
                    prediction=int(score >= self.config.score_threshold),
                    reason="; ".join(triggered) if triggered else "no_log_only_rule_triggered",
                )
            )
        return predictions
