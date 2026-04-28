from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from src.constants import (
    SIGMA_MATCH_EXPECTED,
    SIGMA_SINGLE_SOURCE,
    SIGMA_THD_EXPECTED,
)
from src.scoring.final_score import calculate_score, calculate_total_error, calculate_w_conf
from src.scoring.uncertainty import calculate_uncertainty


def _as_1d_array(values) -> Optional[np.ndarray]:
    if values is None:
        return None
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return None
    return arr.reshape(-1)


def _bootstrap_indices(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.integers(0, n, size=n)


def _resample_paired_profiles(
    variance_array,
    e_fr_profile,
    distortion_profile,
    rng: np.random.Generator,
):
    var_arr = _as_1d_array(variance_array)
    fr_arr = _as_1d_array(e_fr_profile)
    dist_arr = _as_1d_array(distortion_profile)

    candidates = [arr for arr in (var_arr, fr_arr, dist_arr) if arr is not None]
    if not candidates:
        return None, None, None

    n = min(arr.size for arr in candidates)
    if n <= 0:
        return None, None, None

    idx = _bootstrap_indices(n, rng)

    boot_var = var_arr[idx] if var_arr is not None and var_arr.size >= n else None
    boot_fr = fr_arr[idx] if fr_arr is not None and fr_arr.size >= n else None
    boot_dist = dist_arr[idx] if dist_arr is not None and dist_arr.size >= n else None
    return boot_var, boot_fr, boot_dist


def _single_source_bootstrap_uncertainty(
    e_unc: float,
    thd_available: bool,
    match_available: bool,
    rng: np.random.Generator,
    headphone_name: Optional[str] = None,
    source_names: Optional[Iterable[str]] = None,
) -> float:
    fixed_terms = 0.0
    if not thd_available:
        fixed_terms += SIGMA_THD_EXPECTED
    if not match_available:
        fixed_terms += SIGMA_MATCH_EXPECTED

    base_unc = float(e_unc) if e_unc is not None else 0.0
    base_sigma = max(1e-6, (base_unc - fixed_terms) / 1.5)
    sigma_sd = max(1e-6, 0.25 * max(SIGMA_SINGLE_SOURCE, base_sigma))
    sigma_sample = max(1e-6, rng.normal(base_sigma, sigma_sd))

    # Reconstruct the single-source uncertainty with the sampled historical sigma.
    return float(1.5 * sigma_sample + fixed_terms)


def calculate_score_confidence_interval(
    *,
    e_total: float,
    price,
    e_unc: float,
    variance_array=None,
    n_sources: int = 1,
    thd_available: bool = True,
    match_available: bool = True,
    e_fr_profile=None,
    distortion_profile=None,
    e_match: float = 0.0,
    sensitivity_db_mw: Optional[float] = None,
    headphone_name: Optional[str] = None,
    source_names: Optional[Iterable[str]] = None,
    n_boot: int = 400,
    ci: float = 0.95,
    seed: int = 42,
) -> Optional[Tuple[float, float]]:
    """Bootstrap a 95% confidence interval for the final score.

    n_sources > 1
        Resamples the observed inter-source variance together with the
        per-band error profiles, preserving the shared grid.

    n_sources = 1
        Uses the historical single-source sigma as the uncertainty prior.
    """
    if price is None:
        return None
    try:
        price_val = float(price)
    except Exception:
        return None
    if not np.isfinite(price_val) or price_val <= 0:
        return None

    alpha = (1.0 - float(ci)) / 2.0
    if not 0.0 < alpha < 0.5:
        raise ValueError("ci must be between 0 and 1.")

    rng = np.random.default_rng(seed)
    samples = []

    var_arr = _as_1d_array(variance_array)
    fr_arr = _as_1d_array(e_fr_profile)
    dist_arr = _as_1d_array(distortion_profile)
    paired_available = (
        n_sources > 1 and var_arr is not None and var_arr.size > 0
    )

    for _ in range(max(64, int(n_boot))):
        if paired_available:
            boot_var, boot_fr, boot_dist = _resample_paired_profiles(var_arr, fr_arr, dist_arr, rng)
            boot_e_unc = calculate_uncertainty(
                boot_var,
                n_sources,
                thd_available,
                match_available,
                headphone_name=headphone_name,
                source_names=source_names,
            )
            if boot_fr is not None and boot_dist is not None:
                boot_e_fr = float(np.mean(boot_fr))
                boot_distortion = float(np.mean(boot_dist))
                boot_e_total = calculate_total_error(
                    boot_e_fr,
                    boot_distortion,
                    e_match,
                    e_fr_profile=boot_fr,
                    distortion_profile=boot_dist,
                )
            else:
                boot_e_total = float(e_total)
        else:
            boot_e_unc = _single_source_bootstrap_uncertainty(
                e_unc,
                thd_available,
                match_available,
                rng,
                headphone_name=headphone_name,
                source_names=source_names,
            )
            boot_e_total = float(e_total)

        boot_score = calculate_score(
            boot_e_total,
            calculate_w_conf(boot_e_unc),
            price_val,
            sensitivity_db_mw=sensitivity_db_mw,
        )
        if boot_score is not None and np.isfinite(boot_score):
            samples.append(float(boot_score))

    if not samples:
        return None

    lower = float(np.quantile(samples, alpha))
    upper = float(np.quantile(samples, 1.0 - alpha))
    return lower, upper
