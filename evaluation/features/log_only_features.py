"""Train-normal-fitted log-only features for BGL event-count windows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log2
from typing import Sequence

from evaluation.adapters.bgl_adapter import BglWindow


@dataclass(frozen=True)
class BglFeatureSample:
    sample_id: str
    features: dict[str, float]
    ground_truth: int


class BglLogOnlyFeatureTransformer:
    """Learns template vocabulary solely from normal BGL training windows."""

    def __init__(self) -> None:
        self.template_vocabulary: frozenset[str] | None = None

    def fit(self, train_normal_windows: Sequence[BglWindow]) -> "BglLogOnlyFeatureTransformer":
        if not train_normal_windows:
            raise ValueError("Feature vocabulary requires normal training windows")
        self.template_vocabulary = frozenset(
            template_id for window in train_normal_windows for template_id in window.sequence
        )
        return self

    def transform(self, windows: Sequence[BglWindow]) -> list[BglFeatureSample]:
        if self.template_vocabulary is None:
            raise RuntimeError("Transformer must be fitted before transform()")
        result: list[BglFeatureSample] = []
        for window in windows:
            templates = Counter(window.sequence)
            total = len(window.events)
            probabilities = [count / total for count in templates.values()]
            entropy = -sum(probability * log2(probability) for probability in probabilities)
            levels = Counter(event.level for event in window.events)
            unseen = sum(template not in self.template_vocabulary for template in window.sequence)
            features = {
                "total_logs": float(total),
                "unique_templates": float(len(templates)),
                "template_entropy": entropy,
                "top_template_ratio": max(templates.values()) / total,
                "unseen_template_ratio": unseen / total,
                "unique_hosts": float(len({event.host for event in window.events})),
                "unique_services": float(len({event.service for event in window.events})),
                "info_count": float(levels["INFO"]),
                "warn_count": float(levels["WARN"] + levels["WARNING"]),
                "error_count": float(levels["ERROR"]),
            }
            result.append(BglFeatureSample(window.sample_id, features, window.ground_truth))
        return result
