"""Deterministic BGL Rule-only benchmark utilities.

The caller owns artifact persistence; these functions perform no writes to the
dataset source or to the repository tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from evaluation.features.log_only_features import BglFeatureSample, BglLogOnlyFeatureTransformer
from evaluation.detectors.log_only_rule import LogOnlyRuleDetector, RuleConfig
from evaluation.adapters.bgl_adapter import BglWindow


@dataclass(frozen=True)
class BglSplits:
    train: tuple[BglWindow, ...]
    validation: tuple[BglWindow, ...]
    test: tuple[BglWindow, ...]


def chronological_bgl_split(
    windows: Sequence[BglWindow], train_fraction: float = 0.6, validation_fraction: float = 0.2
) -> BglSplits:
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("Split fractions must be between 0 and 1")
    train_end = int(len(windows) * train_fraction)
    validation_end = train_end + int(len(windows) * validation_fraction)
    splits = BglSplits(tuple(windows[:train_end]), tuple(windows[train_end:validation_end]), tuple(windows[validation_end:]))
    if any(not split for split in (splits.train, splits.validation, splits.test)):
        raise ValueError("Every BGL split must contain at least one sample")
    if any(not any(window.ground_truth for window in split) for split in (splits.validation, splits.test)):
        raise ValueError("Validation and test splits must each include an anomaly")
    return splits


def evaluate_bgl_rule(
    splits: BglSplits, config: RuleConfig
) -> tuple[list[dict[str, object]], dict[str, float | int]]:
    """Fit only on normal train data and return test predictions plus metrics."""

    transformer = BglLogOnlyFeatureTransformer()
    transformer.fit([window for window in splits.train if not window.ground_truth])
    train = transformer.transform(splits.train)
    test = transformer.transform(splits.test)
    detector = LogOnlyRuleDetector(config).fit([sample.features for sample in train if not sample.ground_truth])
    predictions = detector.detect([sample.features for sample in test])
    rows = [
        {"sample_id": sample.sample_id, "ground_truth": sample.ground_truth, "detector": "log_only_rule", "raw_score": prediction.raw_score, "normalized_score": prediction.normalized_score, "prediction": prediction.prediction, "reason": prediction.reason}
        for sample, prediction in zip(test, predictions, strict=True)
    ]
    tp = sum(row["prediction"] == 1 and row["ground_truth"] == 1 for row in rows)
    fp = sum(row["prediction"] == 1 and row["ground_truth"] == 0 for row in rows)
    tn = sum(row["prediction"] == 0 and row["ground_truth"] == 0 for row in rows)
    fn = sum(row["prediction"] == 0 and row["ground_truth"] == 1 for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return rows, {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1}
