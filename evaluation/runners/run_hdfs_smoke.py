"""Create an immutable chronological HDFS smoke split."""
from __future__ import annotations
import argparse, csv, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from evaluation.adapters.hdfs_adapter import load_hdfs_traces
from evaluation.detectors.log_only_isolation_forest import IsolationForestConfig, LogOnlyIsolationForest
from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--deeplog-train-limit", type=int, default=2000)
    parser.add_argument("--deeplog-epochs", type=int, default=1)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id): raise ValueError("invalid run-id")
    output = ROOT / "data/processed/evaluation" / args.run_id
    if output.exists(): raise FileExistsError(f"Refusing to overwrite: {output}")
    samples = load_hdfs_traces(ROOT / "Dataset/HDFS_v1/preprocessed/Event_traces.csv", ROOT / "Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv", ROOT / "Dataset/HDFS_v1/preprocessed/anomaly_label.csv")
    train = [item for item in samples if not item.ground_truth][:20000]
    validation, test = samples[20000:25000], samples[25000:35000]
    if not any(x.ground_truth for x in validation) or not any(x.ground_truth for x in test): raise ValueError("smoke split lacks anomaly support")
    output.mkdir(parents=True)
    with (output / "split.csv").open("w", newline="", encoding="utf-8") as handle:
        writer=csv.DictWriter(handle, fieldnames=["sample_id","split","ground_truth"]); writer.writeheader()
        for name, rows in (("train",train),("validation",validation),("test",test)):
            writer.writerows({"sample_id":x.sample_id,"split":name,"ground_truth":x.ground_truth} for x in rows)
    features = tuple(train[0].features)
    detector = LogOnlyIsolationForest(features, IsolationForestConfig(n_estimators=100, random_seed=42)).fit([x.features for x in train])
    validation_scores = detector.score([x.features for x in validation])
    validation_rows=[{"ground_truth":x.ground_truth,"normalized_score":s.normalized_score,"prediction":0} for x,s in zip(validation,validation_scores)]
    threshold=_select_validation_threshold(validation_rows)
    test_scores=detector.score([x.features for x in test])
    test_rows=[{"ground_truth":x.ground_truth,"normalized_score":s.normalized_score,"prediction":int(s.normalized_score>=threshold)} for x,s in zip(test,test_scores)]
    deep_train = train[:args.deeplog_train_limit]
    deeplog=LogOnlyDeepLog(DeepLogConfig(sequence_length=10,epochs=args.deeplog_epochs,batch_size=128,random_seed=42)).fit([x.sequence for x in deep_train])
    validation_deep=deeplog.score([x.sequence for x in validation])
    deep_validation_rows=[{"ground_truth":x.ground_truth,"normalized_score":s,"prediction":0} for x,s in zip(validation,validation_deep)]
    deep_threshold=_select_validation_threshold(deep_validation_rows)
    test_deep=deeplog.score([x.sequence for x in test])
    deep_test_rows=[{"ground_truth":x.ground_truth,"normalized_score":s,"prediction":int(s>=deep_threshold)} for x,s in zip(test,test_deep)]
    import json
    metrics={"isolation_forest":_metrics(test_rows),"deeplog":_metrics(deep_test_rows),"if_validation_threshold":threshold,"deeplog_validation_threshold":deep_threshold,"deeplog_train_limit":len(deep_train),"deeplog_epochs":args.deeplog_epochs}
    (output / "metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print({"output":str(output),"train":len(train),"validation_anomaly":sum(x.ground_truth for x in validation),"test_anomaly":sum(x.ground_truth for x in test),"metrics":metrics})
if __name__ == "__main__": main()
