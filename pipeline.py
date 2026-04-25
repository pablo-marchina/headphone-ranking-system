import numpy as np
from src.preprocessing.erb        import interpolate_to_erb
from src.preprocessing.alignment  import align_gain
from src.preprocessing.smoothing  import apply_smoothing
from src.preprocessing.combination import combine_sources
from src.scoring.frequency_response import calculate_fr_error
from src.scoring.distortion         import calculate_thd_error
from src.scoring.matching           import calculate_matching_error
from src.scoring.uncertainty        import calculate_uncertainty
from src.scoring.final_score        import (
    calculate_total_error, calculate_w_conf, calculate_score
)
from src.constants import MIN_FREQ, MAX_FREQ


def run_evaluation_pipeline(name, sources_data, target_freqs, target_mags,
                             thd_data=None, price=None):
    """
    Full perceptual evaluation pipeline for one headphone.

    Parameters
    ----------
    name          : str
    sources_data  : list of dicts from fetch_autoeq_data()
                    Keys: 'freqs', 'mags', 'left_mags', 'right_mags', 'source'
    target_freqs  : 1-D array — Harman target frequencies
    target_mags   : 1-D array — Harman target magnitudes
    thd_data      : scalar (%) | 1-D array | None
    price         : float (BRL) | None

    Returns
    -------
    dict with all error components, score, and metadata — or None if no data.
    """
    if not sources_data:
        return None

    # ------------------------------------------------------------------
    # 1. Interpolate target to ERB grid once (shared reference)
    # ------------------------------------------------------------------
    erb_freqs, target_erb = interpolate_to_erb(target_freqs, target_mags)

    # ------------------------------------------------------------------
    # 2. Pre-process every source independently
    # ------------------------------------------------------------------
    proc_left  = []
    proc_right = []
    has_lr     = False

    for src in sources_data:
        freqs = src['freqs']
        l_raw = src.get('left_mags',  src.get('mags'))
        r_raw = src.get('right_mags', src.get('mags'))

        # Detect real L/R (not just duplicated mono)
        if not np.allclose(l_raw, r_raw, atol=0.05):
            has_lr = True

        # a. Interpolate to ERB
        _, erb_l = interpolate_to_erb(freqs, l_raw)
        _, erb_r = interpolate_to_erb(freqs, r_raw)

        # b. Gain alignment: offset derived from mono average (same shift for both
        #    channels so L/R differences are preserved, not erased)
        erb_mono  = (erb_l + erb_r) / 2.0
        _, offset = align_gain(erb_freqs, erb_mono, erb_freqs, target_erb)
        al_l = erb_l + offset
        al_r = erb_r + offset

        # c. Smoothing (~1/12 octave)
        proc_left.append(apply_smoothing(al_l))
        proc_right.append(apply_smoothing(al_r))

    # ------------------------------------------------------------------
    # 3. Combine sources (weighted by inter-source consistency)
    # ------------------------------------------------------------------
    n = len(sources_data)
    if n == 1:
        final_left  = proc_left[0]
        final_right = proc_right[0]
        variance    = None
    else:
        final_left,  var_l = combine_sources(proc_left)
        final_right, var_r = combine_sources(proc_right)
        variance = (var_l + var_r) / 2.0

    # Mono reference for E_FR and masking
    final_mags = (final_left + final_right) / 2.0

    # ------------------------------------------------------------------
    # 4. Error components
    # ------------------------------------------------------------------
    e_fr = calculate_fr_error(final_mags, target_erb)

    # E_THD — zero + uncertainty inflation if no data
    if thd_data is not None:
        if np.isscalar(thd_data):
            thd_arr = np.full(len(erb_freqs), float(thd_data))
        else:
            thd_raw = np.asarray(thd_data, dtype=float)
            _, thd_arr = interpolate_to_erb(
                np.linspace(MIN_FREQ, MAX_FREQ, len(thd_raw)), thd_raw
            )
        e_thd         = calculate_thd_error(thd_arr, final_mags)
        thd_available = True
    else:
        e_thd         = 0.0
        thd_available = False

    # E_match — zero + uncertainty inflation if no separate L/R
    if has_lr:
        e_match         = calculate_matching_error(final_left, final_right, final_mags)
        match_available = True
    else:
        e_match         = 0.0
        match_available = False

    # ------------------------------------------------------------------
    # 5. Uncertainty → confidence weight (separate from E_total)
    # ------------------------------------------------------------------
    e_unc  = calculate_uncertainty(variance, n, thd_available, match_available)
    w_conf = calculate_w_conf(e_unc)

    # ------------------------------------------------------------------
    # 6. Score
    # ------------------------------------------------------------------
    e_total = calculate_total_error(e_fr, e_thd, e_match)
    score   = calculate_score(e_total, w_conf, price) if (price and price > 0) else None

    return {
        'name':            name,
        'e_fr':            round(e_fr,    4),
        'e_thd':           round(e_thd,   4),
        'e_match':         round(e_match, 4),
        'e_unc':           round(e_unc,   4),
        'w_conf':          round(w_conf,  4),
        'e_total':         round(e_total, 4),
        'n_sources':       n,
        'thd_available':   thd_available,
        'match_available': match_available,
        'price_brl':       price,
        'score':           round(score, 6) if score is not None else None,
    }