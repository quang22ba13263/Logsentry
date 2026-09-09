from __future__ import annotations

import tempfile
import unittest

from evaluation.artifacts.model_bundle import (
    load_deeplog_bundle,
    load_isolation_forest_bundle,
    save_deeplog_bundle,
    save_isolation_forest_bundle,
)
from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.detectors.log_only_isolation_forest import IsolationForestConfig, LogOnlyIsolationForest


class ModelBundleTests(unittest.TestCase):
    def test_isolation_forest_round_trip_preserves_scores_and_transformer(self) -> None:
        rows = [{"event_count": 1.0}, {"event_count": 2.0}, {"event_count": 3.0}]
        detector = LogOnlyIsolationForest(
            ("event_count",), IsolationForestConfig(n_estimators=8, random_seed=42)
        ).fit(rows)
        expected = detector.score(rows)
        transformer = {"fitted_on": "normal_train_only"}
        with tempfile.TemporaryDirectory() as temporary:
            save_isolation_forest_bundle(detector, f"{temporary}/if", feature_transformer=transformer)
            loaded, loaded_transformer = load_isolation_forest_bundle(f"{temporary}/if")
            actual = loaded.score(rows)
        self.assertEqual(transformer, loaded_transformer)
        self.assertEqual([item.raw_score for item in expected], [item.raw_score for item in actual])
        self.assertEqual([item.normalized_score for item in expected], [item.normalized_score for item in actual])

    def test_deeplog_round_trip_preserves_scores(self) -> None:
        sequences = [["E1", "E2", "E1", "E2"], ["E1", "E2", "E1", "E2"]]
        detector = LogOnlyDeepLog(
            DeepLogConfig(sequence_length=2, embedding_dim=4, lstm_units=4, epochs=1, batch_size=2)
        ).fit(sequences)
        expected = detector.score(sequences)
        with tempfile.TemporaryDirectory() as temporary:
            save_deeplog_bundle(detector, f"{temporary}/deeplog")
            loaded = load_deeplog_bundle(f"{temporary}/deeplog")
            actual = loaded.score(sequences)
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
