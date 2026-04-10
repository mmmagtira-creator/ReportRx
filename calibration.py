from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
from scipy.optimize import minimize_scalar


EPS = 1e-8


@dataclass
class TemperatureScaler:
    temperature: float = 1.0

    def predict(self, prob: float) -> float:
        prob = min(max(prob, EPS), 1.0 - EPS)
        logit = math.log(prob / (1.0 - prob))
        scaled = logit / max(self.temperature, EPS)
        return 1.0 / (1.0 + math.exp(-scaled))

    def transform(self, probs: Sequence[float]) -> List[float]:
        return [self.predict(prob) for prob in probs]


def _nll_for_temperature(temperature: float, probs: np.ndarray, labels: np.ndarray) -> float:
    temperature = max(float(temperature), EPS)
    logits = np.log(np.clip(probs, EPS, 1.0 - EPS) / np.clip(1.0 - probs, EPS, 1.0 - EPS))
    scaled = logits / temperature
    calibrated = 1.0 / (1.0 + np.exp(-scaled))
    calibrated = np.clip(calibrated, EPS, 1.0 - EPS)
    nll = -(labels * np.log(calibrated) + (1.0 - labels) * np.log(1.0 - calibrated)).mean()
    return float(nll)


def fit_temperature_scaler(probs: Sequence[float], labels: Sequence[int]) -> TemperatureScaler:
    probs_array = np.asarray(probs, dtype=float)
    labels_array = np.asarray(labels, dtype=float)

    if len(probs_array) == 0:
        return TemperatureScaler(temperature=1.0)

    result = minimize_scalar(
        lambda temperature: _nll_for_temperature(temperature, probs_array, labels_array),
        bounds=(0.05, 10.0),
        method="bounded",
    )
    temperature = float(result.x if result.success else 1.0)
    return TemperatureScaler(temperature=temperature)