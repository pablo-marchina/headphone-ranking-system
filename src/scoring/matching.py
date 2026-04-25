import numpy as np
from src.constants import JND_MATCH, EPSILON


def calculate_matching_error(left_mags, right_mags, fr_mags):
    """
    E_match(h) = Σ_e |L_h(e) − R_h(e)| · E_rel+(e) / JND_match · Δe

    E_rel+(e) = max(0, FR(e) − mean(FR))
        Energy weighting: L/R imbalances are perceptually more salient where
        there is more signal (above the curve mean).
        Normalised to [0, 1] so the weight bonus doesn't inflate the scale.

    Δe constant on uniform ERB grid → absorbed into mean().

    Parameters
    ----------
    left_mags, right_mags : 1-D arrays — ERB-interpolated, smoothed channel FRs
    fr_mags               : 1-D array  — mean (L+R)/2 reference curve
    """
    diff = np.abs(left_mags - right_mags)

    # Regions energetically above the mean carry extra perceptual weight
    e_rel_plus = np.maximum(0.0, fr_mags - np.mean(fr_mags))
    max_val    = np.max(e_rel_plus)
    e_rel_norm = e_rel_plus / max_val if max_val > 0 else np.zeros_like(e_rel_plus)

    # Weight = 1 (baseline everywhere) + [0,1] bonus in energetic bands
    weighted = diff * (1.0 + e_rel_norm)
    return float(np.mean(weighted / JND_MATCH))