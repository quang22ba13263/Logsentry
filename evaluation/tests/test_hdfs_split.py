from __future__ import annotations

import unittest

from evaluation.adapters.hdfs_adapter import HdfsTrace
from evaluation.runners.hdfs_split import source_order_hdfs_split


class HdfsSplitTests(unittest.TestCase):
    def test_keeps_source_order_and_requires_validation_anomaly(self) -> None:
        traces = [
            HdfsTrace(f"block-{index}", ("E1",), {"E1": 1.0}, int(index == 7))
            for index in range(10)
        ]
        splits = source_order_hdfs_split(traces)
        self.assertEqual(("block-0", "block-1", "block-2", "block-3", "block-4", "block-5", "block-6"), tuple(item.sample_id for item in splits.train))
        self.assertEqual(("block-7",), tuple(item.sample_id for item in splits.validation))
        self.assertEqual(("block-8", "block-9"), tuple(item.sample_id for item in splits.test))

    def test_rejects_missing_validation_support_without_reading_test_labels(self) -> None:
        traces = [HdfsTrace(f"block-{index}", ("E1",), {"E1": 1.0}, 0) for index in range(10)]
        with self.assertRaisesRegex(ValueError, "Validation split lacks anomaly support"):
            source_order_hdfs_split(traces)


if __name__ == "__main__":
    unittest.main()
