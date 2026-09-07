from __future__ import annotations

import unittest

from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog


class LogOnlyDeepLogTests(unittest.TestCase):
    def test_streaming_fit_and_batched_score(self) -> None:
        detector = LogOnlyDeepLog(
            DeepLogConfig(sequence_length=2, embedding_dim=4, lstm_units=4, epochs=1, batch_size=2)
        ).fit([("E1", "E2", "E1", "E2"), ("E1", "E2", "E2")])
        scores = detector.score([("E1", "E2", "E1"), ("E1", "E2", "E9")], batch_size=2)
        self.assertEqual(2, len(scores))
        self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
        self.assertEqual(1.0, scores[1])


if __name__ == "__main__":
    unittest.main()
