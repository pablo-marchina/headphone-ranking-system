
from __future__ import annotations

import re
from typing import Iterable, Optional

import numpy as np
from src.constants import (
    SIGMA_SINGLE_SOURCE, SIGMA_THD_EXPECTED, SIGMA_MATCH_EXPECTED
)

_HIGH_VARIATION_FACTORS = (
    ("hifiman", 1.45),
    ("audeze", 1.30),
    ("early hifiman", 1.55),
    ("early audeze", 1.40),
)


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _unit_variation_multiplier(headphone_name: Optional[str] = None, source_names: Optional[Iterable[str]] = None) -> float:
    text = " ".join(filter(None, [_normalize_text(headphone_name)] + [_normalize_text(x) for x in (source_names or [])]))
    multiplier = 1.0
    for token, factor in _HIGH_VARIATION_FACTORS:
        if token in text:
            multiplier = max(multiplier, factor)
    return multiplier


def calculate_uncertainty(variance_array, n_sources, thd_available, match_available=True, headphone_name: Optional[str] = None, source_names: Optional[Iterable[str]] = None):
    """
    E_unc(h) = σ_inter-source + σ_bootstrap + 1[THD=∅]·σ_THD + 1[LR=∅]·σ_match

    σ_inter-source
        n_sources == 1 → SIGMA_SINGLE_SOURCE (dataset-estimated; not zero,
                         because one source ≠ perfectly reliable)
        n_sources > 1  → mean(std per ERB band) from observed inter-source variance
                         with a unit-to-unit multiplier for historically variable brands.

    σ_bootstrap
        Approximated as 0.5 · σ_inter.

    THD term   : activated when THD measurements are absent for this headphone.
    Match term : activated when separate L/R channel data is unavailable.
    """
    if n_sources > 1 and variance_array is not None and len(variance_array) > 0:
        sigma_inter = float(np.mean(np.sqrt(np.maximum(variance_array, 0.0))))
    else:
        sigma_inter = float(SIGMA_SINGLE_SOURCE)

    sigma_inter *= _unit_variation_multiplier(headphone_name=headphone_name, source_names=source_names)
    sigma_bootstrap = 0.5 * sigma_inter
    thd_term = 0.0 if thd_available else SIGMA_THD_EXPECTED
    match_term = 0.0 if match_available else SIGMA_MATCH_EXPECTED

    return sigma_inter + sigma_bootstrap + thd_term + match_term
