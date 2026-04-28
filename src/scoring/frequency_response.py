
from __future__ import annotations

import numpy as np
from src.constants import JND_FR


def _as_jnd_array(length: int) -> np.ndarray:
    jnd = np.asarray(JND_FR, dtype=float)
    if jnd.ndim == 0:
        return np.full(length, float(jnd), dtype=float)
    if jnd.size == length:
        return jnd.astype(float, copy=False)
    if jnd.size < 2:
        return np.full(length, float(jnd.reshape(())), dtype=float)
    x_old = np.linspace(0.0, 1.0, jnd.size)
    x_new = np.linspace(0.0, 1.0, length)
    return np.interp(x_new, x_old, jnd)


def calculate_peakiness_metric(magnitudes, freqs=None) -> float:
    """Measure resonance-like sharpness as the standard deviation of the first derivative."""
    mags = np.asarray(magnitudes, dtype=float)
    if mags.size < 3:
        return 0.0

    if freqs is None:
        derivative = np.diff(mags)
    else:
        freqs = np.asarray(freqs, dtype=float)
        if freqs.shape != mags.shape:
            raise ValueError("freqs and magnitudes must have the same length when freqs is provided.")
        x = np.log10(np.clip(freqs, 1e-12, None))
        derivative = np.diff(mags) / np.diff(x)

    return float(np.std(derivative))


# Backward-compatible alias.
peakiness_metric = calculate_peakiness_metric


def calculate_fr_error(measured_mags, target_mags, alpha: float = 0.7):
    """Return the weighted FR error in JND units.

    E_FR = alpha * mean(|Δ| / JND_FR) + (1 - alpha) * p95(|Δ| / JND_FR)
    with alpha defaulting to 0.7.
    """
    measured = np.asarray(measured_mags, dtype=float)
    target = np.asarray(target_mags, dtype=float)
    if measured.shape != target.shape:
        raise ValueError("measured_mags and target_mags must have the same length.")
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError("alpha must be between 0 and 1.")

    normalized_error = np.abs(measured - target) / _as_jnd_array(measured.size)
    mean_term = float(np.mean(normalized_error))
    p95_term = float(np.percentile(normalized_error, 95))
    return float(float(alpha) * mean_term + (1.0 - float(alpha)) * p95_term)


def estimate_impedance_variation(impedance_curve) -> float:
    """Return the impedance spread in ohms for a curve represented as values or (freq, ohm) pairs."""
    if impedance_curve is None:
        return 0.0
    arr = np.asarray(impedance_curve, dtype=float)
    if arr.size == 0:
        return 0.0
    if arr.ndim == 2 and arr.shape[1] >= 2:
        values = arr[:, 1]
    else:
        values = arr.reshape(-1)
    if values.size < 2:
        return 0.0
    return float(np.nanmax(values) - np.nanmin(values))


def flag_impedance_interaction(impedance_curve, is_ba_iem: bool = False, source_impedance_ohms: float = 0.0, variation_threshold: float = 10.0) -> bool:
    """Flag BA IEMs whose impedance variation suggests source-dependent FR changes."""
    if not is_ba_iem:
        return False
    if float(source_impedance_ohms) <= 0.0:
        return False
    if estimate_impedance_variation(impedance_curve) <= float(variation_threshold):
        return False
    return True
