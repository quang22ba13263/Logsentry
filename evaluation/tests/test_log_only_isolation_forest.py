from __future__ import annotations

import unittest

from evaluation.detectors.log_only_isolation_forest import LogOnlyIsolationForest


NORMAL = [
    {"total_logs": 20.0, "template_entropy": 1.0},
    {"total_logs": 21.0, "template_entropy": 1.1},
    {"total_logs": 19.0, "template_entropy": 0.9},
    {"total_logs": 20.0, "template_entropy": 1.0},
]


class LogOnlyIsolationForestTests(unittest.TestCase):
    def test_fit_normal_only_and_score_is_normalized(self) -> None:
        detector = LogOnlyIsolationForest(["total_logs", "template_entropy"]).fit(NORMAL)
        prediction = detector.score([{"total_logs": 100.0, "template_entropy": 5.0}])[0]
        self.assertGreaterEqual(prediction.normalized_score, 0.0)
        self.assertLessEqual(prediction.normalized_score, 1.0)
        self.assertGreater(prediction.raw_score, 0.0)

    def test_rejects_label_leakage_and_missing_features(self) -> None:
        with self.assertRaisesRegex(ValueError, "Forbidden leakage-prone"):
            LogOnlyIsolationForest(["ground_truth"])
        detector = LogOnlyIsolationForest(["total_logs"]).fit([{"total_logs": 1.0}])
        with self.assertRaisesRegex(ValueError, "Forbidden leakage-prone"):
            detector.score([{"total_logs": 1.0, "Label": "-"}])
        with self.assertRaisesRegex(ValueError, "Missing Isolation Forest"):
            detector.score([{}])


if __name__ == "__main__":
    unittest.main()
