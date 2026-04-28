from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np

from src.constants import DEFAULT_GRID_POINTS, MIN_FREQ, MAX_FREQ, JND_FR, jnd_fr_for
from src.preprocessing.loudness_model import interpolate_to_erb
from src.preprocessing.rig_normalization import apply_rig_offset
from src.scoring.confidence import calculate_score_confidence_interval
from src.scoring.distortion import (
    calculate_thd_error_profile,
    calculate_imd_error_profile,
)
from src.scoring.final_score import (
    calculate_total_error,
    calculate_w_conf,
    calculate_score,
)
from src.scoring.frequency_response import (
    calculate_fr_error,
    calculate_peakiness_metric,
    flag_impedance_interaction,
)
from src.scoring.matching import calculate_matching_error
from src.scoring.uncertainty import calculate_uncertainty


def _align_gain(freqs, measured_mags, target_freqs, target_mags):
    freqs = np.asarray(freqs, dtype=float)
    measured_mags = np.asarray(measured_mags, dtype=float)
    target_freqs = np.asarray(target_freqs, dtype=float)
    target_mags = np.asarray(target_mags, dtype=float)

    lo = max(200.0, float(np.min(freqs)), float(np.min(target_freqs)))
    hi = min(2000.0, float(np.max(freqs)), float(np.max(target_freqs)))
    if hi <= lo:
        offset = float(np.mean(target_mags) - np.mean(measured_mags))
        return measured_mags + offset, offset

    grid = np.geomspace(lo, hi, 48)
    meas = np.interp(grid, freqs, measured_mags, left=measured_mags[0], right=measured_mags[-1])
    targ = np.interp(grid, target_freqs, target_mags, left=target_mags[0], right=target_mags[-1])
    offset = float(np.mean(targ - meas))
    return measured_mags + offset, offset


def _apply_smoothing(values, sigma_points: int = 3):
    values = np.asarray(values, dtype=float)
    if values.size < 5 or sigma_points <= 0:
        return values
    radius = int(max(1, 3 * sigma_points))
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x / float(sigma_points)) ** 2)
    kernel /= np.sum(kernel)
    return np.convolve(values, kernel, mode="same")


def _combine_sources(list_of_magnitudes):
    n = len(list_of_magnitudes)
    if n == 1:
        arr = np.asarray(list_of_magnitudes[0], dtype=float)
        return arr, np.zeros_like(arr)

    stacked = np.array(list_of_magnitudes, dtype=float)
    mean_curve = np.mean(stacked, axis=0)
    rms_devs = np.sqrt(np.mean((stacked - mean_curve) ** 2, axis=1))
    weights = 1.0 / (rms_devs + 0.01)
    weights /= weights.sum()

    combined = np.average(stacked, axis=0, weights=weights)
    w_col = weights[:, np.newaxis]
    variance = np.sum(w_col * (stacked - combined) ** 2, axis=0)
    return combined, variance


def _lookup_offset(label: str, rig_offsets: Optional[Mapping[str, float]]) -> float:
    if not rig_offsets:
        return 0.0
    label_l = str(label or "").lower()
    for key, value in rig_offsets.items():
        if str(key).lower() in label_l:
            try:
                return float(value)
            except Exception:
                continue
    return 0.0


def _extract_distortion_payload(thd_data: Any, rtings_metrics: Optional[Mapping[str, Any]] = None):
    payload = {}
    if isinstance(thd_data, Mapping):
        payload.update(thd_data)
    elif thd_data is not None:
        payload["thd"] = thd_data
    if rtings_metrics:
        for key in ("thd", "thd_plus_n", "imd", "sensitivity_db_mw", "impedance_ohms", "impedance_curve"):
            if key in rtings_metrics and key not in payload:
                payload[key] = rtings_metrics[key]
    return payload


def _coerce_measurement_array(value: Any, length: int):
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return np.full(length, float(arr), dtype=float)
    if arr.size == length:
        return arr.astype(float, copy=False)
    if arr.size < 2:
        return np.full(length, float(arr.reshape(())), dtype=float)
    x_old = np.linspace(0.0, 1.0, arr.size)
    x_new = np.linspace(0.0, 1.0, length)
    return np.interp(x_new, x_old, arr)


