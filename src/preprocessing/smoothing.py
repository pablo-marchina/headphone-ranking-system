import numpy as np
from scipy.ndimage import gaussian_filter1d

# 1/12 octave on a 500-point ERB grid:
#   ERB span  ≈ 37.2 ERB  (20 Hz → 20 kHz)
#   pts/ERB   ≈ 13.4
#   1/12 oct  ≈ 0.44 ERB  → ~6 pts FWHM → σ ≈ FWHM/2.35 ≈ 2.5 pts
# We round to 3 for a very slight extra smoothing (conservative).
ERB_SMOOTHING_SIGMA = 3


def apply_smoothing(magnitudes, sigma=ERB_SMOOTHING_SIGMA):
    """
    Gaussian smoothing on the ERB-rate grid.
    Default sigma ≈ 1/12 octave perceptual bandwidth.
    Applied uniformly — same smoothing at every frequency, as required by the model.
    """
    return gaussian_filter1d(magnitudes.astype(float), sigma=sigma)