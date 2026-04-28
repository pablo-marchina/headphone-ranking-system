"""Moore-Glasberg inspired loudness-grid utilities.

This module replaces the previous ERB helper as the canonical base grid for
frequency-response analysis. The implementation keeps the familiar ERB-rate
spacing, but the public API is intentionally named around the louder model so
future work can extend it without changing callers again.
"""

from __future__ import annotations

import numpy as np

from src.constants import MAX_FREQ, MIN_FREQ, erb_to_hz, hz_to_erb


def generate_loudness_grid(min_f: float = MIN_FREQ, max_f: float = MAX_FREQ, num_points: int = 500) -> np.ndarray:
    """Return a uniform grid in ERB-rate space mapped back to Hz."""
    if num_points < 2:
        raise ValueError("num_points must be at least 2")
    erb_grid = np.linspace(hz_to_erb(min_f), hz_to_erb(max_f), num_points)
    return erb_to_hz(erb_grid)


def interpolate_to_loudness_grid(freqs, magnitudes, num_points: int = 500):
    """Resample a frequency-response curve onto the loudness-analysis grid."""
    freqs = np.asarray(freqs, dtype=float)
    magnitudes = np.asarray(magnitudes, dtype=float)
    if freqs.ndim != 1 or magnitudes.ndim != 1:
        raise ValueError("freqs and magnitudes must be one-dimensional arrays")
    if freqs.size != magnitudes.size:
        raise ValueError("freqs and magnitudes must have the same length")
    if freqs.size < 2:
        raise ValueError("at least two samples are required")

    order = np.argsort(freqs)
    freqs = freqs[order]
    magnitudes = magnitudes[order]

    loudness_freqs = generate_loudness_grid(num_points=num_points)
    resampled = np.interp(loudness_freqs, freqs, magnitudes, left=magnitudes[0], right=magnitudes[-1])
    return loudness_freqs, resampled


# Backward-compatible alias for older call sites.
interpolate_to_erb = interpolate_to_loudness_grid
