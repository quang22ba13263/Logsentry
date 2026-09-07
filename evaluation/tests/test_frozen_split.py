from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.runners.frozen_split import load_hdfs_development_assignments


class FrozenSplitTests(unittest.TestCase):
    def test_reads_train_validation_and_seals_test_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split.csv"
            path.write_text("sample_id,split,ground_truth\na,train,0\nb,validation,1\nc,test,\n", encoding="utf-8")
            assignments = load_hdfs_development_assignments(path)
        self.assertEqual(("a",), tuple(item.sample_id for item in assignments.train))
        self.assertEqual(("b",), tuple(item.sample_id for item in assignments.validation))

    def test_rejects_exposed_test_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split.csv"
            path.write_text("sample_id,split,ground_truth\na,train,0\nb,validation,1\nc,test,0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not expose"):
                load_hdfs_development_assignments(path)


if __name__ == "__main__":
    unittest.main()
