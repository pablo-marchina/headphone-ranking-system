import numpy as np
from src.constants import KAPPA, THD_THRESHOLD, JND_THD, EPSILON, MASKING_BANDWIDTH_POINTS


def calculate_masking_factor(measured_mags):
    """
    M_h(b) = 1 + κ · (1/|B_viz|) Σ_{b'∈B_viz(b)} E_rel,h(b')

    E_rel,h(b) = FR_h_final(b) − mean(FR_h_final)
        Deviation in dB relative to the headphone's own mean curve.
        Physically: how energetic this band is compared to the average level.
        NOT relative to the target (that was the discarded interpretation).

    B_viz(b) = ±MASKING_BANDWIDTH_POINTS (≈ ±1 critical band on the 500-pt ERB grid)
        Spectral spread: masking by a loud region affects adjacent critical bands.
    """
    # E_rel in dB — deviation from own curve mean (not from target)
    e_rel = measured_mags - np.mean(measured_mags)

    # Spread over ±1 critical band via uniform (box) convolution
    kernel_size = 2 * MASKING_BANDWIDTH_POINTS + 1
    kernel      = np.ones(kernel_size) / kernel_size
    e_rel_spread = np.convolve(e_rel, kernel, mode='same')

    return 1.0 + KAPPA * e_rel_spread


def calculate_thd_error(thd_measurements, measured_mags):
    """
    E_THD(h) = Σ_b max(0, THD_h(b) − τ_THD) / (JND_THD · M_h(b)) · Δb

    Δb is constant on the uniform ERB grid → absorbed into mean().
    thd_measurements: array in % (e.g. 0.5 for 0.5 % THD).
    Distortion below τ_THD is perceptually inaudible and earns zero penalty.
    """
    masking = calculate_masking_factor(measured_mags)
    excess  = np.maximum(0.0, thd_measurements - THD_THRESHOLD)
    error   = excess / (JND_THD * masking + EPSILON)
    return float(np.mean(error))