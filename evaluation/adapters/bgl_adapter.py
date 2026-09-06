"""Adapter for the Loghub BGL structured-log benchmark input.

The adapter deliberately keeps labels outside the model-input contract.  The
``ground_truth`` field is retained only to make deterministic splits and to
evaluate predictions after inference.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


REQUIRED_BGL_COLUMNS = frozenset(
    {
        "LineId",
        "Label",
        "Timestamp",
        "Node",
        "Component",
        "Type",
        "Level",
        "Content",
        "EventId",
        "EventTemplate",
    }
)

# The feature transformer must receive values from this allow-list only.
ALLOWED_BGL_INPUT = (
    "timestamp",
    "host",
    "service",
    "level",
    "message",
    "template_id",
    "template",
)

FORBIDDEN_FEATURE_TOKENS = ("label", "ground_truth", "type", "blockid")


@dataclass(frozen=True)
class BglEvent:
    """One normalized BGL log event in the common event contract."""

    event_id: str
    timestamp: datetime
    host: str
    service: str
    level: str
    message: str
    template_id: str
    template: str
    ground_truth: int

    def model_input(self) -> dict[str, object]:
        """Return only fields that are legitimate input for a model."""

        values = asdict(self)
        return {name: values[name] for name in ALLOWED_BGL_INPUT}


@dataclass(frozen=True)
class BglWindow:
    """An event-count BGL sample used by the v1 benchmark."""

    sample_id: str
    dataset: str
    event_start_id: str
    event_end_id: str
    timestamp_start: datetime
    timestamp_end: datetime
    sequence: tuple[str, ...]
    events: tuple[BglEvent, ...]
    ground_truth: int


def _parse_timestamp(value: str) -> datetime:
    """Convert BGL epoch seconds to an explicit UTC datetime."""

    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError) as exc:
        raise ValueError(f"Invalid BGL Timestamp value: {value!r}") from exc


def _require_columns(fieldnames: Sequence[str] | None) -> None:
    available = set(fieldnames or ())
    missing = REQUIRED_BGL_COLUMNS - available
    if missing:
        raise ValueError(f"BGL input is missing required columns: {sorted(missing)}")


def load_bgl_events(path: str | Path) -> list[BglEvent]:
    """Load and chronologically sort BGL events without modifying the source.

    ``Label`` is translated to the evaluation-only ``ground_truth`` flag.  It
    is never retained as a raw field in the normalized event.
    """

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"BGL structured log not found: {source}")

    events: list[BglEvent] = []
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            try:
                line_id = int(row["LineId"])
                timestamp = _parse_timestamp(row["Timestamp"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid BGL record at CSV row {row_number}") from exc

            service = row["Component"].strip() or row["Type"].strip()
            events.append(
                BglEvent(
                    event_id=f"bgl_event_{line_id:06d}",
                    timestamp=timestamp,
                    host=row["Node"].strip(),
                    service=service,
                    level=row["Level"].strip(),
                    message=row["Content"],
                    template_id=row["EventId"].strip(),
                    template=row["EventTemplate"],
                    ground_truth=int(row["Label"].strip() != "-"),
                )
            )

    # Keep the original row order as a stable tie breaker for equal timestamps.
    return sorted(events, key=lambda event: (event.timestamp, event.event_id))


def make_bgl_event_windows(
    events: Sequence[BglEvent], size: int = 20, stride: int = 20
) -> list[BglWindow]:
    """Create complete event-count windows and OR their evaluation labels.

    ``size=20, stride=20`` is the frozen BGL v1 protocol.  Partial tail
    windows are intentionally excluded so every sample has equivalent context.
    """

    if size <= 0 or stride <= 0:
        raise ValueError("Window size and stride must be positive integers")

    windows: list[BglWindow] = []
    for start in range(0, len(events) - size + 1, stride):
        event_window = tuple(events[start : start + size])
        sample_number = len(windows) + 1
        windows.append(
            BglWindow(
                sample_id=f"bgl_window_{sample_number:06d}",
                dataset="BGL",
                event_start_id=event_window[0].event_id,
                event_end_id=event_window[-1].event_id,
                timestamp_start=event_window[0].timestamp,
                timestamp_end=event_window[-1].timestamp,
                sequence=tuple(event.template_id for event in event_window),
                events=event_window,
                ground_truth=int(any(event.ground_truth for event in event_window)),
            )
        )
    return windows


def iter_model_inputs(events: Iterable[BglEvent]) -> Iterable[dict[str, object]]:
    """Yield allow-listed model inputs and fail closed on leakage-prone names."""

    for event in events:
        values = event.model_input()
        invalid = [
            name
            for name in values
            if any(token in name.casefold() for token in FORBIDDEN_FEATURE_TOKENS)
        ]
        if invalid:
            raise ValueError(f"Forbidden feature columns: {invalid}")
        yield values
