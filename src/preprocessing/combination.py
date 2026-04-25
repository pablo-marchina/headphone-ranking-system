import numpy as np


def combine_sources(list_of_magnitudes):
    """
    Combine multiple FR curves weighted by inter-source consistency.
    Weight for source s = 1 / (RMS deviation from consensus mean + guard).

    Returns
    -------
    combined : 1-D array — weighted mean curve
    variance : 1-D array — per-band WEIGHTED variance (consistent with weights)
    """
    n = len(list_of_magnitudes)
    if n == 1:
        arr = np.asarray(list_of_magnitudes[0], dtype=float)
        return arr, np.zeros_like(arr)

    stacked    = np.array(list_of_magnitudes, dtype=float)   # (n, bands)
    mean_curve = np.mean(stacked, axis=0)
    rms_devs   = np.sqrt(np.mean((stacked - mean_curve)**2, axis=1))  # (n,)
    weights    = 1.0 / (rms_devs + 0.01)
    weights   /= weights.sum()

    combined = np.average(stacked, axis=0, weights=weights)

    # Weighted variance — consistent with the same weights used for the mean
    w_col    = weights[:, np.newaxis]                        # (n, 1) for broadcasting
    variance = np.sum(w_col * (stacked - combined)**2, axis=0)

    return combined, variance