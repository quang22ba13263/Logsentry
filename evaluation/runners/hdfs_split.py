"""Deterministic source-order split utilities for HDFS trace evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from evaluation.adapters.hdfs_adapter import HdfsTrace


@dataclass(frozen=True)
class HdfsSplits:
    train: tuple[HdfsTrace, ...]
    validation: tuple[HdfsTrace, ...]
    test: tuple[HdfsTrace, ...]


def source_order_hdfs_split(
    traces: Sequence[HdfsTrace], train_fraction: float = 0.70, validation_fraction: float = 0.10
) -> HdfsSplits:
    """Split in CSV source order; do not randomize or consult test labels."""

    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("Split fractions must be between 0 and 1")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("Train and validation fractions must leave a test split")
    train_end = int(len(traces) * train_fraction)
    validation_end = train_end + int(len(traces) * validation_fraction)
    splits = HdfsSplits(
        tuple(traces[:train_end]), tuple(traces[train_end:validation_end]), tuple(traces[validation_end:])
    )
    if any(not split for split in (splits.train, splits.validation, splits.test)):
        raise ValueError("Every HDFS split must contain at least one trace")
    if not any(trace.ground_truth for trace in splits.validation):
        raise ValueError("Validation split lacks anomaly support")
    return splits
