"""Select a HDFS log-only fusion configuration only from validation artifacts."""
from __future__ import annotations
import argparse, csv, itertools, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import yaml
from evaluation.runners.bgl_rule_benchmark import _metrics, _select_validation_threshold

def load_rows(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("test_scored") is not False or manifest.get("test_labels_exported") is not False:
        raise ValueError(f"Artifact is not validation-only: {path}")
    rows = list(csv.DictReader((path / "predictions.csv").open(encoding="utf-8", newline="")))
    if not rows or any(row["split"] != "validation" for row in rows):
        raise ValueError(f"Artifact must contain validation rows only: {path}")
    return {row["sample_id"]: row for row in rows}, manifest

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "evaluation/config/hdfs_fusion_tuning_v1.yaml")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(); config_path=args.config.resolve(); config=yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = {name: ROOT / "data/processed/evaluation" / run_id for name, run_id in config["input_artifacts"].items()}
    loaded = {name: load_rows(path) for name, path in source.items()}; row_maps={name:value[0] for name,value in loaded.items()}
    sample_ids = set(next(iter(row_maps.values())))
    if any(set(rows) != sample_ids for rows in row_maps.values()): raise ValueError("Fusion inputs do not share identical validation IDs")
    if len({manifest.get("upstream_split_sha256") for _,manifest in loaded.values()}) != 1: raise ValueError("Fusion inputs use different frozen splits")
    weights_grid=config["weight_grid"]; minimum=int(config["minimum_active_detectors"]); best=None
    for candidate in itertools.product(weights_grid, repeat=len(row_maps)):
        if sum(weight > 0 for weight in candidate) < minimum: continue
        total=sum(candidate); weights=dict(zip(row_maps, (weight/total for weight in candidate), strict=True))
        rows=[]
        for sample_id in sorted(sample_ids):
            values=[row_maps[name][sample_id] for name in row_maps]
            if len({row["ground_truth"] for row in values}) != 1: raise ValueError("Fusion inputs disagree on labels")
            score=sum(weights[name]*float(row_maps[name][sample_id]["normalized_score"]) for name in row_maps)
            rows.append({"sample_id":sample_id,"split":"validation","ground_truth":int(values[0]["ground_truth"]),"normalized_score":score,"prediction":0})
        threshold=_select_validation_threshold(rows)
        for row in rows: row["prediction"]=int(float(row["normalized_score"])>=threshold)
        metrics=_metrics(rows); rank=(metrics["f1"],metrics["precision"],metrics["recall"])
        if best is None or rank > best[0]: best=(rank,weights,threshold,metrics,rows)
    assert best is not None
    _,weights,threshold,metrics,rows=best; output=ROOT/"data/processed/evaluation"/args.run_id
    if output.exists(): raise FileExistsError(f"Refusing to overwrite: {output}")
    output.mkdir(parents=True)
    for row in rows:
        row.update({"dataset":"HDFS_v1","detector":"hdfs_log_only_fusion","threshold":threshold,"reason":"validation_weighted_normalized_scores","model_version":"hdfs-fusion-tuning-v1","config_version":config["version"]})
    with (output/"predictions.csv").open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    result={"evaluation_phase":"development_validation_only","metric_split":"validation","hdfs_log_only_fusion":metrics,"selected_validation_threshold":threshold,"weights":weights,"active_detectors":[name for name,weight in weights.items() if weight>0],"test_scored":False,"test_labels_exported":False}
    (output/"metrics.json").write_text(json.dumps(result,indent=2),encoding="utf-8"); (output/"run_config.yaml").write_text(config_path.read_text(encoding="utf-8"),encoding="utf-8")
    (output/"manifest.json").write_text(json.dumps({"evaluation_phase":"development_validation_only","upstream_split_sha256":next(iter({manifest.get("upstream_split_sha256") for _,manifest in loaded.values()})),"test_scored":False,"test_labels_exported":False},indent=2),encoding="utf-8")
    print(json.dumps({"output":str(output),"metrics":result},indent=2))
if __name__ == "__main__": main()
