"""Scoring helpers."""

from .frequency_response import (
    calculate_fr_error,
    calculate_peakiness_metric,
    peakiness_metric,
    estimate_impedance_variation,
    flag_impedance_interaction,
)
from .distortion import (
    a_weighting_db_for,
    a_weighting_linear_for,
    calculate_masking_factor,
    calculate_thd_error,
    calculate_thd_error_profile,
    calculate_imd_error,
    calculate_imd_error_profile,
    calculate_distortion_score,
)
from .olive_score import calculate_olive_preference_score, calculate_olive_score, calculate_olive_band_stats
from .matching import calculate_matching_error
from .confidence import calculate_score_confidence_interval
from .final_score import (
    calculate_total_error,
    calculate_w_conf,
    estimate_amp_cost,
    calculate_effective_price,
    calculate_score,
    rank_scores,
)
from .uncertainty import calculate_uncertainty

__all__ = [
    "calculate_fr_error",
    "calculate_peakiness_metric",
    "peakiness_metric",
    "estimate_impedance_variation",
    "flag_impedance_interaction",
    "a_weighting_db_for",
    "a_weighting_linear_for",
    "calculate_masking_factor",
    "calculate_thd_error",
    "calculate_thd_error_profile",
    "calculate_imd_error",
    "calculate_imd_error_profile",
    "calculate_distortion_score",
    "calculate_olive_preference_score",
    "calculate_olive_score",
    "calculate_olive_band_stats",
    "calculate_matching_error",
    "calculate_score_confidence_interval",
    "calculate_total_error",
    "calculate_w_conf",
    "estimate_amp_cost",
    "calculate_effective_price",
    "calculate_score",
    "rank_scores",
    "calculate_uncertainty",
]
