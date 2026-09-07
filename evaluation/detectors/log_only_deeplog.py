"""DeepLog-style LSTM next-event detector for isolated benchmark sequences."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Sequence

import numpy as np
import tensorflow as tf


@dataclass(frozen=True)
class DeepLogConfig:
    sequence_length: int = 10
    embedding_dim: int = 16
    lstm_units: int = 32
    epochs: int = 5
    batch_size: int = 32
    random_seed: int = 42


class LogOnlyDeepLog:
    """LSTM trained only on normal train-window EventId sequences."""

    def __init__(self, config: DeepLogConfig | None = None) -> None:
        self.config = config or DeepLogConfig()
        self.vocabulary: dict[str, int] | None = None
        self.model: tf.keras.Model | None = None

    def fit(self, normal_sequences: Sequence[Sequence[str]]) -> "LogOnlyDeepLog":
        tokens = sorted({token for sequence in normal_sequences for token in sequence})
        if not tokens:
            raise ValueError("DeepLog requires normal training sequences")
        self.vocabulary = {token: index + 1 for index, token in enumerate(tokens)}
        encoded = [[self.vocabulary[token] for token in sequence] for sequence in normal_sequences]
        contexts, targets = [], []
        length = self.config.sequence_length
        for sequence in encoded:
            for index in range(length, len(sequence)):
                contexts.append(sequence[index - length:index]); targets.append(sequence[index])
        if not contexts:
            raise ValueError("Normal sequences are shorter than sequence_length")
        tf.keras.utils.set_random_seed(self.config.random_seed)
        self.model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=(length,)),
            tf.keras.layers.Embedding(len(self.vocabulary) + 1, self.config.embedding_dim),
            tf.keras.layers.LSTM(self.config.lstm_units),
            tf.keras.layers.Dense(len(self.vocabulary) + 1, activation="softmax"),
        ])
        self.model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
        self.model.fit(np.asarray(contexts), np.asarray(targets), epochs=self.config.epochs, batch_size=self.config.batch_size, verbose=0)
        return self

    def score(self, sequences: Sequence[Sequence[str]], batch_size: int = 4096) -> list[float]:
        if self.model is None or self.vocabulary is None:
            raise RuntimeError("LogOnlyDeepLog must be fitted before score()")
        unk = 0; length = self.config.sequence_length; scores = [0.0] * len(sequences)
        contexts: list[list[int]] = []; targets: list[int] = []; owners: list[int] = []
        def flush() -> None:
            if not contexts: return
            probabilities = self.model.predict(np.asarray(contexts), batch_size=batch_size, verbose=0)
            for owner, target, probability in zip(owners, targets, probabilities, strict=True):
                surprise = 1.0 if target == unk else 1.0 - float(probability[target])
                scores[owner] = max(scores[owner], surprise)
            contexts.clear(); targets.clear(); owners.clear()
        for owner, sequence in enumerate(sequences):
            encoded = [self.vocabulary.get(token, unk) for token in sequence]
            for index in range(length, len(encoded)):
                contexts.append(encoded[index - length:index]); targets.append(encoded[index]); owners.append(owner)
                if len(contexts) >= batch_size: flush()
        flush()
        return scores
