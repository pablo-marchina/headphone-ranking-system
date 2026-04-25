import numpy as np


def align_gain(freqs, magnitudes, target_freqs, target_mags, f_min=200, f_max=2000):
    """
    L1-optimal gain alignment: find the constant offset c* that minimises
        Σ |FR(f) + c* − target(f)|   over the midrange window [f_min, f_max].

    Closed-form solution: c* = median(target − FR)  in the window.
    Restricting to midrange (200–2 kHz) avoids bass roll-off and
    treble diffraction artefacts biasing the alignment.

    Parameters
    ----------
    freqs, magnitudes  : 1-D arrays — headphone FR on ERB grid
    target_freqs, target_mags : 1-D arrays — target on the same ERB grid
    f_min, f_max       : float — alignment window in Hz

    Returns
    -------
    aligned_mags : magnitudes + c*
    offset       : float — c* in dB
    """
    mask = (freqs >= f_min) & (freqs <= f_max)
    if not np.any(mask):
        mask = np.ones(len(freqs), dtype=bool)   # fallback: use full range

    offset = float(np.median(target_mags[mask] - magnitudes[mask]))
    return magnitudes + offset, offset