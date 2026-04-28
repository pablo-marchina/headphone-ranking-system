from __future__ import annotations

import numpy as np

# --- Frequency range ---
MIN_FREQ = 20
MAX_FREQ = 20000
DEFAULT_GRID_POINTS = 500


# --- ERB conversion (Glasberg & Moore, 1990) ---
def hz_to_erb(f):
    return 21.4 * np.log10(0.00437 * f + 1.0)


def erb_to_hz(e):
    return (10 ** (e / 21.4) - 1.0) / 0.00437


# --- ISO 226:2003 helper data ---
# Frequency-dependent FR sensitivity is approximated from the 40-phon contour.
ISO226_FREQS = np.array([
    20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0,
    200.0, 250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0,
    1600.0, 2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0,
    10000.0, 12500.0,
], dtype=float)

ISO226_AF = np.array([
    0.532, 0.506, 0.480, 0.455, 0.432, 0.409, 0.387, 0.367, 0.349,
    0.330, 0.315, 0.301, 0.288, 0.276, 0.267, 0.259, 0.253, 0.250,
    0.246, 0.244, 0.243, 0.243, 0.243, 0.242, 0.242, 0.245, 0.254,
    0.271, 0.301,
], dtype=float)

ISO226_LU = np.array([
    -31.6, -27.2, -23.0, -19.1, -15.9, -13.0, -10.3, -8.1, -6.2,
    -4.5, -3.1, -2.0, -1.1, -0.4, 0.0, 0.3, 0.5, 0.0, -2.7, -4.1,
    -1.0, 1.7, 2.5, 1.2, -2.1, -7.1, -11.2, -10.7, -3.1,
], dtype=float)

ISO226_TF = np.array([
    78.5, 68.7, 59.5, 51.1, 44.0, 37.5, 31.5, 26.5, 22.1, 17.9,
    14.4, 11.4, 8.6, 6.2, 4.4, 3.0, 2.2, 2.4, 3.5, 1.7, -1.3, -4.2,
    -6.0, -5.4, -1.5, 6.0, 12.6, 13.9, 12.3,
], dtype=float)


def _iso226_contour(phon: float = 40.0):
    """Return the ISO 226 contour (frequency, SPL) for a given phon level."""
    phon = float(phon)
    af = ISO226_AF
    lu = ISO226_LU
    tf = ISO226_TF
    af_term = 4.47e-3 * (10 ** (0.025 * phon) - 1.15)
    bf_term = (0.4 * 10 ** (((tf + lu) / 10.0) - 9.0)) ** af
    af_total = af_term + bf_term
    spl = (10.0 / af) * np.log10(af_total) - lu + 94.0
    return ISO226_FREQS.copy(), spl


def _generate_default_frequency_grid():
    erb_grid = np.linspace(hz_to_erb(MIN_FREQ), hz_to_erb(MAX_FREQ), DEFAULT_GRID_POINTS)
    return erb_to_hz(erb_grid)


def _jnd_curve_from_iso226(freqs: np.ndarray) -> np.ndarray:
    """Map ISO 226 sensitivity into a frequency-dependent JND curve.

    Lower values mean the response deviation is more audible.
    The curve is intentionally bounded to remain numerically stable.
    """
    contour_freqs, contour_spl = _iso226_contour(phon=40.0)
    interp_spl = np.interp(freqs, contour_freqs, contour_spl, left=contour_spl[0], right=contour_spl[-1])
    sensitivity = interp_spl.max() - interp_spl
    if np.allclose(sensitivity.max(), 0.0):
        normalized = np.zeros_like(sensitivity)
    else:
        normalized = sensitivity / sensitivity.max()

    # High sensitivity (3–4 kHz) => small JND; low sensitivity => larger JND.
    return 0.45 + (2.35 * (1.0 - normalized))


JND_FR_FREQS = _generate_default_frequency_grid()
JND_FR = _jnd_curve_from_iso226(JND_FR_FREQS)
JND_THD = 0.05
JND_MATCH = 0.5


def jnd_fr_for(freqs):
    """Interpolate the frequency-dependent JND curve to arbitrary frequencies."""
    freqs = np.asarray(freqs, dtype=float)
    return np.interp(freqs, JND_FR_FREQS, JND_FR, left=JND_FR[0], right=JND_FR[-1])


# --- THD threshold (below this = perceptually inaudible) ---
THD_THRESHOLD = 0.1

# --- Masking coefficient (Zwicker 1961; Moore & Glasberg 1983) ---
KAPPA = 0.07
MASKING_BANDWIDTH_POINTS = 13

# --- Score regularisation ---
EPSILON = 0.1

# --- Uncertainty defaults ---
SIGMA_SINGLE_SOURCE = 0.5
SIGMA_THD_EXPECTED = 0.3
SIGMA_MATCH_EXPECTED = 0.2
