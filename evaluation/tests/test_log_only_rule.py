from __future__ import annotations

import unittest

from evaluation.detectors.log_only_rule import LogOnlyRuleDetector, RuleConfig


NORMAL_TRAIN = [
    {
        "total_logs": 20,
        "template_entropy": 1.0,
        "top_template_ratio": 0.50,
        "unseen_template_ratio": 0.0,
    },
    {
        "total_logs": 22,
        "template_entropy": 1.1,
        "top_template_ratio": 0.45,
        "unseen_template_ratio": 0.0,
    },
]


class LogOnlyRuleDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = LogOnlyRuleDetector(
            RuleConfig(normal_percentile=99.0, score_threshold=0.20)
        ).fit(NORMAL_TRAIN)

    def test_uses_only_log_features_and_reports_reason(self) -> None:
        prediction = self.detector.detect(
            [
                {
                    "total_logs": 30,
                    "template_entropy": 1.1,
                    "top_template_ratio": 0.45,
                    "unseen_template_ratio": 0.2,
                }
            ]
        )[0]

        self.assertEqual(2, prediction.raw_score)
        self.assertEqual(0.4, prediction.normalized_score)
        self.assertEqual(1, prediction.prediction)
        self.assertIn("total_logs_above", prediction.reason)
        self.assertIn("unseen_template_ratio_above", prediction.reason)

    def test_rejects_label_and_identifier_leakage(self) -> None:
        row = dict(NORMAL_TRAIN[0], ground_truth=0)
        with self.assertRaisesRegex(ValueError, "Forbidden leakage-prone"):
            self.detector.detect([row])

        row = dict(NORMAL_TRAIN[0], BlockId="blk_1")
        with self.assertRaisesRegex(ValueError, "Forbidden leakage-prone"):
            self.detector.detect([row])

    def test_rejects_missing_log_feature_instead_of_defaulting_to_zero(self) -> None:
        row = dict(NORMAL_TRAIN[0])
        del row["template_entropy"]
        with self.assertRaisesRegex(ValueError, "Missing required"):
            self.detector.detect([row])

    def test_requires_fit(self) -> None:
        detector = LogOnlyRuleDetector()
        with self.assertRaisesRegex(RuntimeError, "must be fitted"):
            detector.detect(NORMAL_TRAIN)


if __name__ == "__main__":
    unittest.main()
