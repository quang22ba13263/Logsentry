"""Create the immutable HDFS final-scale split without scoring held-out test."""

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

from evaluation.adapters.hdfs_adapter import load_hdfs_traces
from evaluation.runners.hdfs_split import source_order_hdfs_split


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create immutable HDFS final-scale development split")
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/hdfs_v1_final.yaml")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
        raise ValueError("run-id may contain only letters, digits, underscores and hyphens")
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset = config["dataset"]
    paths = {
        "event_traces": (ROOT / dataset["event_traces_path"]).resolve(),
        "occurrence_matrix": (ROOT / dataset["occurrence_matrix_path"]).resolve(),
        "anomaly_label": (ROOT / dataset["anomaly_label_path"]).resolve(),
    }
    expected_hashes = {
        "event_traces": dataset["event_traces_sha256"],
        "occurrence_matrix": dataset["occurrence_matrix_sha256"],
        "anomaly_label": dataset["anomaly_label_sha256"],
    }
    actual_hashes = {name: sha256(path) for name, path in paths.items()}
    for name, actual in actual_hashes.items():
        if actual != expected_hashes[name]:
            raise RuntimeError(f"Dataset checksum mismatch for {name}: {actual}")

    output = (ROOT / config["output"]["processed_dir"]).resolve().parent / args.run_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing run artifact: {output}")
    splits = source_order_hdfs_split(
        load_hdfs_traces(paths["event_traces"], paths["occurrence_matrix"], paths["anomaly_label"]),
        config["split"]["train_fraction"],
        config["split"]["validation_fraction"],
    )
    output.mkdir(parents=True)
    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "ground_truth"])
        writer.writeheader()
        for name, samples in (("train", splits.train), ("validation", splits.validation), ("test", splits.test)):
            writer.writerows(
                {"sample_id": sample.sample_id, "split": name, "ground_truth": sample.ground_truth if name != "test" else ""}
                for sample in samples
            )
    summary = {
        "evaluation_phase": "development_split_only",
        "source_order": True,
        "train": {"samples": len(splits.train), "normal": sum(not item.ground_truth for item in splits.train), "anomaly": sum(item.ground_truth for item in splits.train)},
        "validation": {"samples": len(splits.validation), "normal": sum(not item.ground_truth for item in splits.validation), "anomaly": sum(item.ground_truth for item in splits.validation)},
        "test": {"samples": len(splits.test), "labels_exported": False, "scored": False},
    }
    (output / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "run_config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"run_id": args.run_id, "evaluation_phase": "development_split_only", "dataset_sha256": actual_hashes, "config_sha256": sha256(config_path), "split_sha256": sha256(output / "split.csv"), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
