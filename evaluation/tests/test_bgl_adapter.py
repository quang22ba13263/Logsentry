from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone
from pathlib import Path

from evaluation.adapters.bgl_adapter import (
    ALLOWED_BGL_INPUT,
    BglEvent,
    iter_model_inputs,
    load_bgl_events,
    make_bgl_event_windows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BGL_SOURCE = PROJECT_ROOT / "Dataset" / "BGL" / "BGL_2k.log_structured.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BglAdapterTests(unittest.TestCase):
    def test_loads_expected_events_and_labels_without_mutating_dataset(self) -> None:
        source_hash_before = sha256(BGL_SOURCE)
        events = load_bgl_events(BGL_SOURCE)

        self.assertEqual(2000, len(events))
        self.assertEqual(143, sum(event.ground_truth for event in events))
        self.assertEqual(source_hash_before, sha256(BGL_SOURCE))
        self.assertEqual(events, sorted(events, key=lambda item: (item.timestamp, item.event_id)))

    def test_model_inputs_use_only_the_allow_list(self) -> None:
        event = load_bgl_events(BGL_SOURCE)[0]
        model_input = event.model_input()

        self.assertEqual(set(ALLOWED_BGL_INPUT), set(model_input))
        self.assertNotIn("Label", model_input)
        self.assertNotIn("ground_truth", model_input)
        self.assertNotIn("type", model_input)
        self.assertNotIn("block_id", model_input)
        self.assertEqual([model_input], list(iter_model_inputs([event])))

    def test_windows_are_non_overlapping_and_use_or_label(self) -> None:
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            BglEvent(
                event_id=f"bgl_event_{index:06d}",
                timestamp=timestamp,
                host="host",
                service="service",
                level="INFO",
                message="message",
                template_id=f"E{index}",
                template="template",
                ground_truth=int(index == 2),
            )
            for index in range(1, 8)
        ]

        windows = make_bgl_event_windows(events, size=3, stride=3)

        self.assertEqual(["bgl_window_000001", "bgl_window_000002"], [w.sample_id for w in windows])
        self.assertEqual([1, 0], [w.ground_truth for w in windows])
        self.assertEqual(("E1", "E2", "E3"), windows[0].sequence)
        self.assertEqual("bgl_event_000004", windows[1].event_start_id)

    def test_rejects_invalid_window_settings(self) -> None:
        with self.assertRaises(ValueError):
            make_bgl_event_windows([], size=0)
        with self.assertRaises(ValueError):
            make_bgl_event_windows([], stride=0)


if __name__ == "__main__":
    unittest.main()
