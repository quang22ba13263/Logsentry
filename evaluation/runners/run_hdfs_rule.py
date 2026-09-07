"""Evaluate the HDFS Rule baseline on a frozen split without scoring test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.adapters.hdfs_adapter import load_hdfs_traces
from evaluation.detectors.hdfs_log_only_rule import HdfsLogOnlyRuleDetector
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.features.hdfs_log_only_features import HdfsLogOnlyRuleFeatureTransformer
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold
from evaluation.runners.frozen_split import load_hdfs_development_assignments


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HDFS Rule development evaluation on a frozen split")
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/hdfs_v1_final.yaml")
    parser.add_argument("--split-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--normal-percentile", type=float)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        raise ValueError("run-id may contain only letters, digits, underscores and hyphens")
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    split_artifact = args.split_artifact.resolve()
    split_path, split_manifest_path = split_artifact / "split.csv", split_artifact / "manifest.json"
    upstream_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    if upstream_manifest.get("evaluation_phase") != "development_split_only":
        raise ValueError("Rule development requires a sealed development split artifact")
    if upstream_manifest.get("split_sha256") != sha256(split_path):
        raise RuntimeError("Frozen split hash does not match its manifest")
    dataset = config["dataset"]
    expected_hashes = {
        "event_traces": dataset["event_traces_sha256"],
        "occurrence_matrix": dataset["occurrence_matrix_sha256"],
        "anomaly_label": dataset["anomaly_label_sha256"],
    }
    if upstream_manifest.get("dataset_sha256") != expected_hashes:
        raise RuntimeError("Config dataset checksums do not match the frozen split manifest")
    assignments = load_hdfs_development_assignments(split_path)

    traces = load_hdfs_traces(
        ROOT / dataset["event_traces_path"],
        ROOT / dataset["occurrence_matrix_path"],
        ROOT / dataset["anomaly_label_path"],
    )
    trace_by_id = {trace.sample_id: trace for trace in traces}
    train = [trace_by_id[item.sample_id] for item in assignments.train]
    validation = [trace_by_id[item.sample_id] for item in assignments.validation]
    for assignment, trace in zip((*assignments.train, *assignments.validation), (*train, *validation), strict=True):
        if assignment.ground_truth != trace.ground_truth:
            raise RuntimeError("Train or validation label differs from frozen split")
    train_normal = [trace for trace in train if not trace.ground_truth]
    rule_config = config["detectors"]["log_only_rule"]
    normal_percentile = args.normal_percentile or float(rule_config["normal_percentile"])
    transformer = HdfsLogOnlyRuleFeatureTransformer().fit(train_normal)
    train_features = transformer.transform(train_normal)
    validation_features = transformer.transform(validation)
    detector = HdfsLogOnlyRuleDetector(
        RuleConfig(normal_percentile=normal_percentile)
    ).fit([item.features for item in train_features])
    predictions = detector.detect([item.features for item in validation_features])
    rows = [
        {"sample_id": sample.sample_id, "dataset": "HDFS_v1", "split": "validation", "ground_truth": sample.ground_truth, "detector": "hdfs_log_only_rule", "raw_score": prediction.raw_score, "normalized_score": prediction.normalized_score, "threshold": None, "prediction": 0, "reason": prediction.reason, "model_version": "hdfs-log-only-rule-v1", "config_version": config["version"]}
        for sample, prediction in zip(validation_features, predictions, strict=True)
    ]
    threshold = _select_validation_threshold(rows)
    for row in rows:
        row["threshold"] = threshold
        row["prediction"] = int(float(row["normalized_score"]) >= threshold)
    output = (ROOT / config["output"]["processed_dir"]).resolve().parent / args.run_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing run artifact: {output}")
    output.mkdir(parents=True)
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metrics = {"evaluation_phase": "development_validation_only", "metric_split": "validation", "hdfs_log_only_rule": _metrics(rows), "selected_validation_threshold": threshold, "normal_percentile": normal_percentile, "train_normal_samples": len(train_normal), "validation_samples": len(validation)}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (output / "run_config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"run_id": args.run_id, "evaluation_phase": "development_validation_only", "upstream_split_artifact": str(split_artifact), "upstream_split_sha256": upstream_manifest["split_sha256"], "config_sha256": sha256(config_path), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "test_scored": False, "test_labels_exported": False}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
