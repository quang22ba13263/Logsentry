from __future__ import annotations

import unittest
from types import SimpleNamespace

from evaluation.runners.run_hdfs_final_test import RELEASE_TOKEN, _score_rows, validate_release


class HdfsFinalTestGuardTests(unittest.TestCase):
    def test_rejects_missing_flag_or_token(self) -> None:
        with self.assertRaises(PermissionError):
            validate_release(release_flag=False, approval_token=RELEASE_TOKEN)
        with self.assertRaises(PermissionError):
            validate_release(release_flag=True, approval_token="wrong")

    def test_allows_explicit_release(self) -> None:
        validate_release(release_flag=True, approval_token=RELEASE_TOKEN)

    def test_score_rows_pairs_each_trace_with_its_score(self) -> None:
        rows = _score_rows(
            [SimpleNamespace(sample_id="block-a", ground_truth=0), SimpleNamespace(sample_id="block-b", ground_truth=1)],
            "hdfs_log_only_rule",
            [(0.1, 0.2), (0.3, 0.9)],
            0.5,
            "frozen_validation_rule_threshold",
        )
        self.assertEqual(["block-a", "block-b"], [row["sample_id"] for row in rows])
        self.assertEqual([0, 1], [row["prediction"] for row in rows])


if __name__ == "__main__":
    unittest.main()
