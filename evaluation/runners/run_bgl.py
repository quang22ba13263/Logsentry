"""Run the reproducible BGL v1 log-only Rule baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.adapters.bgl_adapter import load_bgl_events, make_bgl_event_windows
from evaluation.detectors.log_only_isolation_forest import IsolationForestConfig, LogOnlyIsolationForest
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.features.log_only_features import BglLogOnlyFeatureTransformer
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold, chronological_bgl_split, evaluate_bgl_rule


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BGL v1 log-only Rule benchmark")
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/bgl_v1.yaml")
    parser.add_argument("--run-id", required=True, help="Immutable output directory name, e.g. bgl_v1_20260907")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        raise ValueError("run-id may contain only letters, digits, underscores and hyphens")
    source = (ROOT / config["dataset"]["structured_log_path"]).resolve()
    actual_hash = sha256(source)
    if actual_hash != config["dataset"]["sha256"]:
        raise RuntimeError(f"Dataset checksum mismatch: {actual_hash}")

    output = (ROOT / config["output"]["processed_dir"]).resolve().parent / args.run_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing run artifact: {output}")
    output.mkdir(parents=True)
    sample = config["sample"]
    splits = chronological_bgl_split(
        make_bgl_event_windows(load_bgl_events(source), size=sample["window_size"], stride=sample["stride"]),
        config["split"]["train_fraction"], config["split"]["validation_fraction"],
    )
    rule_config = config["detectors"]["log_only_rule"]
    result = evaluate_bgl_rule(splits, RuleConfig(normal_percentile=rule_config["normal_percentile"]))

    transformer = BglLogOnlyFeatureTransformer().fit([item for item in splits.train if not item.ground_truth])
    train_features = transformer.transform(splits.train)
    validation_features = transformer.transform(splits.validation)
    test_features = transformer.transform(splits.test)
    feature_names = tuple(train_features[0].features)
    if_config = config["detectors"]["isolation_forest"]
    detector = LogOnlyIsolationForest(feature_names, IsolationForestConfig(
        n_estimators=if_config["n_estimators"], max_samples=if_config["max_samples"],
        contamination=if_config["contamination"], random_seed=config["random_seed"],
    )).fit([item.features for item in train_features if not item.ground_truth])
    validation_scores = detector.score([item.features for item in validation_features])
    validation_if_rows = [{"sample_id": item.sample_id, "split": "validation", "ground_truth": item.ground_truth, "detector": "log_only_isolation_forest", "raw_score": score.raw_score, "normalized_score": score.normalized_score, "threshold": None, "prediction": 0, "reason": "isolation_forest_log_feature"} for item, score in zip(validation_features, validation_scores, strict=True)]
    if_threshold = _select_validation_threshold(validation_if_rows)
    test_scores = detector.score([item.features for item in test_features])
    test_if_rows = [{"sample_id": item.sample_id, "split": "test", "ground_truth": item.ground_truth, "detector": "log_only_isolation_forest", "raw_score": score.raw_score, "normalized_score": score.normalized_score, "threshold": if_threshold, "prediction": int(score.normalized_score >= if_threshold), "reason": "isolation_forest_log_feature"} for item, score in zip(test_features, test_scores, strict=True)]
    for row in validation_if_rows:
        row["threshold"] = if_threshold
        row["prediction"] = int(float(row["normalized_score"]) >= if_threshold)

    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "ground_truth"])
        writer.writeheader()
        for name, items in (("train", splits.train), ("validation", splits.validation), ("test", splits.test)):
            writer.writerows({"sample_id": item.sample_id, "split": name, "ground_truth": item.ground_truth} for item in items)
    rows = [*result.validation_rows, *result.test_rows, *validation_if_rows, *test_if_rows]
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    metrics = {"log_only_rule": result.test_metrics, "log_only_isolation_forest": _metrics(test_if_rows)}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    with (output / "confusion_matrices.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["detector", "tp", "fp", "tn", "fn"])
        writer.writeheader()
        for detector_name, detector_metrics in metrics.items():
            writer.writerow({"detector": detector_name, **{key: detector_metrics[key] for key in ("tp", "fp", "tn", "fn")}})
    (output / "run_config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"run_id": args.run_id, "dataset_sha256": actual_hash, "config_sha256": sha256(config_path), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(), "selected_validation_threshold": result.selected_threshold, "selected_if_validation_threshold": if_threshold, "split_sha256": sha256(output / "split.csv"), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": metrics, "thresholds": {"log_only_rule": result.selected_threshold, "log_only_isolation_forest": if_threshold}}, indent=2))


if __name__ == "__main__":
    main()
