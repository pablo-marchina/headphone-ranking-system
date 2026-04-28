"""Sean Olive-inspired preference score.

This is intentionally complementary to E_FR: it summarizes broad tonal balance
across four bands and can be combined with other metrics later, but it does not
replace the main frequency-response error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np

BANDS: Dict[str, Tuple[float, float]] = {
    "bass": (80.0, 200.0),
    "mid_bass": (200.0, 400.0),
    "midrange": (400.0, 2000.0),
    "treble": (2000.0, 20000.0),
}

# Heuristic weights inspired by Olive-style bandwise preference regressions.
BAND_WEIGHTS: Dict[str, float] = {
    "bass": 0.90,
    "mid_bass": 0.60,
    "midrange": 0.40,
    "treble": 0.70,
}


@dataclass(frozen=True)
class OliveBandStats:
    bass: float
    mid_bass: float
    midrange: float
    treble: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "bass": self.bass,
            "mid_bass": self.mid_bass,
            "midrange": self.midrange,
            "treble": self.treble,
        }


def _ensure_arrays(freqs, magnitudes, target_mags=None):
    freqs = np.asarray(freqs, dtype=float)
    mags = np.asarray(magnitudes, dtype=float)
    if freqs.ndim != 1 or mags.ndim != 1:
        raise ValueError("freqs and magnitudes must be one-dimensional arrays")
    if freqs.size != mags.size:
        raise ValueError("freqs and magnitudes must have the same length")

    if target_mags is None:
        target = np.zeros_like(mags)
    else:
        target = np.asarray(target_mags, dtype=float)
        if target.shape != mags.shape:
            raise ValueError("target_mags must match magnitudes shape when provided")
    return freqs, mags, target


def _band_mask(freqs: np.ndarray, low: float, high: float) -> np.ndarray:
    return (freqs >= low) & (freqs < high)


def calculate_olive_band_stats(freqs, magnitudes, target_mags=None) -> OliveBandStats:
    """Return mean deviation (measured - target) per broad tonal band."""
    freqs, mags, target = _ensure_arrays(freqs, magnitudes, target_mags)
    diff = mags - target

    values = []
    for low, high in BANDS.values():
        mask = _band_mask(freqs, low, high)
        if np.any(mask):
            values.append(float(np.mean(diff[mask])))
        else:
            # Fallback to interpolation on the requested band midpoint.
            midpoint = np.sqrt(low * high)
            values.append(float(np.interp(midpoint, freqs, diff, left=diff[0], right=diff[-1])))

    return OliveBandStats(*values)


def calculate_olive_preference_score(freqs, magnitudes, target_mags=None, scale: float = 10.0) -> float:
    """Return a higher-is-better tonal preference score.

    The score penalizes broad deviations from the reference target across the
    main Olive-style tonal bands. It is intentionally lightweight and stable.
    """
    band_stats = calculate_olive_band_stats(freqs, magnitudes, target_mags=target_mags)
    penalties = 0.0
    for band_name, stat in band_stats.as_dict().items():
        penalties += BAND_WEIGHTS[band_name] * abs(float(stat))

    score = float(scale - penalties)
    return max(0.0, score)


# Backward-compatible alias.
calculate_olive_score = calculate_olive_preference_score
