"""Persist trusted, locally-produced evaluation candidates with file hashes."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import joblib
import tensorflow as tf

from evaluation.detectors.log_only_deeplog import DeepLogConfig, LogOnlyDeepLog
from evaluation.detectors.log_only_isolation_forest import (
    IsolationForestConfig,
    LogOnlyIsolationForest,
)


BUNDLE_SCHEMA_VERSION = 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_manifest(directory: Path, payload: dict[str, object]) -> Path:
    manifest_path = directory / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path


def save_isolation_forest_bundle(
    detector: LogOnlyIsolationForest,
    directory: str | Path,
    *,
    feature_transformer: object | None = None,
) -> Path:
    """Save a fitted IF, scaler, score reference and optional feature transformer."""
    if detector.model is None or detector._normal_raw_scores is None:
        raise RuntimeError("Cannot persist an unfitted Isolation Forest")
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    model_path = target / "isolation_forest.joblib"
    joblib.dump(
        {
            "feature_names": detector.feature_names,
            "config": asdict(detector.config),
            "scaler": detector.scaler,
            "model": detector.model,
            "normal_raw_scores": detector._normal_raw_scores,
            "feature_transformer": feature_transformer,
        },
        model_path,
    )
    return _write_manifest(
        target,
        {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "detector": "log_only_isolation_forest",
            "files": {model_path.name: sha256(model_path)},
            "has_feature_transformer": feature_transformer is not None,
        },
    )


def load_isolation_forest_bundle(directory: str | Path) -> tuple[LogOnlyIsolationForest, object | None]:
    """Load a trusted local IF bundle after checking its hash."""
    target = Path(directory)
    manifest = json.loads((target / "bundle_manifest.json").read_text(encoding="utf-8"))
    model_path = target / "isolation_forest.joblib"
    if manifest.get("detector") != "log_only_isolation_forest" or manifest["files"].get(model_path.name) != sha256(model_path):
        raise RuntimeError("Isolation Forest bundle manifest or file hash is invalid")
    payload = joblib.load(model_path)
    detector = LogOnlyIsolationForest(payload["feature_names"], IsolationForestConfig(**payload["config"]))
    detector.scaler = payload["scaler"]
    detector.model = payload["model"]
    detector._normal_raw_scores = payload["normal_raw_scores"]
    return detector, payload["feature_transformer"]


def save_deeplog_bundle(detector: LogOnlyDeepLog, directory: str | Path) -> Path:
    """Save a fitted DeepLog Keras model together with vocabulary and config."""
    if detector.model is None or detector.vocabulary is None:
        raise RuntimeError("Cannot persist an unfitted DeepLog model")
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=False)
    model_path = target / "deeplog.keras"
    detector.model.save(model_path)
    metadata_path = target / "deeplog_metadata.json"
    metadata_path.write_text(
        json.dumps({"config": asdict(detector.config), "vocabulary": detector.vocabulary}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return _write_manifest(
        target,
        {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "detector": "log_only_deeplog",
            "files": {model_path.name: sha256(model_path), metadata_path.name: sha256(metadata_path)},
        },
    )


def load_deeplog_bundle(directory: str | Path) -> LogOnlyDeepLog:
    """Load a trusted local DeepLog bundle after checking its hashes."""
    target = Path(directory)
    manifest = json.loads((target / "bundle_manifest.json").read_text(encoding="utf-8"))
    model_path, metadata_path = target / "deeplog.keras", target / "deeplog_metadata.json"
    if (
        manifest.get("detector") != "log_only_deeplog"
        or manifest["files"].get(model_path.name) != sha256(model_path)
        or manifest["files"].get(metadata_path.name) != sha256(metadata_path)
    ):
        raise RuntimeError("DeepLog bundle manifest or file hash is invalid")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    detector = LogOnlyDeepLog(DeepLogConfig(**metadata["config"]))
    detector.vocabulary = {str(token): int(index) for token, index in metadata["vocabulary"].items()}
    detector.model = tf.keras.models.load_model(model_path)
    return detector
