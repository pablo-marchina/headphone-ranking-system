import numpy as np
from src.constants import JND_FR


def calculate_fr_error(measured_mags, target_mags):
    """
    E_FR(h) = Σ_e |FR_h(e) − T(e)| / JND_FR · Δe

    Δe is constant on the uniform ERB grid → absorbed into mean().
    Returns a scalar in JND units.
    """
    if len(measured_mags) != len(target_mags):
        raise ValueError("measured_mags and target_mags must have the same length.")
    return float(np.mean(np.abs(measured_mags - target_mags) / JND_FR))