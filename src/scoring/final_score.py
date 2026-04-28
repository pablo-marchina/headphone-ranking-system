
from __future__ import annotations

import math
from typing import Iterable, Optional

import numpy as np

from src.constants import EPSILON


def _as_float_array(values):
    if values is None:
        return None
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr


def calculate_cross_masked_distortion(e_fr_profile=None, distortion_profile=None, cross_mask_strength: float = 0.35):
    """Apply cross-masking so tonal errors can partially hide distortion."""
    if distortion_profile is None:
        return None

    distortion = _as_float_array(distortion_profile)
    if distortion is None or distortion.size == 0:
        return 0.0

    if e_fr_profile is None:
        return float(np.mean(distortion))

    fr_profile = _as_float_array(e_fr_profile)
    if fr_profile is None or fr_profile.size == 0:
        return float(np.mean(distortion))

    if fr_profile.size != distortion.size:
        x_old = np.linspace(0.0, 1.0, fr_profile.size)
        x_new = np.linspace(0.0, 1.0, distortion.size)
        fr_profile = np.interp(x_new, x_old, fr_profile)

    relief = np.clip(fr_profile / (1.0 + fr_profile), 0.0, 1.0)
    mask = 1.0 - (float(cross_mask_strength) * relief)
    return float(np.mean(distortion * mask))


def calculate_total_error(e_fr, e_thd, e_match, e_fr_profile=None, distortion_profile=None, cross_mask_strength: float = 0.35):
    """Combine the major perceptual errors.

    When per-band profiles are supplied, distortion is discounted in bands
    where the tonal error is already large, reflecting cross-masking.
    """
    masked_distortion = calculate_cross_masked_distortion(
        e_fr_profile=e_fr_profile,
        distortion_profile=distortion_profile if distortion_profile is not None else e_thd,
        cross_mask_strength=cross_mask_strength,
    )
    if masked_distortion is None:
        masked_distortion = float(e_thd)
    return float(e_fr + masked_distortion + e_match)


def calculate_w_conf(e_unc):
    """w_conf(h) = 1 / (1 + E_unc)"""
    return 1.0 / (1.0 + float(e_unc))


def estimate_amp_cost(sensitivity_db_mw: Optional[float], threshold_db_mw: float = 85.0, max_cost_brl: float = 180.0) -> float:
    """Heuristic amplifier cost when sensitivity is too low to drive easily."""
    if sensitivity_db_mw is None:
        return 0.0
    try:
        sensitivity = float(sensitivity_db_mw)
    except Exception:
        return 0.0
    if not math.isfinite(sensitivity) or sensitivity >= threshold_db_mw:
        return 0.0
    deficit = threshold_db_mw - sensitivity
    estimated = 15.0 * deficit
    return float(min(max_cost_brl, max(0.0, estimated)))


def calculate_effective_price(price, sensitivity_db_mw: Optional[float] = None, threshold_db_mw: float = 85.0):
    if price is None:
        return None
    try:
        base_price = float(price)
    except Exception:
        return None
    if base_price <= 0:
        return None
    return base_price + estimate_amp_cost(sensitivity_db_mw, threshold_db_mw=threshold_db_mw)


def calculate_score(e_total, w_conf, price, sensitivity_db_mw: Optional[float] = None, epsilon=EPSILON, threshold_db_mw: float = 85.0):
    """Score(h) = w_conf / (max(E_total, ε) · P_effective)"""
    effective_price = calculate_effective_price(price, sensitivity_db_mw=sensitivity_db_mw, threshold_db_mw=threshold_db_mw)
    if effective_price is None:
        return None
    return w_conf / (max(float(e_total), epsilon) * float(effective_price))


def rank_scores(results):
    """Sort result dicts by Score (descending); add 'rank' and 'percentile'."""
    scored = [dict(r) for r in results if r.get('score') is not None]
    scored.sort(key=lambda x: x['score'], reverse=True)
    n = len(scored)
    for i, r in enumerate(scored):
        r['rank'] = i + 1
        r['percentile'] = round(100.0 * (n - i) / n, 1) if n else None
    return scored
