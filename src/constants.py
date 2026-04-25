import numpy as np

# --- Frequency range ---
MIN_FREQ = 20
MAX_FREQ = 20000

# --- ERB conversion (Glasberg & Moore, 1990) ---
def hz_to_erb(f):
    return 21.4 * np.log10(0.00437 * f + 1.0)

def erb_to_hz(e):
    return (10 ** (e / 21.4) - 1.0) / 0.00437

# --- JND values (Just Noticeable Difference) ---
JND_FR    = 1.0    # dB  — scalar approximation; ideally frequency-dependent per ISO 226
JND_THD   = 0.05   # %   — perceptual resolution for harmonic distortion
JND_MATCH = 0.5    # dB  — L/R imbalance detection threshold

# --- THD threshold (below this = perceptually inaudible) ---
THD_THRESHOLD = 0.1   # 0.1 %

# --- Masking coefficient (Zwicker 1961; Moore & Glasberg 1983) ---
# κ ∈ [0.05, 0.1] — midpoint used; verify invariance empirically with real dataset
KAPPA = 0.07

# Neighbourhood for spectral spread: ±1 critical band ≈ ±13 pts on a 500-pt ERB grid
# (37.2 ERB span / 500 pts → ~13.4 pts/ERB)
MASKING_BANDWIDTH_POINTS = 13

# --- Score regularisation ---
# Below ε JND the difference is perceptually irrelevant → prevents score explosion
EPSILON = 0.1

# --- Uncertainty defaults (calibrate once full dataset is available) ---
SIGMA_SINGLE_SOURCE  = 0.5   # Estimated σ when only one measurement source exists
SIGMA_THD_EXPECTED   = 0.3   # Additive E_unc term when THD data is absent
SIGMA_MATCH_EXPECTED = 0.2   # Additive E_unc term when L/R channel data is absent