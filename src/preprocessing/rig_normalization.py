
"""Cross-rig normalization helpers.

The goal is to estimate a systematic dB offset between measurement rigs
(e.g. oratory1990 vs Crinacle) from headphones measured on both rigs.
This module is deliberately data-driven and does not assume a single fixed
correction until the dataset provides it.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Optional

import numpy as np


def _normalize_rig_name(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _extract_curve(entry: Mapping[str, Any]):
    freqs = entry.get("freqs")
    mags = entry.get("mags")
    if mags is None:
        mags = entry.get("magnitudes")
    if mags is None:
        mags = entry.get("response")
    if freqs is None or mags is None:
        return None
    freqs = np.asarray(freqs, dtype=float)
    mags = np.asarray(mags, dtype=float)
    if freqs.size != mags.size or freqs.size < 2:
        return None
    order = np.argsort(freqs)
    return freqs[order], mags[order]


def estimate_rig_offset(common_headphone_pairs: Iterable[Mapping[str, Any]], reference_rig: str = "oratory1990", comparison_rig: str = "crinacle", band: tuple[float, float] = (200.0, 2000.0)) -> Optional[float]:
    """Estimate a median dB offset between two rigs from common headphones.

    Each item in ``common_headphone_pairs`` should contain either:
        - keys matching the rig names directly, each with ``freqs``/``mags``
        - a ``sources`` list of dicts with ``source`` / ``reviewer`` fields
    """
    diffs: list[float] = []
    ref_key = _normalize_rig_name(reference_rig)
    cmp_key = _normalize_rig_name(comparison_rig)
    low, high = map(float, band)

    for item in common_headphone_pairs:
        ref_curve = None
        cmp_curve = None

        if isinstance(item, Mapping):
            if ref_key in item and cmp_key in item:
                ref_curve = _extract_curve(item[ref_key]) if isinstance(item[ref_key], Mapping) else None
                cmp_curve = _extract_curve(item[cmp_key]) if isinstance(item[cmp_key], Mapping) else None
            if (ref_curve is None or cmp_curve is None) and isinstance(item.get("sources"), list):
                for src in item["sources"]:
                    if not isinstance(src, Mapping):
                        continue
                    label = _normalize_rig_name(src.get("source") or src.get("reviewer") or src.get("rig"))
                    if ref_curve is None and ref_key in label:
                        ref_curve = _extract_curve(src)
                    if cmp_curve is None and cmp_key in label:
                        cmp_curve = _extract_curve(src)

        if ref_curve is None or cmp_curve is None:
            continue

        ref_freqs, ref_mags = ref_curve
        cmp_freqs, cmp_mags = cmp_curve

        grid = np.union1d(ref_freqs, cmp_freqs)
        grid = grid[(grid >= low) & (grid <= high)]
        if grid.size < 8:
            continue

        ref_interp = np.interp(grid, ref_freqs, ref_mags, left=ref_mags[0], right=ref_mags[-1])
        cmp_interp = np.interp(grid, cmp_freqs, cmp_mags, left=cmp_mags[0], right=cmp_mags[-1])
        diffs.append(float(np.median(ref_interp - cmp_interp)))

    if not diffs:
        return None
    return float(np.median(diffs))


def build_rig_offset_map(common_headphone_pairs: Iterable[Mapping[str, Any]], rigs: Iterable[str] = ("oratory1990", "crinacle")) -> dict[tuple[str, str], float]:
    """Build pairwise offsets for every ordered rig pair present in the data."""
    rigs = tuple(_normalize_rig_name(r) for r in rigs)
    offsets: dict[tuple[str, str], list[float]] = defaultdict(list)

    for item in common_headphone_pairs:
        if not isinstance(item, Mapping):
            continue
        source_map = {}
        if isinstance(item.get("sources"), list):
            for src in item["sources"]:
                if not isinstance(src, Mapping):
                    continue
                label = _normalize_rig_name(src.get("source") or src.get("reviewer") or src.get("rig"))
                curve = _extract_curve(src)
                if curve is not None:
                    source_map[label] = curve

        for ref in rigs:
            for cmp in rigs:
                if ref == cmp or ref not in source_map or cmp not in source_map:
                    continue
                ref_freqs, ref_mags = source_map[ref]
                cmp_freqs, cmp_mags = source_map[cmp]
                grid = np.union1d(ref_freqs, cmp_freqs)
                if grid.size < 8:
                    continue
                ref_interp = np.interp(grid, ref_freqs, ref_mags, left=ref_mags[0], right=ref_mags[-1])
                cmp_interp = np.interp(grid, cmp_freqs, cmp_mags, left=cmp_mags[0], right=cmp_mags[-1])
                offsets[(ref, cmp)].append(float(np.median(ref_interp - cmp_interp)))

    return {key: float(np.median(vals)) for key, vals in offsets.items() if vals}


def apply_rig_offset(magnitudes, offset_db: Optional[float] = None):
    if offset_db is None:
        return np.asarray(magnitudes, dtype=float)
    return np.asarray(magnitudes, dtype=float) + float(offset_db)
