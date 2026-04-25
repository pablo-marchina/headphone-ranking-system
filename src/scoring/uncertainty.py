import numpy as np
from src.constants import (
    SIGMA_SINGLE_SOURCE, SIGMA_THD_EXPECTED, SIGMA_MATCH_EXPECTED
)


def calculate_uncertainty(variance_array, n_sources, thd_available, match_available=True):
    """
    E_unc(h) = σ_inter-source + σ_bootstrap + 1[THD=∅]·σ_THD + 1[LR=∅]·σ_match

    σ_inter-source
        n_sources == 1 → SIGMA_SINGLE_SOURCE (dataset-estimated; not zero,
                         because one source ≠ perfectly reliable)
        n_sources > 1  → mean(std per ERB band) from observed inter-source variance

    σ_bootstrap
        Approximated as 0.5 · σ_inter (full bootstrap deferred to
        dataset-level calibration, where ERB-band resampling is feasible).

    THD term   : activated when THD measurements are absent for this headphone.
    Match term : activated when separate L/R channel data is unavailable.
    """
    if n_sources > 1 and variance_array is not None and len(variance_array) > 0:
        sigma_inter = float(np.mean(np.sqrt(np.maximum(variance_array, 0.0))))
    else:
        sigma_inter = SIGMA_SINGLE_SOURCE

    sigma_bootstrap = 0.5 * sigma_inter
    thd_term        = 0.0 if thd_available   else SIGMA_THD_EXPECTED
    match_term      = 0.0 if match_available else SIGMA_MATCH_EXPECTED

    return sigma_inter + sigma_bootstrap + thd_term + match_term