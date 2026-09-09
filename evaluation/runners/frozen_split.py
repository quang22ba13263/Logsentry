"""Read development split assignments while preserving the held-out test seal."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SplitAssignment:
    sample_id: str
    ground_truth: int


@dataclass(frozen=True)
class HdfsDevelopmentAssignments:
    train: tuple[SplitAssignment, ...]
    validation: tuple[SplitAssignment, ...]


def load_hdfs_development_assignments(path: str | Path) -> HdfsDevelopmentAssignments:
    """Return train/validation assignments and reject a split that exposes test labels."""

    buckets: dict[str, list[SplitAssignment]] = {"train": [], "validation": []}
    seen_ids: set[str] = set()
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sample_id, split = row.get("sample_id", ""), row.get("split", "")
            if not sample_id or sample_id in seen_ids:
                raise ValueError("Split contains a missing or duplicate sample_id")
            seen_ids.add(sample_id)
            if split == "test":
                if row.get("ground_truth", ""):
                    raise ValueError("Development split must not expose held-out test labels")
                continue
            if split not in buckets or row.get("ground_truth") not in {"0", "1"}:
                raise ValueError("Split must provide binary labels only for train and validation")
            buckets[split].append(SplitAssignment(sample_id, int(row["ground_truth"])))
    if not buckets["train"] or not buckets["validation"]:
        raise ValueError("Development split requires non-empty train and validation assignments")
    return HdfsDevelopmentAssignments(tuple(buckets["train"]), tuple(buckets["validation"]))


def load_hdfs_sealed_test_ids(path: str | Path) -> tuple[str, ...]:
    """Return sealed test IDs while rejecting any label exposed in the split."""
    ids: list[str] = []
    seen_ids: set[str] = set()
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sample_id, split = row.get("sample_id", ""), row.get("split", "")
            if not sample_id or sample_id in seen_ids:
                raise ValueError("Split contains a missing or duplicate sample_id")
            seen_ids.add(sample_id)
            if split == "test":
                if row.get("ground_truth", ""):
                    raise ValueError("Sealed test labels must be blank in the frozen split artifact")
                ids.append(sample_id)
    if not ids:
        raise ValueError("Frozen split contains no sealed test IDs")
    return tuple(ids)
