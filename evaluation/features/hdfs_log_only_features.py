"""Train-normal-fitted, leakage-safe HDFS trace features for the Rule baseline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log2
from typing import Sequence

from evaluation.adapters.hdfs_adapter import HdfsTrace


@dataclass(frozen=True)
class HdfsRuleFeatureSample:
    sample_id: str
    features: dict[str, float]
    ground_truth: int


class HdfsLogOnlyRuleFeatureTransformer:
    """Learns EventId vocabulary only from normal HDFS training traces."""

    def __init__(self) -> None:
        self.event_vocabulary: frozenset[str] | None = None

    def fit(self, train_normal_traces: Sequence[HdfsTrace]) -> "HdfsLogOnlyRuleFeatureTransformer":
        if not train_normal_traces:
            raise ValueError("HDFS Rule features require normal training traces")
        self.event_vocabulary = frozenset(
            event_id for trace in train_normal_traces for event_id in trace.sequence
        )
        return self

    def transform(self, traces: Sequence[HdfsTrace]) -> list[HdfsRuleFeatureSample]:
        if self.event_vocabulary is None:
            raise RuntimeError("Transformer must be fitted before transform()")
        result: list[HdfsRuleFeatureSample] = []
        for trace in traces:
            events = Counter(trace.sequence)
            total = len(trace.sequence)
            probabilities = [count / total for count in events.values()]
            unseen = sum(event_id not in self.event_vocabulary for event_id in trace.sequence)
            result.append(
                HdfsRuleFeatureSample(
                    sample_id=trace.sample_id,
                    features={
                        "trace_length": float(total),
                        "unique_event_count": float(len(events)),
                        "event_entropy": -sum(p * log2(p) for p in probabilities),
                        "top_event_ratio": max(events.values()) / total,
                        "unseen_event_ratio": unseen / total,
                    },
                    ground_truth=trace.ground_truth,
                )
            )
        return result
