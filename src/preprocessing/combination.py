import numpy as np


def combine_sources(list_of_magnitudes):
    """
    Combine multiple FR curves with weights proportional to consistency.

    Weight for source s: w_s = 1 / (RMS deviation from mean + guard)
    Sources that deviate more from the consensus get lower weight.

    Returns
    -------
    combined   : 1-D array — weighted mean curve
    variance   : 1-D array — per-band variance across sources (used for E_unc)
    """
    n = len(list_of_magnitudes)
    if n == 1:
        arr = np.asarray(list_of_magnitudes[0], dtype=float)
        return arr, np.zeros_like(arr)

    stacked = np.array(list_of_magnitudes, dtype=float)   # (n, bands)

    # Compute per-source RMS deviation from the equal-weight mean
    mean_curve = np.mean(stacked, axis=0)
    rms_devs   = np.sqrt(np.mean((stacked - mean_curve) ** 2, axis=1))  # (n,)
    weights    = 1.0 / (rms_devs + 0.01)    # guard against division by zero
    weights   /= weights.sum()

    combined = np.average(stacked, axis=0, weights=weights)
    variance = np.var(stacked, axis=0)       # per-band, unweighted (for E_unc)

    return combined, variance