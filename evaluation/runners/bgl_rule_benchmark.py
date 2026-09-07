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


@dataclass(frozen=True)
class BglRuleBenchmarkResult:
    validation_rows: list[dict[str, object]]
    test_rows: list[dict[str, object]]
    selected_threshold: float
    test_metrics: dict[str, float | int]


@dataclass(frozen=True)
class BglRuleValidationResult:
    """Development-only output; it deliberately contains no test prediction."""

    validation_rows: list[dict[str, object]]
    selected_threshold: float
    validation_metrics: dict[str, float | int]


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


def _metrics(rows: Sequence[dict[str, object]]) -> dict[str, float | int]:
    """Calculate binary metrics from prediction-contract rows."""

    tp = sum(row["prediction"] == 1 and row["ground_truth"] == 1 for row in rows)
    fp = sum(row["prediction"] == 1 and row["ground_truth"] == 0 for row in rows)
    tn = sum(row["prediction"] == 0 and row["ground_truth"] == 0 for row in rows)
    fn = sum(row["prediction"] == 0 and row["ground_truth"] == 1 for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _rows(samples: Sequence[BglFeatureSample], predictions: Sequence[object], split: str) -> list[dict[str, object]]:
    return [
        {"sample_id": sample.sample_id, "split": split, "ground_truth": sample.ground_truth, "detector": "log_only_rule", "raw_score": prediction.raw_score, "normalized_score": prediction.normalized_score, "threshold": None, "prediction": prediction.prediction, "reason": prediction.reason}
        for sample, prediction in zip(samples, predictions, strict=True)
    ]


def _select_validation_threshold(rows: Sequence[dict[str, object]]) -> float:
    """Choose the F1-maximizing threshold exclusively from validation scores."""

    candidates = sorted({0.0, 1.0, *(float(row["normalized_score"]) for row in rows)}, reverse=True)
    ordered = sorted(((float(row["normalized_score"]), int(row["ground_truth"])) for row in rows), reverse=True)
    positives = sum(label for _, label in ordered)
    cursor = tp = fp = 0
    best_threshold, best_f1 = min(candidates), -1.0
    for threshold in candidates:
        while cursor < len(ordered) and ordered[cursor][0] >= threshold:
            if ordered[cursor][1]: tp += 1
            else: fp += 1
            cursor += 1
        fn = positives - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if f1 > best_f1 or (f1 == best_f1 and threshold < best_threshold):
            best_threshold, best_f1 = threshold, f1
    return best_threshold


def evaluate_bgl_rule(splits: BglSplits, config: RuleConfig) -> BglRuleBenchmarkResult:
    """Fit on train-normal, tune on validation, then evaluate test once."""

    transformer = BglLogOnlyFeatureTransformer()
    transformer.fit([window for window in splits.train if not window.ground_truth])
    train = transformer.transform(splits.train)
    validation = transformer.transform(splits.validation)
    test = transformer.transform(splits.test)
    scoring_detector = LogOnlyRuleDetector(config).fit([sample.features for sample in train if not sample.ground_truth])
    validation_rows = _rows(validation, scoring_detector.detect([sample.features for sample in validation]), "validation")
    threshold = _select_validation_threshold(validation_rows)
    selected_config = RuleConfig(normal_percentile=config.normal_percentile, score_threshold=threshold)
    final_detector = LogOnlyRuleDetector(selected_config).fit([sample.features for sample in train if not sample.ground_truth])
    validation_rows = _rows(validation, final_detector.detect([sample.features for sample in validation]), "validation")
    test_rows = _rows(test, final_detector.detect([sample.features for sample in test]), "test")
    for row in [*validation_rows, *test_rows]:
        row["threshold"] = threshold
    return BglRuleBenchmarkResult(validation_rows, test_rows, threshold, _metrics(test_rows))


def evaluate_bgl_rule_validation(splits: BglSplits, config: RuleConfig) -> BglRuleValidationResult:
    """Fit and tune the Rule baseline without accessing the held-out test split."""

    transformer = BglLogOnlyFeatureTransformer()
    transformer.fit([window for window in splits.train if not window.ground_truth])
    train = transformer.transform(splits.train)
    validation = transformer.transform(splits.validation)
    scoring_detector = LogOnlyRuleDetector(config).fit(
        [sample.features for sample in train if not sample.ground_truth]
    )
    validation_rows = _rows(
        validation, scoring_detector.detect([sample.features for sample in validation]), "validation"
    )
    threshold = _select_validation_threshold(validation_rows)
    final_detector = LogOnlyRuleDetector(
        RuleConfig(normal_percentile=config.normal_percentile, score_threshold=threshold)
    ).fit([sample.features for sample in train if not sample.ground_truth])
    validation_rows = _rows(
        validation, final_detector.detect([sample.features for sample in validation]), "validation"
    )
    for row in validation_rows:
        row["threshold"] = threshold
    return BglRuleValidationResult(validation_rows, threshold, _metrics(validation_rows))
