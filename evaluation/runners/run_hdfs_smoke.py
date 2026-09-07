"""Run a bounded HDFS development benchmark without opening test by default."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.adapters.hdfs_adapter import load_hdfs_traces
from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.detectors.hdfs_log_only_rule import HdfsLogOnlyRuleDetector
from evaluation.detectors.log_only_isolation_forest import IsolationForestConfig, LogOnlyIsolationForest
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.features.hdfs_log_only_features import HdfsLogOnlyRuleFeatureTransformer
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold


def _rows(samples: list[object], scores: list[float], threshold: float | None = None) -> list[dict[str, object]]:
    return [
        {"ground_truth": sample.ground_truth, "normalized_score": score, "prediction": 0 if threshold is None else int(score >= threshold)}
        for sample, score in zip(samples, scores, strict=True)
    ]


def _fuse(left: list[dict[str, object]], right: list[dict[str, object]], threshold: float | None = None) -> list[dict[str, object]]:
    return [
        {"ground_truth": if_row["ground_truth"], "normalized_score": (float(if_row["normalized_score"]) + float(deep_row["normalized_score"])) / 2, "prediction": 0 if threshold is None else int((float(if_row["normalized_score"]) + float(deep_row["normalized_score"])) / 2 >= threshold)}
        for if_row, deep_row in zip(left, right, strict=True)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded HDFS log-only development benchmark")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--deeplog-train-limit", type=int, default=2000)
    parser.add_argument("--deeplog-epochs", type=int, default=1)
    parser.add_argument("--final-test", action="store_true", help="Score held-out test only after config is frozen.")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        raise ValueError("invalid run-id")
    if args.deeplog_train_limit <= 0 or args.deeplog_epochs <= 0:
        raise ValueError("DeepLog limits must be positive")
    output = ROOT / "data/processed/evaluation" / args.run_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")

    samples = load_hdfs_traces(ROOT / "Dataset/HDFS_v1/preprocessed/Event_traces.csv", ROOT / "Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv", ROOT / "Dataset/HDFS_v1/preprocessed/anomaly_label.csv")
    train = [item for item in samples if not item.ground_truth][:20000]
    validation, test = samples[20000:25000], samples[25000:35000]
    if not any(item.ground_truth for item in validation):
        raise ValueError("smoke validation split lacks anomaly support")
    if args.final_test and not any(item.ground_truth for item in test):
        raise ValueError("smoke test split lacks anomaly support")
    if args.deeplog_train_limit > len(train):
        raise ValueError("deeplog train limit exceeds available normal training traces")

    output.mkdir(parents=True)
    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "ground_truth"])
        writer.writeheader()
        for name, rows in (("train", train), ("validation", validation), ("test", test)):
            writer.writerows({"sample_id": item.sample_id, "split": name, "ground_truth": item.ground_truth if args.final_test or name != "test" else ""} for item in rows)

    detector = LogOnlyIsolationForest(tuple(train[0].features), IsolationForestConfig(n_estimators=100, random_seed=42)).fit([item.features for item in train])
    rule_transformer = HdfsLogOnlyRuleFeatureTransformer().fit(train)
    train_rule_features = rule_transformer.transform(train)
    validation_rule_features = rule_transformer.transform(validation)
    rule_detector = HdfsLogOnlyRuleDetector(RuleConfig()).fit(
        [item.features for item in train_rule_features]
    )
    rule_predictions = rule_detector.detect([item.features for item in validation_rule_features])
    validation_rule_rows = _rows(
        validation,
        [prediction.normalized_score for prediction in rule_predictions],
    )
    rule_threshold = _select_validation_threshold(validation_rule_rows)
    for row in validation_rule_rows:
        row["prediction"] = int(float(row["normalized_score"]) >= rule_threshold)
    validation_if_rows = _rows(validation, [score.normalized_score for score in detector.score([item.features for item in validation])])
    if_threshold = _select_validation_threshold(validation_if_rows)
    for row in validation_if_rows:
        row["prediction"] = int(float(row["normalized_score"]) >= if_threshold)
    deep_train = train[:args.deeplog_train_limit]
    deeplog = LogOnlyDeepLog(DeepLogConfig(sequence_length=10, epochs=args.deeplog_epochs, batch_size=128, random_seed=42)).fit([item.sequence for item in deep_train])
    validation_deep_rows = _rows(validation, deeplog.score([item.sequence for item in validation]))
    deep_threshold = _select_validation_threshold(validation_deep_rows)
    for row in validation_deep_rows:
        row["prediction"] = int(float(row["normalized_score"]) >= deep_threshold)
    fusion_validation_rows = _fuse(validation_if_rows, validation_deep_rows)
    fusion_threshold = _select_validation_threshold(fusion_validation_rows)
    for row in fusion_validation_rows:
        row["prediction"] = int(float(row["normalized_score"]) >= fusion_threshold)

    phase = "final_test" if args.final_test else "development_validation_only"
    metric_rows: dict[str, list[dict[str, object]]] = {"log_only_rule": validation_rule_rows, "isolation_forest": validation_if_rows, "deeplog": validation_deep_rows, "log_only_fusion": fusion_validation_rows}
    if args.final_test:
        test_rule_features = rule_transformer.transform(test)
        test_rule_predictions = rule_detector.detect([item.features for item in test_rule_features])
        test_rule_rows = _rows(test, [prediction.normalized_score for prediction in test_rule_predictions], rule_threshold)
        test_if_rows = _rows(test, [score.normalized_score for score in detector.score([item.features for item in test])], if_threshold)
        test_deep_rows = _rows(test, deeplog.score([item.sequence for item in test]), deep_threshold)
        metric_rows = {"log_only_rule": test_rule_rows, "isolation_forest": test_if_rows, "deeplog": test_deep_rows, "log_only_fusion": _fuse(test_if_rows, test_deep_rows, fusion_threshold)}
    metrics = {"evaluation_phase": phase, "metric_split": "test" if args.final_test else "validation", **{name: _metrics(rows) for name, rows in metric_rows.items()}, "rule_validation_threshold": rule_threshold, "if_validation_threshold": if_threshold, "deeplog_validation_threshold": deep_threshold, "fusion_validation_threshold": fusion_threshold, "fusion_weights": {"isolation_forest": 0.5, "deeplog": 0.5}, "fusion_available_detectors": ["isolation_forest", "deeplog"], "deeplog_train_limit": len(deep_train), "deeplog_epochs": args.deeplog_epochs}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "phase": phase, "validation_anomaly": sum(item.ground_truth for item in validation), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
