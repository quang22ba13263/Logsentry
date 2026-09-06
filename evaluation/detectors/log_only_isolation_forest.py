"""One-class Isolation Forest baseline for log-only benchmark features."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from evaluation.detectors.log_only_rule import FORBIDDEN_INPUT_TOKENS


@dataclass(frozen=True)
class IsolationForestConfig:
    n_estimators: int = 100
    max_samples: str = "auto"
    contamination: str = "auto"
    random_seed: int = 42


@dataclass(frozen=True)
class IsolationForestPrediction:
    raw_score: float
    normalized_score: float


class LogOnlyIsolationForest:
    """Isolation Forest whose vocabulary, scaler and model fit normal train only."""

    def __init__(self, feature_names: Sequence[str], config: IsolationForestConfig | None = None) -> None:
        if not feature_names:
            raise ValueError("Isolation Forest requires at least one feature")
        invalid = [name for name in feature_names if any(token in name.casefold() for token in FORBIDDEN_INPUT_TOKENS)]
        if invalid:
            raise ValueError(f"Forbidden leakage-prone feature columns: {invalid}")
        self.feature_names = tuple(feature_names)
        self.config = config or IsolationForestConfig()
        self.scaler = RobustScaler()
        self.model: IsolationForest | None = None
        self._normal_raw_scores: list[float] | None = None

    def _matrix(self, rows: Sequence[Mapping[str, object]]) -> np.ndarray:
        if not rows:
            raise ValueError("At least one feature row is required")
        values: list[list[float]] = []
        for row in rows:
            forbidden = [name for name in row if any(token in name.casefold() for token in FORBIDDEN_INPUT_TOKENS)]
            if forbidden:
                raise ValueError(f"Forbidden leakage-prone feature columns: {forbidden}")
            missing = [name for name in self.feature_names if name not in row]
            if missing:
                raise ValueError(f"Missing Isolation Forest features: {missing}")
            values.append([float(row[name]) for name in self.feature_names])
        return np.asarray(values, dtype=float)

    def fit(self, train_normal_features: Sequence[Mapping[str, object]]) -> "LogOnlyIsolationForest":
        matrix = self._matrix(train_normal_features)
        transformed = self.scaler.fit_transform(matrix)
        self.model = IsolationForest(
            n_estimators=self.config.n_estimators,
            max_samples=self.config.max_samples,
            contamination=self.config.contamination,
            random_state=self.config.random_seed,
        ).fit(transformed)
        self._normal_raw_scores = sorted((-self.model.score_samples(transformed)).tolist())
        return self

    def score(self, features: Sequence[Mapping[str, object]]) -> list[IsolationForestPrediction]:
        if self.model is None or self._normal_raw_scores is None:
            raise RuntimeError("LogOnlyIsolationForest must be fitted before score()")
        raw_scores = -self.model.score_samples(self.scaler.transform(self._matrix(features)))
        total = len(self._normal_raw_scores)
        return [
            IsolationForestPrediction(float(raw), bisect_right(self._normal_raw_scores, float(raw)) / total)
            for raw in raw_scores
        ]
