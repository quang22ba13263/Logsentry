"""Run the reproducible BGL v1 log-only Rule baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.adapters.bgl_adapter import load_bgl_events, make_bgl_event_windows
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.runners.bgl_rule_benchmark import chronological_bgl_split, evaluate_bgl_rule


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BGL v1 log-only Rule benchmark")
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/bgl_v1.yaml")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = (ROOT / config["dataset"]["structured_log_path"]).resolve()
    actual_hash = sha256(source)
    if actual_hash != config["dataset"]["sha256"]:
        raise RuntimeError(f"Dataset checksum mismatch: {actual_hash}")

    output = (ROOT / config["output"]["processed_dir"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    sample = config["sample"]
    splits = chronological_bgl_split(
        make_bgl_event_windows(load_bgl_events(source), size=sample["window_size"], stride=sample["stride"]),
        config["split"]["train_fraction"], config["split"]["validation_fraction"],
    )
    rule_config = config["detectors"]["log_only_rule"]
    result = evaluate_bgl_rule(splits, RuleConfig(normal_percentile=rule_config["normal_percentile"]))

    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "split", "ground_truth"])
        writer.writeheader()
        for name, items in (("train", splits.train), ("validation", splits.validation), ("test", splits.test)):
            writer.writerows({"sample_id": item.sample_id, "split": name, "ground_truth": item.ground_truth} for item in items)
    rows = [*result.validation_rows, *result.test_rows]
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (output / "metrics.json").write_text(json.dumps(result.test_metrics, indent=2), encoding="utf-8")
    (output / "run_config.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"dataset_sha256": actual_hash, "config_sha256": sha256(config_path), "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(), "selected_validation_threshold": result.selected_threshold, "split_sha256": sha256(output / "split.csv"), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": result.test_metrics, "threshold": result.selected_threshold}, indent=2))


if __name__ == "__main__":
    main()
