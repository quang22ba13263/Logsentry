from __future__ import annotations

import unittest

from evaluation.adapters.hdfs_adapter import HdfsTrace
from evaluation.detectors.hdfs_log_only_rule import HdfsLogOnlyRuleDetector
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.features.hdfs_log_only_features import HdfsLogOnlyRuleFeatureTransformer


NORMAL_TRAIN = [
    {"trace_length": 3, "event_entropy": 1.0, "top_event_ratio": 0.5, "unseen_event_ratio": 0.0},
    {"trace_length": 4, "event_entropy": 1.1, "top_event_ratio": 0.5, "unseen_event_ratio": 0.0},
]


class HdfsLogOnlyRuleDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = HdfsLogOnlyRuleDetector(
            RuleConfig(normal_percentile=99.0, score_threshold=0.2)
        ).fit(NORMAL_TRAIN)

    def test_reports_trace_shape_reason(self) -> None:
        prediction = self.detector.detect(
            [{"trace_length": 8, "event_entropy": 1.0, "top_event_ratio": 0.5, "unseen_event_ratio": 0.2}]
        )[0]
        self.assertEqual(2, prediction.raw_score)
        self.assertEqual(1, prediction.prediction)
        self.assertIn("trace_length_above", prediction.reason)
        self.assertIn("unseen_event_ratio_above", prediction.reason)

    def test_rejects_label_type_and_block_id(self) -> None:
        for forbidden in ("ground_truth", "Label", "Type", "BlockId"):
            with self.subTest(forbidden=forbidden):
                row = dict(NORMAL_TRAIN[0], **{forbidden: "leak"})
                with self.assertRaisesRegex(ValueError, "Forbidden leakage-prone"):
                    self.detector.detect([row])

    def test_transformer_learns_unseen_events_from_normal_train_only(self) -> None:
        train = HdfsTrace("normal-block", ("E1", "E2", "E1"), {"E1": 2.0, "E2": 1.0}, 0)
        candidate = HdfsTrace("anomaly-block", ("E1", "E3"), {"E1": 1.0, "E3": 1.0}, 1)
        feature = HdfsLogOnlyRuleFeatureTransformer().fit([train]).transform([candidate])[0]
        self.assertEqual(0.5, feature.features["unseen_event_ratio"])
        self.assertNotIn("ground_truth", feature.features)
        self.assertNotIn("sample_id", feature.features)


if __name__ == "__main__":
    unittest.main()
