"""Score the sealed HDFS test once, after an explicit release acknowledgement.

The checked-in YAML is a deliberately unusable template.  It must be copied,
completed from validation-only results, committed, and marked ``frozen`` before
this runner can access the label-bearing source input.
"""

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
from evaluation.artifacts.model_bundle import save_deeplog_bundle, save_isolation_forest_bundle
from evaluation.detectors.hdfs_log_only_rule import HdfsLogOnlyRuleDetector
from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.detectors.log_only_isolation_forest import IsolationForestConfig, LogOnlyIsolationForest
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.features.hdfs_log_only_features import HdfsLogOnlyRuleFeatureTransformer
from evaluation.runners.bgl_rule_benchmark import _metrics
from evaluation.runners.frozen_split import load_hdfs_development_assignments, load_hdfs_sealed_test_ids


RELEASE_TOKEN = "HDFS_TEST_RELEASE_CONFIRMED"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_release(*, release_flag: bool, approval_token: str | None) -> None:
    if not release_flag or approval_token != RELEASE_TOKEN:
        raise PermissionError(
            "Final HDFS scoring requires --release-sealed-test and "
            f"--approval-token {RELEASE_TOKEN}"
        )


def _score_rows(test, detector: str, scores, threshold: float, reason: str) -> list[dict[str, object]]:
    return [
        {
            "sample_id": trace.sample_id, "dataset": "HDFS_v1", "split": "test", "ground_truth": trace.ground_truth,
            "detector": detector, "raw_score": raw_score, "normalized_score": normalized_score,
            "threshold": threshold, "prediction": int(normalized_score >= threshold), "reason": reason,
        }
        for trace, raw_score, normalized_score in scores
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/hdfs_final_test_template.yaml")
    parser.add_argument("--split-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--release-sealed-test", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()
    validate_release(release_flag=args.release_sealed_test, approval_token=args.approval_token)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        raise ValueError("run-id may contain only letters, digits, underscores and hyphens")
    candidate_path = args.config.resolve()
    candidate = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
    if candidate.get("status") != "frozen":
        raise RuntimeError("Final-test config must be frozen before the sealed test is released")
    deep, fusion = candidate["candidate"]["deeplog"], candidate["candidate"]["fusion"]
    if any(deep.get(name) is None for name in ("epochs", "validation_threshold")) or fusion.get("validation_threshold") is None:
        raise RuntimeError("Frozen candidate is missing the selected DeepLog epoch or validation threshold")
    base_path = (ROOT / candidate["dataset_config"]).resolve()
    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    split_artifact = args.split_artifact.resolve()
    split_path = split_artifact / "split.csv"
    split_manifest = json.loads((split_artifact / "manifest.json").read_text(encoding="utf-8"))
    if split_manifest.get("evaluation_phase") != "development_split_only" or split_manifest.get("split_sha256") != sha256(split_path):
        raise RuntimeError("Frozen split artifact is invalid")
    assignments = load_hdfs_development_assignments(split_path)
    test_ids = load_hdfs_sealed_test_ids(split_path)
    data = base["dataset"]
    traces = load_hdfs_traces(ROOT / data["event_traces_path"], ROOT / data["occurrence_matrix_path"], ROOT / data["anomaly_label_path"])
    by_id = {trace.sample_id: trace for trace in traces}
    train = [by_id[item.sample_id] for item in assignments.train]
    test = [by_id[sample_id] for sample_id in test_ids]
    train_normal = [trace for trace in train if not trace.ground_truth]

    rule = candidate["candidate"]["rule"]
    rule_transformer = HdfsLogOnlyRuleFeatureTransformer().fit(train_normal)
    rule_detector = HdfsLogOnlyRuleDetector(RuleConfig(normal_percentile=float(rule["normal_percentile"]))).fit(
        [item.features for item in rule_transformer.transform(train_normal)]
    )
    rule_predictions = rule_detector.detect([item.features for item in rule_transformer.transform(test)])
    rule_rows = _score_rows(test, "hdfs_log_only_rule", [(p.raw_score, p.normalized_score) for p in rule_predictions], float(rule["validation_threshold"]), "frozen_validation_rule_threshold")

    if_config = candidate["candidate"]["isolation_forest"]
    if_detector = LogOnlyIsolationForest(tuple(train_normal[0].features), IsolationForestConfig(n_estimators=int(if_config["n_estimators"]), max_samples=if_config["max_samples"], random_seed=int(base["random_seed"]))).fit([trace.features for trace in train_normal])
    if_predictions = if_detector.score([trace.features for trace in test])
    if_rows = _score_rows(test, "hdfs_log_only_isolation_forest", [(p.raw_score, p.normalized_score) for p in if_predictions], float(if_config["validation_threshold"]), "frozen_validation_if_threshold")

    deep_detector = LogOnlyDeepLog(DeepLogConfig(sequence_length=int(deep["sequence_length"]), embedding_dim=int(deep["embedding_dim"]), lstm_units=int(deep["lstm_units"]), epochs=int(deep["epochs"]), batch_size=int(deep["batch_size"]), random_seed=int(base["random_seed"]))).fit([trace.sequence for trace in train_normal[:int(deep["train_normal_limit"])]])
    deep_predictions = deep_detector.score([trace.sequence for trace in test], batch_size=int(deep["score_batch_size"]))
    deep_rows = _score_rows(test, "hdfs_log_only_deeplog", [(score, score) for score in deep_predictions], float(deep["validation_threshold"]), "frozen_validation_deeplog_threshold")

    weights = fusion["weights"]
    fusion_rows = []
    for rule_row, if_row, deep_row in zip(rule_rows, if_rows, deep_rows, strict=True):
        score = float(weights["log_only_rule"]) * float(rule_row["normalized_score"]) + float(weights["log_only_isolation_forest"]) * float(if_row["normalized_score"]) + float(weights["log_only_deeplog"]) * float(deep_row["normalized_score"])
        fusion_rows.append({"sample_id": rule_row["sample_id"], "dataset": "HDFS_v1", "split": "test", "ground_truth": rule_row["ground_truth"], "detector": "hdfs_log_only_fusion", "raw_score": score, "normalized_score": score, "threshold": float(fusion["validation_threshold"]), "prediction": int(score >= float(fusion["validation_threshold"])), "reason": "frozen_validation_fusion_weights"})

    output, models = ROOT / "data/processed/evaluation" / args.run_id, ROOT / "data/models/evaluation" / args.run_id
    if output.exists() or models.exists():
        raise FileExistsError("Final-test run ID already exists; refusing to overwrite a sealed result")
    output.mkdir(parents=True); models.mkdir(parents=True)
    if_bundle = save_isolation_forest_bundle(if_detector, models / "isolation_forest")
    deep_bundle = save_deeplog_bundle(deep_detector, models / "deeplog")
    all_rows = [*rule_rows, *if_rows, *deep_rows, *fusion_rows]
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0])); writer.writeheader(); writer.writerows(all_rows)
    metrics = {"evaluation_phase": "final_test", "metric_split": "test", "test_scored": True, "hdfs_log_only_rule": _metrics(rule_rows), "hdfs_log_only_isolation_forest": _metrics(if_rows), "hdfs_log_only_deeplog": _metrics(deep_rows), "hdfs_log_only_fusion": _metrics(fusion_rows)}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest = {"run_id": args.run_id, "evaluation_phase": "final_test", "test_scored": True, "test_labels_exported": True, "sealed_test_ids": len(test_ids), "upstream_split_sha256": split_manifest["split_sha256"], "candidate_config_sha256": sha256(candidate_path), "dataset_config_sha256": sha256(base_path), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "model_bundles": {"isolation_forest": str(if_bundle), "deeplog": str(deep_bundle)}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
