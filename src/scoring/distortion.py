
"""Distortion-related scoring helpers.

This module adds IEC 61672 A-weighting, THD and IMD penalties, and helpers
to expose both scalar errors and per-band error profiles.
"""

from __future__ import annotations

import numpy as np

from src.constants import KAPPA, THD_THRESHOLD, JND_THD, EPSILON, MASKING_BANDWIDTH_POINTS

# IEC 61672 A-weighting reference table (nominal frequencies, dB).
A_WEIGHTING_FREQS = np.array([
    20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0,
    200.0, 250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0,
    1600.0, 2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0,
    10000.0, 12500.0, 16000.0, 20000.0,
], dtype=float)

A_WEIGHTING_DB = np.array([
    -50.5, -44.7, -39.4, -34.6, -30.2, -26.2, -22.5, -19.1, -16.1,
    -13.4, -10.9, -8.6, -6.6, -4.8, -3.2, -1.9, -0.8, 0.0, 0.6, 1.0,
    1.2, 1.3, 1.2, 1.0, 0.5, -0.1, -1.1, -2.5, -4.3, -6.6, -9.3,
], dtype=float)


def _as_float_array(values):
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr


def a_weighting_db_for(freqs) -> np.ndarray:
    """Interpolate IEC 61672 A-weighting weights in dB for arbitrary frequencies."""
    freqs = _as_float_array(freqs)
    if freqs.size == 0:
        return freqs.astype(float)
    clipped = np.clip(freqs, A_WEIGHTING_FREQS[0], A_WEIGHTING_FREQS[-1])
    return np.interp(clipped, A_WEIGHTING_FREQS, A_WEIGHTING_DB)


def a_weighting_linear_for(freqs) -> np.ndarray:
    """Return linear A-weighting multipliers."""
    return 10.0 ** (a_weighting_db_for(freqs) / 20.0)


def calculate_masking_factor(measured_mags):
    """
    M_h(b) = 1 + κ · (1/|B_viz|) Σ_{b'∈B_viz(b)} E_rel,h(b')

    E_rel,h(b) = FR_h_final(b) − mean(FR_h_final)
        Deviation in dB relative to the headphone's own mean curve.

    B_viz(b) = ±MASKING_BANDWIDTH_POINTS (≈ ±1 critical band on the 500-pt ERB grid)
    """
    measured_mags = _as_float_array(measured_mags)
    if measured_mags.size == 0:
        return measured_mags

    e_rel = measured_mags - np.mean(measured_mags)
    kernel_size = 2 * MASKING_BANDWIDTH_POINTS + 1
    kernel = np.ones(kernel_size, dtype=float) / kernel_size
    e_rel_spread = np.convolve(e_rel, kernel, mode="same")
    return 1.0 + KAPPA * e_rel_spread


def _weighted_distortion_profile(distortion_measurements, measured_mags, freqs=None, threshold=THD_THRESHOLD):
    distortion_measurements = _as_float_array(distortion_measurements)
    measured_mags = _as_float_array(measured_mags)

    if distortion_measurements.shape != measured_mags.shape:
        raise ValueError("distortion_measurements and measured_mags must have the same length.")
    if distortion_measurements.size == 0:
        return np.zeros_like(distortion_measurements)

    masking = calculate_masking_factor(measured_mags)
    excess = np.maximum(0.0, distortion_measurements - float(threshold))
    error = excess / (JND_THD * masking + EPSILON)

    if freqs is not None:
        freqs = _as_float_array(freqs)
        if freqs.shape != distortion_measurements.shape:
            raise ValueError("freqs must have the same length as distortion_measurements.")
        error = error * a_weighting_linear_for(freqs)

    return error


def _weighted_distortion_error(distortion_measurements, measured_mags, freqs=None, threshold=THD_THRESHOLD):
    profile = _weighted_distortion_profile(distortion_measurements, measured_mags, freqs=freqs, threshold=threshold)
    return float(np.mean(profile)) if profile.size else 0.0


def calculate_thd_error(thd_measurements, measured_mags, freqs=None):
    """
    E_THD(h) = mean(max(0, THD_h(b) − τ_THD) / (JND_THD · M_h(b)))
    with optional A-weighting by frequency band.
    """
    return _weighted_distortion_error(thd_measurements, measured_mags, freqs=freqs, threshold=THD_THRESHOLD)


def calculate_thd_error_profile(thd_measurements, measured_mags, freqs=None):
    return _weighted_distortion_profile(thd_measurements, measured_mags, freqs=freqs, threshold=THD_THRESHOLD)


def calculate_imd_error(imd_measurements, measured_mags, freqs=None):
    """IMD penalty with the same perceptual weighting strategy as THD."""
    return _weighted_distortion_error(imd_measurements, measured_mags, freqs=freqs, threshold=THD_THRESHOLD)


def calculate_imd_error_profile(imd_measurements, measured_mags, freqs=None):
    return _weighted_distortion_profile(imd_measurements, measured_mags, freqs=freqs, threshold=THD_THRESHOLD)


def combine_distortion_errors(thd_error=None, imd_error=None):
    """Combine distortion components conservatively."""
    values = []
    for value in (thd_error, imd_error):
        if value is None:
            continue
        try:
            numeric = float(value)
        except Exception:
            continue
        if np.isfinite(numeric):
            values.append(numeric)
    return float(np.sum(values)) if values else 0.0


def calculate_distortion_score(thd_measurements, measured_mags, freqs=None, imd_measurements=None):
    """Convenience helper returning the combined distortion penalty."""
    thd_error = None
    imd_error = None
    if thd_measurements is not None:
        thd_error = calculate_thd_error(thd_measurements, measured_mags, freqs=freqs)
    if imd_measurements is not None:
        imd_error = calculate_imd_error(imd_measurements, measured_mags, freqs=freqs)
    return combine_distortion_errors(thd_error=thd_error, imd_error=imd_error)
