"""
Dataset generator — two-pass pipeline orchestrator.

Pass 1 — Acoustic  (CPU + local I/O, parallelised with ThreadPoolExecutor)
    · Loads FR measurements from AutoEQ local clone + external collectors
      (Squig.link, InnerFidelity, Headphones.com, ASR, independent reviewers)
    · Fetches RTINGS metrics (THD+N, IMD, sensitivity, impedance)
    · Runs the full perceptual model (ERB/loudness, alignment, scoring)
    · Saves results to  data/acoustic_cache.json
    · Skipped automatically when cache exists; use --force-acoustic to redo.

Pass 2 — Price + Score  (network I/O, parallelised with ThreadPoolExecutor)
    · Fetches prices from all configured sources
      (Zoom, Buscapé, Shopee, Mercado Livre API, Amazon BR)
    · Consolidates via clean_prices() — lowest trustworthy BRL price wins
    · Applies score formula, ranks, writes  output/ranking.csv

Structured per-fone logs go to  output/run_log.jsonl.

Usage
-----
    python dataset_generator.py               # full run
    python dataset_generator.py --limit 20   # smoke-test first 20 fones
    python dataset_generator.py --force-acoustic  # redo Pass 1 even if cached
    python dataset_generator.py --pass2-only      # skip Pass 1 entirely
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from src.env_loader import load_local_env
from pipeline import run_evaluation_pipeline
from src.collectors.autoeq import fetch_autoeq_data, LOCAL_REPO
from src.collectors.targets import get_harman_target
from src.collectors.rtings import fetch_rtings_metrics
from src.preprocessing.price_cleaner import resolve_prices_for_headphone
from src.collectors.product_matcher import (
    canonicalize_headphone_name,
    commercial_search_name,
    model_core_search_name,
    normalize_text,
    ultra_commercial_search_name,
)
from src.scoring.final_score import rank_scores, calculate_score
from src.scoring.confidence import calculate_score_confidence_interval
from src.pricing import is_cache_entry_valid

load_local_env()

# External acoustic collectors (best-effort — skip if unavailable)
try:
    from src.collectors.squig import SquigCollector
    _SQUIG = SquigCollector()
except Exception:
    _SQUIG = None

try:
    from src.collectors.innerfidelity import InnerFidelityCollector
    _INNERFIDELITY = InnerFidelityCollector()
except Exception:
    _INNERFIDELITY = None

try:
    from src.collectors.headphonescom import HeadphonesComCollector
    _HEADPHONESCOM = HeadphonesComCollector()
except Exception:
    _HEADPHONESCOM = None

try:
    from src.collectors.asr import ASRCollector
    _ASR = ASRCollector()
except Exception:
    _ASR = None

try:
    from src.collectors.independent_reviewers import IndependentReviewersCollector
    _INDEPENDENT = IndependentReviewersCollector()
except Exception:
    _INDEPENDENT = None

# External price collectors
try:
    from src.collectors.kabum import KabumPriceCollector
    _KABUM = KabumPriceCollector()
except Exception:
    _KABUM = None

try:
    from src.collectors.shopee import ShopeeCollector
    _SHOPEE = ShopeeCollector()
except Exception:
    _SHOPEE = None

try:
    from src.collectors.amazon import AmazonBrasilCollector
    _AMAZON = AmazonBrasilCollector()
except Exception:
    _AMAZON = None

try:
    from src.collectors.price_aggregator import ZoomJacoteiCollector
    _ZOOM = ZoomJacoteiCollector()
except Exception:
    _ZOOM = None

try:
    from src.collectors.mercadolivre import MercadoLivrePriceCollector
    _MERCADOLIVRE = MercadoLivrePriceCollector()
except Exception:
    _MERCADOLIVRE = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LIBRARY_PATH       = Path("data/headphone_library.json")
MAPPING_PATH       = Path("data/name_mapping.json")
ACOUSTIC_CACHE     = Path("data/acoustic_cache.json")
PRICE_CACHE_PATH   = Path("data/price_cache.json")
OUTPUT_CSV         = Path("output/ranking.csv")
PRICE_AUDIT_CSV    = Path("output/price_audit.csv")
PARTIAL_CSV        = Path("output/ranking_partial.csv")
RUN_LOG            = Path("output/run_log.jsonl")
CHECKPOINT_EVERY   = 50
LOCAL_MODE         = os.path.isdir(LOCAL_REPO)
_PRICE_CACHE_LOCK  = threading.Lock()   # guards shared price_cache dict in Pass 2


# ---------------------------------------------------------------------------
# RTINGS slug validation
# ---------------------------------------------------------------------------

def _slug_is_plausible(name: str, slug: str) -> bool:
    """
    Return False when the slug model part shares no meaningful tokens with the
    headphone name — indicating a wrong fuzzy match (e.g. 'truthear/hexa' for
    'Truthear Gate').

    Strategy: tokenise the model portion of the slug and the headphone name,
    then require ≥ 40 % token overlap.  This catches clear mismatches while
    accepting slugs where abbreviations or minor spelling variations exist.
    """
    if not slug:
        return False
    import re as _re
    model_part  = slug.split("/")[-1].replace("-", " ")
    name_clean  = _re.sub(r"[^a-z0-9 ]", " ", name.lower())
    model_clean = _re.sub(r"[^a-z0-9 ]", " ", model_part.lower())
    name_tokens  = {t for t in name_clean.split()  if len(t) >= 2}
    model_tokens = {t for t in model_clean.split() if len(t) >= 2}
    if not model_tokens:
        return True   # no tokens to compare — assume ok
    overlap = name_tokens & model_tokens
    return len(overlap) / len(model_tokens) >= 0.40

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first, then atomically rename to prevent corruption
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    # Validate that the written JSON can be read back
    with tmp.open("r", encoding="utf-8") as f:
        json.load(f)
    tmp.replace(path)

def _append_log(record: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def _load_mapping() -> dict:
    data = _load_json(MAPPING_PATH) or {}
    if isinstance(data, list):
        return {item["autoeq_name"]: item.get("rtings_slug") for item in data}
    return data if isinstance(data, dict) else {}

def _resolve_category(item: dict) -> str:
    cat = item.get("category")
    if cat in ("in-ear", "over-ear", "on-ear"):
        return cat
    from src.collectors.targets import detect_category
    return detect_category(item["name"])

def _write_csv(results: list, path: Path) -> int:
    ranked = rank_scores(list(results))
    cols = [
        "rank", "name", "category", "score", "percentile",
        "e_total", "e_fr", "e_thd", "e_match",
        "e_unc", "w_conf", "price_brl", "canonical_name",
        "price_brl_real", "price_brl_estimated", "price_confidence",
        "price_source", "price_source_type", "price_match_score", "updated_at",
        "score_lower_95", "score_upper_95",
        "n_sources", "thd_available", "match_available",
        "peakiness", "impedance_interaction",
    ]
    df = pd.DataFrame(ranked)
    df = df[[c for c in cols if c in df.columns]]
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(ranked)


def _write_price_audit(records: list[dict], path: Path) -> int:
    if not records:
        if path.exists():
            path.unlink()
        return 0
    cols = [
        "display_name", "canonical_name", "price_brl_real", "price_brl_estimated",
        "price_source", "price_confidence", "query_strategy", "audit_reason",
    ]
    df = pd.DataFrame(records)
    df = df[[c for c in cols if c in df.columns]]
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return len(df)


# ---------------------------------------------------------------------------
# IEC711 coupler correction  (fix #7)
# ---------------------------------------------------------------------------
# Fixed frequency-dependent correction (dB) that maps IEC711 measurements
# to the B&K 5128 reference standard.  Based on published coupler comparison
# data (Crinacle 2022, Harman 2019 supplement).
# Below 8 kHz the difference is negligible (<0.5 dB); above 8 kHz the IEC711
# exhibits a systematic resonance that inflates measured SPL by up to ~12 dB.
_IEC711_CORR_FREQS = np.array(
    [20, 1000, 6000, 8000, 9000, 10000, 11000, 12000, 14000, 16000, 20000],
    dtype=float,
)
_IEC711_CORR_DB = np.array(
    [0.0, 0.0, 0.0, -1.5, -3.5, -5.5, -8.0, -10.5, -11.5, -10.0, -8.0],
    dtype=float,
)

# Reviewer/path patterns that reliably indicate IEC711 rig
_IEC711_PATTERNS = ("iec711", "iec 711", "ears-711", "ears711", "711 coupler")


def _is_iec711(source: dict) -> bool:
    """Return True when the source is known to be measured on an IEC711 coupler."""
    for field in ("rig", "measurement_rig", "reviewer", "path_prefix"):
        val = str(source.get(field) or "").lower()
        if any(p in val for p in _IEC711_PATTERNS):
            return True
    return False


def _apply_iec711_correction(source: dict) -> dict:
    """
    Apply the fixed IEC711→B&K5128 correction to one measurement dict.
    Returns a corrected shallow copy; never mutates the original.
    No-op when the source is not tagged as IEC711.
    """
    if not _is_iec711(source):
        return source

    freqs = source.get("freqs")
    # Support the three magnitude key variants used across collectors
    mag_key = next(
        (k for k in ("mags", "magnitudes", "response") if source.get(k) is not None),
        None,
    )
    if freqs is None or mag_key is None:
        return source

    freqs_arr = np.asarray(freqs, dtype=float)
    mags_arr  = np.asarray(source[mag_key], dtype=float)
    correction = np.interp(
        freqs_arr,
        _IEC711_CORR_FREQS,
        _IEC711_CORR_DB,
        left=0.0,
        right=float(_IEC711_CORR_DB[-1]),
    )
    corrected = dict(source)
    corrected[mag_key]            = (mags_arr + correction).tolist()
    corrected["_iec711_corrected"] = True
    return corrected


# ---------------------------------------------------------------------------
# IEC711 deduplication  (Crinacle B&K + IEC711 same measurement twice)
# ---------------------------------------------------------------------------
_IEC711_SUFFIX_RE = re.compile(
    r"\s*(ears-?711|iec\s*711|711\s*coupler|iec711)\s*$", re.IGNORECASE
)


def _reviewer_base(source: dict) -> str:
    """Strip IEC711 rig suffixes from reviewer name for grouping."""
    reviewer = str(source.get("reviewer", "") or "")
    return _IEC711_SUFFIX_RE.sub("", reviewer).strip().lower()


def _dedup_iec711_sources(sources: list[dict]) -> list[dict]:
    """
    Drop IEC711-corrected duplicates when a native B&K measurement from the
    same reviewer already exists.

    After _apply_iec711_correction() both measurements are nearly identical
    in signal, but without deduplication they count as two independent sources,
    artificially inflating n_sources and w_conf.
    """
    if not sources:
        return sources

    from collections import defaultdict
    by_reviewer: dict[str, list[dict]] = defaultdict(list)
    for s in sources:
        by_reviewer[_reviewer_base(s)].append(s)

    deduped: list[dict] = []
    for base, group in by_reviewer.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        native    = [s for s in group if not s.get("_iec711_corrected")]
        corrected = [s for s in group if s.get("_iec711_corrected")]

        if native and corrected:
            # Prefer native B&K; discard the corrected IEC711 duplicate
            deduped.extend(native)
            log.debug(
                "  [dedup] dropped %d IEC711 duplicate(s) for reviewer '%s'",
                len(corrected), base,
            )
        else:
            deduped.extend(group)

    return deduped


# ---------------------------------------------------------------------------
# Acoustic source collection
# ---------------------------------------------------------------------------

def _collect_acoustic_sources(name: str, library_entry: dict) -> list[dict]:
    """
    Gather all available FR measurements for one headphone.

    Priority:
      1. AutoEQ local clone    — one entry per source in library_entry['sources']
      2. Squig.link            — external, best-effort
      3. InnerFidelity         — external, best-effort
      4. Headphones.com        — external, best-effort
      5. ASR                   — external, best-effort
      6. Independent reviewers — external, best-effort

    IEC711 correction is applied to every source before returning,
    normalising measurements to the B&K 5128 reference standard.
    """
    all_sources: list[dict] = []

    # 1. AutoEQ local (supports multiple sources per headphone)
    sources_meta = library_entry.get("sources", [])
    if sources_meta:
        for src_meta in sources_meta:
            entry_copy = dict(library_entry)
            entry_copy.update(src_meta)
            fetched = fetch_autoeq_data(name, library_entry=entry_copy)
            all_sources.extend(_apply_iec711_correction(s) for s in fetched)
    else:
        # Legacy single-source format
        fetched = fetch_autoeq_data(name, library_entry=library_entry)
        all_sources.extend(_apply_iec711_correction(s) for s in fetched)

    # 2–6. External collectors (best-effort, never crash the pipeline)
    for collector, label in [
        (_SQUIG,         "squig.link"),
        (_INNERFIDELITY, "innerfidelity"),
        (_HEADPHONESCOM, "headphones.com"),
        (_ASR,           "asr"),
        (_INDEPENDENT,   "independent_reviewers"),
    ]:
        if collector is None:
            continue
        try:
            fetched = collector.fetch(name)
            if fetched:
                corrected = [_apply_iec711_correction(s) for s in fetched]
                all_sources.extend(corrected)
                log.debug("  [%s] +%d sources for '%s'", label, len(corrected), name)
        except Exception as exc:
            log.debug("  [%s] skipped for '%s': %s", label, name, exc)

    return _dedup_iec711_sources(all_sources)


# ---------------------------------------------------------------------------
# Pass 1 — Acoustic worker
# ---------------------------------------------------------------------------

def _acoustic_worker(item: dict, name_map: dict) -> dict:
    """
    Process one headphone acoustically. Returns a result dict or an error dict.
    Runs in a thread pool — must be exception-safe.
    """
    name     = item["name"]
    slug     = name_map.get(name) or ""
    # Reject slugs that don't match the headphone name (wrong fuzzy matches)
    if slug and not _slug_is_plausible(name, slug):
        log.debug("  [rtings] slug '%s' rejected for '%s'", slug, name)
        slug = ""
    category = _resolve_category(item)
    t_start  = time.time()

    try:
        sources = _collect_acoustic_sources(name, item)
        if not sources:
            return {"name": name, "status": "no_acoustic_data"}

        t_f, t_m = get_harman_target(category)
        rtings   = fetch_rtings_metrics(slug) if slug else None

        result = run_evaluation_pipeline(
            name          = name,
            sources_data  = sources,
            target_freqs  = t_f,
            target_mags   = t_m,
            thd_data      = None,   # THD handled via rtings_metrics
            price         = None,   # price resolved in Pass 2
            rtings_metrics = rtings,
        )

        if result is None:
            return {"name": name, "status": "pipeline_returned_none"}

        result["category"] = category
        result["status"]   = "ok"
        result["_slug"]    = slug
        result["elapsed"]  = round(time.time() - t_start, 2)
        return result

    except Exception as exc:
        log.warning("  [Pass1] error for '%s': %s", name, exc)
        return {"name": name, "status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Pass 1 — Acoustic orchestration
# ---------------------------------------------------------------------------

def run_pass1(library: list, name_map: dict, limit: Optional[int],
              workers: int = 6, retry_errors: bool = False) -> list[dict]:
    """
    Run the acoustic pipeline in parallel.

    Normal mode: automatically resumes from an existing partial cache.
    retry_errors=True: re-processes only entries whose status != 'ok',
      replacing their cache entries with fresh results.
    Returns the full result list (cached + newly processed).
    """
    to_process = library[:limit] if limit else library

    # ----- Retry-errors branch -----
    if retry_errors:
        existing_cache: list[dict] = _load_json(ACOUSTIC_CACHE) or []
        if not existing_cache:
            log.error("--retry-errors: no acoustic cache found. Run a full pass first.")
            return []

        failed_names = {r["name"] for r in existing_cache if r.get("status") != "ok"}
        if not failed_names:
            log.info("--retry-errors: no failed entries in cache — nothing to do.")
            return existing_cache

        library_by_name = {item["name"]: item for item in to_process}
        pending = [library_by_name[n] for n in failed_names if n in library_by_name]
        # Start from the successful entries; failed ones will be replaced
        results: list[dict] = [r for r in existing_cache if r.get("status") == "ok"]
        ok_count  = len(results)
        err_count = 0
        total_all = len(existing_cache)
        log.info("--retry-errors: retrying %d failed entries", len(pending))

    else:
        # ----- Resume logic -----
        existing_cache = _load_json(ACOUSTIC_CACHE) or []
        done_names: set[str] = {r["name"] for r in existing_cache}
        pending = [item for item in to_process if item["name"] not in done_names]

        if done_names:
            log.info(
                "Pass 1 — resuming: %d already cached, %d remaining",
                len(done_names), len(pending),
            )
        else:
            log.info("Pass 1 — Acoustic: %d fones, %d workers", len(pending), workers)

        if not pending:
            log.info("Pass 1 — nothing to do, all fones already cached.")
            return existing_cache

        results   = list(existing_cache)
        ok_count  = sum(1 for r in results if r.get("status") == "ok")
        err_count = len(results) - ok_count
        total_all = len(to_process)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_acoustic_worker, item, name_map): item
                   for item in pending}

        for i, future in enumerate(as_completed(futures), len(done_names) + 1):
            try:
                result = future.result()
            except Exception as exc:
                item   = futures[future]
                result = {"name": item["name"], "status": "future_error", "error": str(exc)}

            results.append(result)
            status = result.get("status", "?")

            if status == "ok":
                ok_count += 1
                log.info("[%d/%d] %-55s e_fr=%.3f w_conf=%.3f",
                         i, total_all, result["name"][:55],
                         result.get("e_fr", 0), result.get("w_conf", 0))
            else:
                err_count += 1
                log.info("[%d/%d] %-55s SKIP (%s)",
                         i, total_all, result["name"][:55], status)

            _append_log({"pass": 1, "idx": i, **result})

            # Periodic checkpoint
            if i % CHECKPOINT_EVERY == 0:
                _save_json(ACOUSTIC_CACHE, results)
                log.info("  [checkpoint] %d / %d saved", i, total_all)

    log.info("Pass 1 done: %d ok, %d skipped/error", ok_count, err_count)
    _save_json(ACOUSTIC_CACHE, results)
    return results


# ---------------------------------------------------------------------------
# Pass 2 — Price worker
# ---------------------------------------------------------------------------

def _read_cached_price_entry(price_cache: dict, canonical_name: str) -> Optional[dict]:
    entry = price_cache.get(canonical_name)
    if entry is None:
        return None
    if isinstance(entry, (int, float)):
        return {
            "display_name": canonical_name,
            "canonical_name": canonical_name,
            "price_brl_real": float(entry),
            "price_brl_estimated": None,
            "price_confidence": "real_medium",
            "price_source": "legacy_cache",
            "price_source_type": "unknown",
            "price_match_score": 0.0,
            "candidates_summary": [],
            "updated_at": None,
            "ttl_until": None,
            "source_health": "healthy",
            "failure_reason": None,
            "last_success_source": "legacy_cache",
            "last_success_price": float(entry),
            "query_used": None,
            "query_strategy": "legacy_cache",
            "audit_records": [],
        }
    if isinstance(entry, dict):
        return entry if is_cache_entry_valid(entry) else None
    return None


def _fetch_prices(name: str, slug: str, price_cache: dict) -> dict[str, Any]:
    """
    Fetch the lowest reliable BRL price for one headphone from all sources.
    Results are cached to avoid re-fetching on repeated runs.
    """
    canonical_name = canonicalize_headphone_name(name)
    with _PRICE_CACHE_LOCK:
        cached = _read_cached_price_entry(price_cache, canonical_name)
        if cached is not None:
            return cached

    all_price_data: list = []
    query_attempts: list[tuple[str, str, str]] = []
    for strategy, candidate_query in (
        ("original_query", name),
        ("commercial_query", commercial_search_name(name)),
        ("ultra_commercial_query", ultra_commercial_search_name(name)),
        ("model_core_query", model_core_search_name(name)),
    ):
        cleaned = " ".join(str(candidate_query or "").split()).strip()
        normalized = normalize_text(cleaned) if cleaned else ""
        if not cleaned or not normalized:
            continue
        if any(existing_normalized == normalized for _, _, existing_normalized in query_attempts):
            continue
        query_attempts.append((strategy, cleaned, normalized))

    winning_strategy: Optional[str] = None
    winning_query: Optional[str] = None

    def _maybe_return_early(query: str, strategy: str) -> Optional[dict[str, Any]]:
        early = resolve_prices_for_headphone(
            name,
            all_price_data,
            require_direct_source=True,
            query_used=query,
            query_strategy=strategy,
        )
        if early.get("price_confidence") == "real_high":
            with _PRICE_CACHE_LOCK:
                price_cache[canonical_name] = early
            return early
        return None

    for strategy, query, _ in query_attempts:
        for collector, label in (
            (_ZOOM, "Zoom/Buscape"),
            (_KABUM, "Kabum"),
            (_SHOPEE, "Shopee"),
            (_MERCADOLIVRE, "Mercado Livre"),
            (_AMAZON, "Amazon"),
        ):
            if not collector:
                continue
            try:
                data = collector.fetch(query)
                if data:
                    winning_strategy = strategy
                    winning_query = query
                    all_price_data.extend(data)
                    log.debug("[precos] %s: %d hits from %s using strategy=%s query=%s", name, len(data), label, strategy, query)
                    early = _maybe_return_early(query, strategy)
                    if early is not None:
                        return early
            except Exception as exc:
                log.debug("[precos] %s: %s error with strategy=%s query=%s: %s", name, label, strategy, query, exc)

    resolution = resolve_prices_for_headphone(
        name,
        all_price_data,
        require_direct_source=True,
        query_used=winning_query,
        query_strategy=winning_strategy,
    )

    with _PRICE_CACHE_LOCK:
        price_cache[canonical_name] = resolution
    return resolution


def _score_worker(result: dict, price_cache: dict) -> dict:
    """Apply price and recalculate score for one cached acoustic result."""
    if result.get("status") != "ok":
        return result

    name  = result["name"]
    slug  = result.get("_slug", "")
    price_info = _fetch_prices(name, slug, price_cache)
    price_real = price_info.get("price_brl_real")
    price_estimated = price_info.get("price_brl_estimated")
    effective_price = price_real or price_estimated

    result["canonical_name"]  = price_info.get("canonical_name", canonicalize_headphone_name(name))
    result["price_brl"]       = effective_price
    result["price_brl_real"]  = price_real
    result["price_brl_estimated"] = price_estimated
    result["price_confidence"] = price_info.get("price_confidence")
    result["price_source"]     = price_info.get("price_source")
    result["price_source_type"] = price_info.get("price_source_type")
    result["price_match_score"] = price_info.get("price_match_score")
    result["updated_at"] = price_info.get("updated_at")
    result["query_used"] = price_info.get("query_used")
    result["query_strategy"] = price_info.get("query_strategy")
    result["source_health"] = price_info.get("source_health")
    result["failure_reason"] = price_info.get("failure_reason")
    result["audit_records"] = price_info.get("audit_records", [])

    if effective_price is None or effective_price <= 0:
        result["score"]     = None
        result["score_lower_95"] = None
        result["score_upper_95"] = None
        return result

    e_total           = result.get("e_total", 0.0)
    w_conf            = result.get("w_conf",  0.0)
    sensitivity_db_mw = result.get("sensitivity_db_mw")

    score = calculate_score(e_total, w_conf, effective_price,
                            sensitivity_db_mw=sensitivity_db_mw)

    ci = calculate_score_confidence_interval(
        e_total        = e_total,
        price          = effective_price,
        e_unc          = result.get("e_unc", 1.0),
        n_sources      = result.get("n_sources", 1),
        thd_available  = result.get("thd_available", False),
        match_available = result.get("match_available", False),
        sensitivity_db_mw = sensitivity_db_mw,
        headphone_name = name,
        n_boot         = 300,
        seed           = 42,
    ) if score is not None else None

    result["score"]          = round(float(score), 6) if score is not None else None
    result["score_lower_95"] = round(float(ci[0]), 6) if ci else None
    result["score_upper_95"] = round(float(ci[1]), 6) if ci else None
    return result


def _invalidate_clustered_prices(price_cache: dict,
                                  max_shared: int = 5,
                                  bucket_size: float = 0.50) -> tuple[dict, int]:
    """
    Remove prices shared by too many distinct headphone models.

    When price P (within ±R$0.25) appears for more than `max_shared` different
    models, it is almost certainly a generic product (accessory, cheapest brand
    entry) contaminating multiple searches, not the actual headphone price.

    Returns the cleaned cache and the number of invalidated entries.
    """
    from collections import defaultdict

    def bucket(price: float) -> float:
        return round(price / bucket_size) * bucket_size

    bucket_to_names: dict[float, set] = defaultdict(set)
    for name, entry in price_cache.items():
        price = entry if isinstance(entry, (int, float)) else (entry or {}).get("price_brl_real")
        if price and float(price) > 0:
            bucket_to_names[bucket(float(price))].add(name)

    contaminated = {b for b, names in bucket_to_names.items()
                    if len(names) > max_shared}

    if not contaminated:
        return price_cache, 0

    cleaned, n_invalidated = {}, 0
    for name, entry in price_cache.items():
        price = entry if isinstance(entry, (int, float)) else (entry or {}).get("price_brl_real")
        if price and float(price) > 0 and bucket(float(price)) in contaminated:
            cleaned[name] = None
            n_invalidated += 1
        else:
            cleaned[name] = entry

    return cleaned, n_invalidated


# ---------------------------------------------------------------------------
# Pass 2 — Price + Score orchestration
# ---------------------------------------------------------------------------

def run_pass2(acoustic_results: list, workers: int = 10,
              refresh_prices: bool = False) -> list[dict]:
    """
    Fetch prices in parallel and compute final scores.
    Returns enriched result list (acoustic + price + score).

    Parameters
    ----------
    refresh_prices:
        When True, ignore the on-disk price cache and re-fetch every
        headphone's price from scratch.
    """
    ok_results = [r for r in acoustic_results if r.get("status") == "ok"]
    total      = len(ok_results)
    log.info("Pass 2 — Price+Score: %d fones, %d workers", total, workers)

    price_cache = _load_json(PRICE_CACHE_PATH) or {}

    if refresh_prices:
        n = len(price_cache)
        price_cache = {}
        log.info("  --refresh-prices: invalidated %d cached entries", n)

    # Remove suspicious prices shared by too many different models
    # (e.g. R$84 appearing for HEDD HEDDphone + HIFIMAN Deva Pro).
    price_cache, n_invalidated = _invalidate_clustered_prices(price_cache)
    if n_invalidated:
        log.info("  clustered-price cleanup: invalidated %d entries", n_invalidated)
    scored: list[dict] = []
    audit_records: list[dict] = []
    query_strategy_counts: dict[str, int] = {}
    failure_reason_counts: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_score_worker, dict(r), price_cache): r
                   for r in ok_results}

        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
            except Exception as exc:
                orig   = futures[future]
                result = dict(orig)
                result["score"] = None
                log.warning("  [Pass2] price error for '%s': %s", orig.get("name"), exc)

            scored.append(result)
            audit_records.extend(result.get("audit_records", []) or [])
            strategy = result.get("query_strategy")
            if strategy:
                query_strategy_counts[str(strategy)] = query_strategy_counts.get(str(strategy), 0) + 1
            failure_reason = result.get("failure_reason")
            if failure_reason:
                failure_reason_counts[str(failure_reason)] = failure_reason_counts.get(str(failure_reason), 0) + 1
            score_str = f"{result['score']:.6f}" if result.get("score") else "N/A"
            price_str = f"R${result.get('price_brl', 0):.0f}" if result.get("price_brl") else "sem preço"
            log.info("[%d/%d] %-55s %s  %s",
                     i, total, result["name"][:55], price_str, score_str)

            _append_log({"pass": 2, "idx": i,
                         "name": result["name"],
                         "canonical_name": result.get("canonical_name"),
                         "price_brl": result.get("price_brl"),
                         "score": result.get("score"),
                         "price_confidence": result.get("price_confidence"),
                         "query_used": result.get("query_used"),
                         "query_strategy": result.get("query_strategy"),
                         "source_health": result.get("source_health"),
                         "failure_reason": result.get("failure_reason")})
            for audit in result.get("audit_records", []) or []:
                _append_log({
                    "pass": 2,
                    "event": "price_audit",
                    "audit_type": audit.get("audit_reason"),
                    "name": result["name"],
                    "canonical_name": result.get("canonical_name"),
                    "price_source": result.get("price_source"),
                    "price_confidence": result.get("price_confidence"),
                    "query_strategy": result.get("query_strategy"),
                })

            if i % CHECKPOINT_EVERY == 0:
                # Clean contaminated clusters before saving checkpoint
                cleaned_cache, n_ckpt = _invalidate_clustered_prices(price_cache)
                _save_json(PRICE_CACHE_PATH, cleaned_cache)
                if n_ckpt:
                    log.info("  [checkpoint cleanup] invalidated %d clustered", n_ckpt)
                _write_csv(scored, PARTIAL_CSV)
                log.info("  [checkpoint] %d / %d saved", i, total)

    # Remove contaminated prices before final save (catches clusters
    # produced by the current batch of parallel fetches).
    price_cache, n_cleaned = _invalidate_clustered_prices(price_cache)
    if n_cleaned:
        log.info("  post-fetch cleanup: invalidated %d clustered prices", n_cleaned)

    _save_json(PRICE_CACHE_PATH, price_cache)
    _write_price_audit(audit_records, PRICE_AUDIT_CSV)
    log.info(
        "Price summary: real_high=%d real_medium=%d estimated_low=%d missing=%d",
        sum(1 for r in scored if (r.get("price_confidence") or "missing") == "real_high"),
        sum(1 for r in scored if (r.get("price_confidence") or "missing") == "real_medium"),
        sum(1 for r in scored if (r.get("price_confidence") or "missing") == "estimated_low"),
        sum(1 for r in scored if (r.get("price_confidence") or "missing") == "missing"),
    )
    if query_strategy_counts:
        summary = " ".join(f"{key}={value}" for key, value in sorted(query_strategy_counts.items()))
        log.info("Query strategy summary: %s", summary)
    if failure_reason_counts:
        summary = " ".join(f"{key}={value}" for key, value in sorted(failure_reason_counts.items()))
        log.info("Failure reason summary: %s", summary)
    log.info("Pass 2 done: %d fones com score",
             sum(1 for r in scored if r.get("score") is not None))
    return scored


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def build_dataset(
    limit: Optional[int] = None,
    force_acoustic: bool  = False,
    pass2_only: bool      = False,
    retry_errors: bool    = False,
    refresh_prices: bool  = False,
    acoustic_workers: int = 6,
    price_workers: int    = 10,
) -> pd.DataFrame:

    # Clear run log for fresh run (not for targeted retries)
    if RUN_LOG.exists() and not pass2_only and not retry_errors:
        RUN_LOG.unlink()

    library = _load_json(LIBRARY_PATH)
    if not library:
        log.error("headphone_library.json not found. Run get_all_headphones.py first.")
        sys.exit(1)

    name_map = _load_mapping()
    mode     = "local" if LOCAL_MODE else "remote"
    log.info("Dataset: %d fones in library, mode=%s", len(library), mode)

    # ---- Pass 1 ----
    acoustic_results: list[dict] = []

    if pass2_only:
        log.info("--pass2-only: loading acoustic cache")
        cached = _load_json(ACOUSTIC_CACHE)
        if not cached:
            log.error("No acoustic cache found. Run without --pass2-only first.")
            sys.exit(1)
        acoustic_results = cached
    elif retry_errors:
        acoustic_results = run_pass1(library, name_map, limit,
                                     workers=acoustic_workers,
                                     retry_errors=True)
    elif not force_acoustic and ACOUSTIC_CACHE.exists():
        log.info("Acoustic cache found — skipping Pass 1 (use --force-acoustic to redo)")
        acoustic_results = _load_json(ACOUSTIC_CACHE) or []
    else:
        # force_acoustic=True: apaga o cache existente para garantir reprocessamento completo
        if ACOUSTIC_CACHE.exists():
            ACOUSTIC_CACHE.unlink()
            log.info("Acoustic cache deletado — reprocessando todos os fones")
        acoustic_results = run_pass1(library, name_map, limit,
                                     workers=acoustic_workers)

    # ---- Pass 2 ----
    scored_results = run_pass2(acoustic_results, workers=price_workers,
                               refresh_prices=refresh_prices)

    # ---- Final CSV ----
    n = _write_csv(scored_results, OUTPUT_CSV)
    log.info("Done: %d fones ranked → %s", n, OUTPUT_CSV)

    # Clean up partial file if full run completed
    if not limit and PARTIAL_CSV.exists():
        PARTIAL_CSV.unlink()

    return pd.read_csv(OUTPUT_CSV)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Headphone ranking pipeline")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N headphones (smoke-test)")
    p.add_argument("--force-acoustic", action="store_true",
                   help="Redo Pass 1 even if acoustic_cache.json exists")
    p.add_argument("--pass2-only", action="store_true",
                   help="Skip Pass 1, run Pass 2 from existing acoustic cache")
    p.add_argument("--retry-errors", action="store_true",
                   help="Re-process only failed entries in the existing acoustic cache")
    p.add_argument("--refresh-prices", action="store_true",
                   help="Ignore cached prices and re-fetch every headphone from all sources")
    p.add_argument("--acoustic-workers", type=int, default=6,
                   help="Thread pool size for Pass 1 (default: 6)")
    p.add_argument("--price-workers", type=int, default=10,
                   help="Thread pool size for Pass 2 (default: 10)")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    build_dataset(
        limit            = args.limit,
        force_acoustic   = args.force_acoustic,
        pass2_only       = args.pass2_only,
        retry_errors     = args.retry_errors,
        refresh_prices   = args.refresh_prices,
        acoustic_workers = args.acoustic_workers,
        price_workers    = args.price_workers,
    )