def run_evaluation_pipeline(
    name,
    sources_data,
    target_freqs,
    target_mags,
    thd_data=None,
    price=None,
    rtings_metrics=None,
    rig_offsets=None,
    source_impedance_ohms: float = 0.0,
):
    """Full perceptual evaluation pipeline for one headphone."""
    if not sources_data:
        return None

    target_freqs = np.asarray(target_freqs, dtype=float)
    target_mags = np.asarray(target_mags, dtype=float)
    erb_freqs, target_erb = interpolate_to_erb(target_freqs, target_mags)
    jnd_curve = jnd_fr_for(erb_freqs)

    proc_left = []
    proc_right = []
    source_labels = []
    has_lr = False

    for src in sources_data:
        freqs = np.asarray(src['freqs'], dtype=float)
        l_raw = np.asarray(src.get('left_mags', src.get('mags')), dtype=float)
        r_raw = np.asarray(src.get('right_mags', src.get('mags')), dtype=float)
        label = str(src.get('source', 'unknown'))
        source_labels.append(label)

        if not np.allclose(l_raw, r_raw, atol=0.05):
            has_lr = True

        _, erb_l = interpolate_to_erb(freqs, l_raw)
        _, erb_r = interpolate_to_erb(freqs, r_raw)
        erb_mono = (erb_l + erb_r) / 2.0

        rig_offset = _lookup_offset(label, rig_offsets)
        if rig_offset:
            erb_l = apply_rig_offset(erb_l, rig_offset)
            erb_r = apply_rig_offset(erb_r, rig_offset)
            erb_mono = apply_rig_offset(erb_mono, rig_offset)

        _, offset = _align_gain(erb_freqs, erb_mono, erb_freqs, target_erb)
        al_l = erb_l + offset
        al_r = erb_r + offset

        proc_left.append(_apply_smoothing(al_l))
        proc_right.append(_apply_smoothing(al_r))

    n = len(sources_data)
    if n == 1:
        final_left = proc_left[0]
        final_right = proc_right[0]
        variance = None
    else:
        final_left, var_l = _combine_sources(proc_left)
        final_right, var_r = _combine_sources(proc_right)
        variance = (var_l + var_r) / 2.0

    final_mags = (final_left + final_right) / 2.0
    e_fr_profile = np.abs(final_mags - target_erb) / np.maximum(jnd_curve, 1e-6)
    e_fr = calculate_fr_error(final_mags, target_erb)
    peakiness = calculate_peakiness_metric(final_mags, freqs=erb_freqs)

    distortion_payload = _extract_distortion_payload(thd_data, rtings_metrics=rtings_metrics)
    thd_measurements = distortion_payload.get('thd_plus_n') if distortion_payload.get('thd_plus_n') is not None else distortion_payload.get('thd')
    imd_measurements = distortion_payload.get('imd')
    sensitivity_db_mw = distortion_payload.get('sensitivity_db_mw')
    impedance_curve = distortion_payload.get('impedance_curve')
    impedance_flag = flag_impedance_interaction(
        impedance_curve,
        is_ba_iem=bool(distortion_payload.get('is_ba_iem', False)),
        source_impedance_ohms=source_impedance_ohms,
    )

    thd_available = thd_measurements is not None or imd_measurements is not None
    if thd_measurements is not None:
        thd_arr = _coerce_measurement_array(thd_measurements, len(erb_freqs))
        thd_profile = calculate_thd_error_profile(thd_arr, final_mags, freqs=erb_freqs)
    else:
        thd_profile = np.zeros_like(final_mags)

    if imd_measurements is not None:
        imd_arr = _coerce_measurement_array(imd_measurements, len(erb_freqs))
        imd_profile = calculate_imd_error_profile(imd_arr, final_mags, freqs=erb_freqs)
    else:
        imd_profile = np.zeros_like(final_mags)

    distortion_profile = thd_profile + imd_profile
    e_thd = float(np.mean(distortion_profile)) if distortion_profile.size else 0.0

    if has_lr:
        e_match = calculate_matching_error(final_left, final_right, final_mags)
        match_available = True
    else:
        e_match = 0.0
        match_available = False

    e_unc = calculate_uncertainty(
        variance,
        n,
        thd_available,
        match_available,
        headphone_name=name,
        source_names=source_labels,
    )
    if impedance_flag:
        e_unc += 0.15
    w_conf = calculate_w_conf(e_unc)

    e_total = calculate_total_error(
        e_fr,
        e_thd,
        e_match,
        e_fr_profile=e_fr_profile,
        distortion_profile=distortion_profile,
    )
    score = calculate_score(
        e_total,
        w_conf,
        price,
        sensitivity_db_mw=sensitivity_db_mw,
    ) if (price is not None and price > 0) else None

    ci = None
    if score is not None:
        ci = calculate_score_confidence_interval(
            e_total=e_total,
            price=price,
            e_unc=e_unc,
            variance_array=variance,
            n_sources=n,
            thd_available=thd_available,
            match_available=match_available,
            e_fr_profile=e_fr_profile,
            distortion_profile=distortion_profile,
            e_match=e_match,
            sensitivity_db_mw=sensitivity_db_mw,
            headphone_name=name,
            source_names=source_labels,
        )

    return {
        'name': name,
        'e_fr': round(float(e_fr), 4),
        'e_thd': round(float(e_thd), 4),
        'e_match': round(float(e_match), 4),
        'e_unc': round(float(e_unc), 4),
        'w_conf': round(float(w_conf), 4),
        'e_total': round(float(e_total), 4),
        'n_sources': n,
        'thd_available': thd_available,
        'match_available': match_available,
        'price_brl': price,
        'score': round(float(score), 6) if score is not None else None,
        'confidence_interval': tuple(round(float(x), 6) for x in ci) if ci is not None else None,
        'score_lower_95': round(float(ci[0]), 6) if ci is not None else None,
        'score_upper_95': round(float(ci[1]), 6) if ci is not None else None,
        'peakiness': round(float(peakiness), 4),
        'impedance_interaction': impedance_flag,
    }
