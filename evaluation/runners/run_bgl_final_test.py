"""Run the frozen BGL IF candidate as one post-diagnostic confirmation.

This is deliberately separate from the development runner. It loads the exact
hash-checked IF/scaler/feature-transformer bundle selected on validation and
does not re-fit, tune, or score Rule/DeepLog detectors that failed the BGL
fusion gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.adapters.bgl_adapter import load_bgl_events, make_bgl_event_windows
from evaluation.artifacts.model_bundle import load_isolation_forest_bundle
from evaluation.features.log_only_features import BglLogOnlyFeatureTransformer
from evaluation.runners.bgl_rule_benchmark import _metrics, chronological_bgl_split
from evaluation.runners.final_guard import require_clean_worktree, validate_release


RELEASE_TOKEN = "BGL_POST_DIAGNOSTIC_CONFIRMATION_CONFIRMED"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _expected_projected_split(splits) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, items in (("train", splits.train), ("validation", splits.validation), ("test", splits.test)):
        rows.extend(
            {"sample_id": item.sample_id, "split": name, "ground_truth": str(item.ground_truth) if name != "test" else ""}
            for item in items
        )
    return rows


def _verify_validation_artifact(path: Path, expected_split_sha: str, expected_rows: list[dict[str, object]]) -> None:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    split_path = path / "split.csv"
    if manifest.get("evaluation_phase") != "development_validation_only" or sha256(split_path) != expected_split_sha:
        raise RuntimeError("BGL validation artifact is not the declared frozen projected split")
    rows = list(csv.DictReader(split_path.open(encoding="utf-8", newline="")))
    normalized = [{"sample_id": row["sample_id"], "split": row["split"], "ground_truth": row["ground_truth"]} for row in rows]
    if normalized != expected_rows:
        raise RuntimeError("Current BGL source does not reconstruct the frozen projected split")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/bgl_final_candidate_v1.yaml")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--release-sealed-test", action="store_true")
    parser.add_argument("--approval-token")
    args = parser.parse_args()
    validate_release(
        release_flag=args.release_sealed_test,
        approval_token=args.approval_token,
        required_token=RELEASE_TOKEN,
        benchmark="BGL post-diagnostic confirmation",
    )
    require_clean_worktree(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if config.get("status") != "frozen":
        raise RuntimeError("BGL post-diagnostic config must be frozen")
    if not args.run_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("run-id may contain only letters, digits, underscores and hyphens")
    source = (ROOT / config["dataset"]["structured_log_path"]).resolve()
    if sha256(source) != config["dataset"]["sha256"]:
        raise RuntimeError("BGL dataset checksum mismatch")
    sample, split = config["sample"], config["split"]
    splits = chronological_bgl_split(
        make_bgl_event_windows(load_bgl_events(source), size=int(sample["window_size"]), stride=int(sample["stride"])),
        float(split["train_fraction"]),
        float(split["validation_fraction"]),
    )
    frozen = config["frozen_from_validation_only"]
    _verify_validation_artifact(
        (ROOT / frozen["validation_artifact"]).resolve(),
        frozen["projected_split_sha256"],
        _expected_projected_split(splits),
    )
    bundle_path = (ROOT / frozen["isolation_forest_bundle"]).resolve()
    if not bundle_path.is_relative_to(ROOT):
        raise RuntimeError("Frozen BGL model bundle must be stored inside the repository workspace")
    detector, transformer = load_isolation_forest_bundle(bundle_path)
    candidate = config["candidate"]
    if not isinstance(transformer, BglLogOnlyFeatureTransformer):
        raise RuntimeError("BGL IF bundle lacks its fitted BGL feature transformer")
    if (
        detector.config.n_estimators != int(candidate["n_estimators"])
        or detector.config.max_samples != candidate["max_samples"]
        or detector.config.contamination != candidate["contamination"]
        or detector.config.random_seed != int(candidate["random_seed"])
    ):
        raise RuntimeError("BGL IF bundle does not match the frozen candidate")
    test_features = transformer.transform(splits.test)
    threshold = float(candidate["validation_threshold"])
    scores = detector.score([item.features for item in test_features])
    rows = [
        {
            "sample_id": item.sample_id, "dataset": "BGL_2k", "split": "test", "ground_truth": item.ground_truth,
            "detector": "log_only_isolation_forest", "raw_score": score.raw_score, "normalized_score": score.normalized_score,
            "threshold": threshold, "prediction": int(score.normalized_score >= threshold),
            "reason": "frozen_validation_if_threshold",
        }
        for item, score in zip(test_features, scores, strict=True)
    ]
    output = ROOT / "data/processed/evaluation" / args.run_id
    if output.exists():
        raise FileExistsError("Run ID already exists; refusing to overwrite a post-diagnostic result")
    output.mkdir(parents=True)
    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "ground_truth"])
        writer.writeheader()
        for name, items in (("train", splits.train), ("validation", splits.validation), ("test", splits.test)):
            writer.writerows({"sample_id": item.sample_id, "split": name, "ground_truth": item.ground_truth} for item in items)
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    metrics = {"evaluation_phase": config["test_policy"]["evaluation_phase"], "metric_split": "test", "test_scored": True, "log_only_isolation_forest": _metrics(rows)}
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    manifest = {
        "run_id": args.run_id, "evaluation_phase": metrics["evaluation_phase"], "test_scored": True,
        "test_labels_exported": True, "dataset_sha256": sha256(source), "candidate_config_sha256": sha256(config_path),
        "projected_split_sha256": frozen["projected_split_sha256"], "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "model_bundle": str(bundle_path),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
