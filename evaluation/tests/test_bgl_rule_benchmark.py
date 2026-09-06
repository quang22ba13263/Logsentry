from __future__ import annotations

import unittest
from pathlib import Path

from evaluation.adapters.bgl_adapter import load_bgl_events, make_bgl_event_windows
from evaluation.detectors.log_only_rule import RuleConfig
from evaluation.runners.bgl_rule_benchmark import chronological_bgl_split, evaluate_bgl_rule


class BglRuleBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = Path(__file__).resolve().parents[2] / "Dataset/BGL/BGL_2k.log_structured.csv"
        cls.windows = make_bgl_event_windows(load_bgl_events(source))

    def test_chronological_split_is_disjoint_and_has_positive_support(self) -> None:
        splits = chronological_bgl_split(self.windows)
        all_ids = [window.sample_id for split in (splits.train, splits.validation, splits.test) for window in split]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(100, len(all_ids))
        self.assertTrue(any(window.ground_truth for window in splits.validation))
        self.assertTrue(any(window.ground_truth for window in splits.test))

    def test_rule_benchmark_returns_prediction_contract_and_metrics(self) -> None:
        rows, metrics = evaluate_bgl_rule(chronological_bgl_split(self.windows), RuleConfig())
        self.assertEqual(20, len(rows))
        self.assertEqual({"tp", "fp", "tn", "fn", "precision", "recall", "f1"}, set(metrics))
        self.assertTrue(all("ground_truth" in row and "reason" in row for row in rows))


if __name__ == "__main__":
    unittest.main()
