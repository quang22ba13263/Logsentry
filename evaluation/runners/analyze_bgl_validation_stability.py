"""Quantify BGL candidate uncertainty without opening its held-out test split."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def metrics(rows: list[dict[str, int]]) -> dict[str, float | int]:
    tp = sum(row["prediction"] == 1 and row["ground_truth"] == 1 for row in rows)
    fp = sum(row["prediction"] == 1 and row["ground_truth"] == 0 for row in rows)
    fn = sum(row["prediction"] == 0 and row["ground_truth"] == 1 for row in rows)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def stratified_bootstrap_f1(rows: list[dict[str, int]], *, resamples: int, seed: int) -> tuple[float, float]:
    positives = [row for row in rows if row["ground_truth"] == 1]
    negatives = [row for row in rows if row["ground_truth"] == 0]
    if not positives or not negatives:
        raise ValueError("Bootstrap CI requires both positive and negative validation samples")
    generator = random.Random(seed)
    scores = [
        float(metrics([generator.choice(positives) for _ in positives] + [generator.choice(negatives) for _ in negatives])["f1"])
        for _ in range(resamples)
    ]
    return percentile(scores, 0.025), percentile(scores, 0.975)


def load_if_validation_rows(directory: Path) -> tuple[list[dict[str, int]], dict[str, object]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("evaluation_phase") != "development_validation_only":
        raise ValueError(f"Not a validation-only artifact: {directory}")
    rows = [
        {"sample_id": row["sample_id"], "ground_truth": int(row["ground_truth"]), "prediction": int(row["prediction"])}
        for row in csv.DictReader((directory / "predictions.csv").open(encoding="utf-8", newline=""))
        if row["split"] == "validation" and row["detector"] == "log_only_isolation_forest"
    ]
    if not rows:
        raise ValueError(f"No BGL IF validation predictions in {directory}")
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-report", type=Path, default=ROOT / "evaluation/reports/bgl_validation_uncertainty.md")
    parser.add_argument("--resamples", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260909)
    args = parser.parse_args()
    if len(args.run_dir) < 2 or args.resamples <= 0:
        raise ValueError("Provide at least two runs and a positive number of resamples")
    loaded = [load_if_validation_rows(path.resolve()) for path in args.run_dir]
    reference_ids = [row["sample_id"] for row in loaded[0][0]]
    reference_labels = [row["ground_truth"] for row in loaded[0][0]]
    if any([row["sample_id"] for row in rows] != reference_ids or [row["ground_truth"] for row in rows] != reference_labels for rows, _ in loaded[1:]):
        raise ValueError("Seed runs do not share the same BGL validation rows and labels")
    summaries = []
    for rows, manifest in loaded:
        item_metrics = metrics(rows)
        ci_low, ci_high = stratified_bootstrap_f1(rows, resamples=args.resamples, seed=args.bootstrap_seed)
        summaries.append({"run_id": manifest.get("run_id"), "seed": manifest.get("random_seed"), **item_metrics, "ci_low": ci_low, "ci_high": ci_high})
    f1_values = [float(item["f1"]) for item in summaries]
    mean_f1 = sum(f1_values) / len(f1_values)
    variance = sum((score - mean_f1) ** 2 for score in f1_values) / len(f1_values)
    lines = [
        "# BGL v1 — Validation uncertainty and seed stability",
        "",
        "Status: validation-only. This analysis reads no test rows or test labels.",
        "",
        "The fixed chronological validation split has 20 windows (8 anomaly, 12 normal). "
        "The candidate is Isolation Forest with 200 trees; split/window parameters were not changed.",
        "",
        "| Run | Seed | Precision | Recall | F1 | Stratified bootstrap 95% F1 CI |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item['run_id']}` | {item['seed']} | {float(item['precision']):.4f} | {float(item['recall']):.4f} | {float(item['f1']):.4f} | [{float(item['ci_low']):.4f}, {float(item['ci_high']):.4f}] |"
        for item in summaries
    )
    lines.extend(
        [
            "",
            f"Across seeds: mean validation F1 = **{mean_f1:.4f}**, population std = **{variance ** 0.5:.4f}**.",
            "",
            f"Bootstrap method: {args.resamples:,} stratified non-parametric resamples, bootstrap seed {args.bootstrap_seed}. "
            "The CI describes sampling instability of this small validation set; it is not a final-test confidence interval.",
            "",
            "## Reporting constraint",
            "",
            "BGL's 20-window validation set is too small to compare its apparent F1 directly with HDFS's 57,506-trace validation result. "
            "Report the interval and seed spread together with the point estimate, and do not tune further from this analysis.",
            "",
        ]
    )
    output = args.output_report.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
