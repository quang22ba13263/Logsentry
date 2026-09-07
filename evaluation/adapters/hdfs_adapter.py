"""Leakage-safe adapter for HDFS preprocessed trace inputs."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

EVENT_COLUMN = re.compile(r"^E\d+$")

@dataclass(frozen=True)
class HdfsTrace:
    sample_id: str
    sequence: tuple[str, ...]
    features: dict[str, float]
    ground_truth: int

def parse_event_sequence(value: str) -> tuple[str, ...]:
    text = value.strip()
    if not text.startswith("[") or not text.endswith("]"):
        raise ValueError("HDFS Features must be a bracketed EventId sequence")
    tokens = tuple(token.strip() for token in text[1:-1].split(",") if token.strip())
    if not tokens or any(not re.fullmatch(r"E\d+", token) for token in tokens):
        raise ValueError("HDFS sequence contains invalid EventId")
    return tokens

def load_hdfs_traces(event_traces_path: str | Path, occurrence_path: str | Path, label_path: str | Path) -> list[HdfsTrace]:
    """Join all three HDFS inputs; fail if any BlockId set differs."""
    def read(path: str | Path) -> dict[str, dict[str, str]]:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            return {row["BlockId"]: row for row in csv.DictReader(handle)}
    traces, occurrences, labels = read(event_traces_path), read(occurrence_path), read(label_path)
    if set(traces) != set(occurrences) or set(traces) != set(labels):
        raise ValueError("HDFS BlockId mismatch across trace, occurrence, and label files")
    event_columns = [name for name in next(iter(occurrences.values())) if EVENT_COLUMN.fullmatch(name)]
    if not event_columns:
        raise ValueError("HDFS occurrence matrix has no E<n> feature columns")
    result = []
    for block_id, trace in traces.items():
        label = labels[block_id]["Label"]
        if label not in {"Normal", "Anomaly"}:
            raise ValueError(f"Invalid HDFS label: {label}")
        result.append(HdfsTrace(block_id, parse_event_sequence(trace["Features"]), {name: float(occurrences[block_id][name]) for name in event_columns}, int(label == "Anomaly")))
    return result
