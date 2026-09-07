"""Run bounded, streaming HDFS DeepLog development evaluation; never score test."""
from __future__ import annotations
import argparse, csv, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from evaluation.adapters.hdfs_adapter import load_hdfs_traces
from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold
from evaluation.runners.frozen_split import load_hdfs_development_assignments

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description="Run streaming HDFS DeepLog development evaluation")
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/hdfs_v1_final.yaml")
    parser.add_argument("--split-artifact", type=Path, required=True); parser.add_argument("--run-id", required=True)
    parser.add_argument("--train-normal-limit", type=int)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id): raise ValueError("invalid run-id")
    config_path = args.config.resolve(); config = yaml.safe_load(config_path.read_text(encoding="utf-8")); dataset = config["dataset"]
    split_artifact = args.split_artifact.resolve(); split_path = split_artifact / "split.csv"; upstream = json.loads((split_artifact / "manifest.json").read_text(encoding="utf-8"))
    expected = {"event_traces":dataset["event_traces_sha256"],"occurrence_matrix":dataset["occurrence_matrix_sha256"],"anomaly_label":dataset["anomaly_label_sha256"]}
    if upstream.get("evaluation_phase") != "development_split_only" or upstream.get("split_sha256") != sha256(split_path) or upstream.get("dataset_sha256") != expected: raise RuntimeError("Frozen split artifact/config mismatch")
    assignments = load_hdfs_development_assignments(split_path)
    traces = load_hdfs_traces(ROOT / dataset["event_traces_path"], ROOT / dataset["occurrence_matrix_path"], ROOT / dataset["anomaly_label_path"]); by_id = {trace.sample_id: trace for trace in traces}
    train, validation = [by_id[item.sample_id] for item in assignments.train], [by_id[item.sample_id] for item in assignments.validation]
    for assignment, trace in zip((*assignments.train, *assignments.validation), (*train, *validation), strict=True):
        if assignment.ground_truth != trace.ground_truth: raise RuntimeError("Frozen split label mismatch")
    settings = config["detectors"]["deeplog"]; limit = args.train_normal_limit or int(settings["train_normal_limit"]); train_normal = [trace for trace in train if not trace.ground_truth][:limit]
    if len(train_normal) != limit: raise ValueError("train normal limit exceeds frozen split")
    model = LogOnlyDeepLog(DeepLogConfig(sequence_length=int(settings["sequence_length"]), embedding_dim=int(settings["embedding_dim"]), lstm_units=int(settings["lstm_units"]), epochs=int(settings["epochs"]), batch_size=int(settings["batch_size"]), random_seed=int(config["random_seed"]))).fit([trace.sequence for trace in train_normal])
    scores = model.score([trace.sequence for trace in validation], batch_size=int(settings["score_batch_size"]))
    rows = [{"sample_id":trace.sample_id,"dataset":"HDFS_v1","split":"validation","ground_truth":trace.ground_truth,"detector":"hdfs_log_only_deeplog","raw_score":score,"normalized_score":score,"threshold":None,"prediction":0,"reason":"lstm_next_event_surprisal","model_version":"hdfs-log-only-deeplog-v1","config_version":config["version"]} for trace, score in zip(validation,scores,strict=True)]
    threshold = _select_validation_threshold(rows)
    for row in rows: row["threshold"] = threshold; row["prediction"] = int(float(row["normalized_score"]) >= threshold)
    output = (ROOT / config["output"]["processed_dir"]).resolve().parent / args.run_id
    if output.exists(): raise FileExistsError(f"Refusing to overwrite existing run artifact: {output}")
    output.mkdir(parents=True)
    with (output / "predictions.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    metrics={"evaluation_phase":"development_validation_only","metric_split":"validation","hdfs_log_only_deeplog":_metrics(rows),"selected_validation_threshold":threshold,"train_normal_samples":len(train_normal),"validation_samples":len(validation)}
    (output / "metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8"); (output / "run_config.yaml").write_text(config_path.read_text(encoding="utf-8"),encoding="utf-8")
    manifest={"run_id":args.run_id,"evaluation_phase":"development_validation_only","upstream_split_sha256":upstream["split_sha256"],"config_sha256":sha256(config_path),"git_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"timestamp_utc":datetime.now(timezone.utc).isoformat(),"test_scored":False,"test_labels_exported":False}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8"); print(json.dumps({"output":str(output),"metrics":metrics},indent=2))
if __name__ == "__main__": main()
