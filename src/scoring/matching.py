
from __future__ import annotations

import numpy as np

from src.constants import JND_MATCH


def calculate_matching_error(left_mags, right_mags, measured_mags=None):
    """Return an L/R mismatch penalty in JND units."""
    left = np.asarray(left_mags, dtype=float)
    right = np.asarray(right_mags, dtype=float)
    if left.shape != right.shape:
        raise ValueError("left_mags and right_mags must have the same length.")
    if left.size == 0:
        return 0.0
    diff = np.abs(left - right)
    if measured_mags is not None:
        measured = np.asarray(measured_mags, dtype=float)
        if measured.shape == diff.shape:
            weight = 1.0 + np.clip(np.abs(measured - np.mean(measured)) / (np.std(measured) + 1e-6), 0.0, 2.0)
            diff = diff * weight
    return float(np.mean(diff / float(JND_MATCH)))
