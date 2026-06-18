from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np

from src.collectors.product_matcher import canonicalize_headphone_name, infer_variant_group


SOURCE_PRIORITY = {
    "mercadolivre_api": 0,
    "mercadolivre": 1,
    "zoom": 1,
    "buscape": 1,
    "zoom_jacotei": 1,
    "kabum": 1,
    "amazon_paapi": 1,
    "amazon_br": 2,
    "amazon": 2,
    "shopee": 3,
}

TTL_HOURS_BY_SOURCE_TYPE = {
    "official_api": 6,
    "structured_search": 24,
    "marketplace": 12,
    "estimated": 72,
    "unknown": 12,
}


def source_rank(source: str) -> int:
    source = (source or "").lower()
    for key, rank in SOURCE_PRIORITY.items():
        if key in source:
            return rank
    return 50


def source_type(source: str) -> str:
    source = (source or "").lower()
    if "api" in source or "paapi" in source:
        return "official_api"
    if any(key in source for key in ("zoom", "buscape", "kabum")):
        return "structured_search"
    if any(key in source for key in ("mercadolivre", "amazon", "shopee")):
        return "marketplace"
    return "unknown"


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_utc().isoformat()


def ttl_until_for(source_type_name: str) -> str:
    hours = TTL_HOURS_BY_SOURCE_TYPE.get(source_type_name, TTL_HOURS_BY_SOURCE_TYPE["unknown"])
    return (now_utc() + timedelta(hours=hours)).isoformat()


def is_cache_entry_valid(entry: dict[str, Any]) -> bool:
    ttl_until = str(entry.get("ttl_until") or "").strip()
    if not ttl_until:
        return False
    try:
        expires = datetime.fromisoformat(ttl_until)
    except Exception:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now_utc():
        return False
    health = str(entry.get("source_health", "unknown"))
    return health not in {"source_unreachable", "auth_failed"}


def _extract_price(candidate: Any) -> Optional[float]:
    if candidate is None:
        return None
    if isinstance(candidate, (int, float)):
        value = float(candidate)
        return value if value > 0 else None
    if isinstance(candidate, dict):
        for key in ("price_brl", "price", "value", "amount", "final_price"):
            if key in candidate:
                return _extract_price(candidate[key])
    return None


def normalize_candidates(payloads: list[Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            price = _extract_price(obj)
            if price is not None:
                item = dict(obj)
                item["price_brl"] = float(price)
                item.setdefault("source", "unknown")
                item.setdefault("source_type", source_type(str(item.get("source", ""))))
                item.setdefault("match_score", 0.0)
                item.setdefault("condition", "unknown")
                item.setdefault("retrieved_at", now_iso())
                item.setdefault("brand_conflict", False)
                item.setdefault("numeric_conflict", False)
                item.setdefault("variant_group", "base")
                candidates.append(item)
                return
            for value in obj.values():
                visit(value)
            return
        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                visit(item)

    for payload in payloads:
        visit(payload)
    return [c for c in candidates if c.get("price_brl") and float(c["price_brl"]) > 0]


def estimate_from_candidates(candidates: list[dict[str, Any]]) -> Optional[float]:
    plausible = [
        float(c["price_brl"])
        for c in candidates
        if not c.get("is_accessory")
        and not c.get("brand_conflict")
        and not c.get("numeric_conflict")
        and float(c.get("match_score", 0.0)) >= 0.35
        and str(c.get("condition", "unknown")) != "used"
    ]
    if not plausible:
        return None
    return round(float(np.median(np.asarray(plausible, dtype=float))), 2)


def _target_name_features(display_name: str, variant_group: str) -> dict[str, Any]:
    canonical = canonicalize_headphone_name(display_name)
    tokens = canonical.split()
    numeric_tokens = [token for token in tokens if any(ch.isdigit() for ch in token)]
    brand = tokens[0] if tokens else ""
    return {
        "canonical_name": canonical,
        "token_count": len(tokens),
        "numeric_tokens": numeric_tokens,
        "has_strong_numeric": bool(numeric_tokens),
        "has_confirmed_brand": bool(brand),
        "variant_group": variant_group,
        "is_short_commercial_name": len(tokens) <= 4,
    }


def _strong_match_threshold(candidate: dict[str, Any], variant_group: str) -> float:
    source_type_name = str(candidate.get("source_type", "unknown"))
    display_name = str(candidate.get("display_name") or candidate.get("canonical_name") or "")
    features = _target_name_features(display_name, variant_group)
    base = 0.55

    if source_type_name == "structured_search":
        base = 0.5
        if features["has_confirmed_brand"] and not candidate.get("brand_conflict"):
            base -= 0.03
        if features["is_short_commercial_name"]:
            base -= 0.03
        if features["has_strong_numeric"] and not candidate.get("numeric_conflict"):
            base -= 0.02
    elif source_type_name == "official_api":
        base = 0.5
    elif source_type_name == "marketplace":
        base = 0.58

    if features["token_count"] >= 6:
        base += 0.03
    elif features["token_count"] <= 3:
        base -= 0.02

    if variant_group != "base":
        base -= 0.03

    if candidate.get("brand_conflict") or candidate.get("numeric_conflict"):
        base += 0.15

    return max(0.35, min(0.8, base))


def summarize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "min_price_brl": None, "max_price_brl": None})
    for candidate in candidates:
        source = str(candidate.get("source", "unknown"))
        price = float(candidate["price_brl"])
        grouped[source]["count"] += 1
        grouped[source]["min_price_brl"] = price if grouped[source]["min_price_brl"] is None else min(grouped[source]["min_price_brl"], price)
        grouped[source]["max_price_brl"] = price if grouped[source]["max_price_brl"] is None else max(grouped[source]["max_price_brl"], price)
    return [
        {
            "source": source,
            "count": data["count"],
            "min_price_brl": data["min_price_brl"],
            "max_price_brl": data["max_price_brl"],
        }
        for source, data in sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0]))
    ][:5]


def build_audit_records(
    display_name: str,
    canonical_name: str,
    candidates: list[dict[str, Any]],
    *,
    real_price: Optional[float],
    estimated_price: Optional[float],
    price_source: Optional[str],
    price_confidence: str,
    query_strategy: Optional[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    accessory_discards = sum(1 for c in candidates if c.get("is_accessory"))
    variant_discards = sum(1 for c in candidates if c.get("variant_conflict"))
    if accessory_discards >= 2:
        records.append({
            "display_name": display_name,
            "canonical_name": canonical_name,
            "price_brl_real": real_price,
            "price_brl_estimated": estimated_price,
            "price_source": price_source,
            "price_confidence": price_confidence,
            "query_strategy": query_strategy,
            "audit_reason": "many_accessory_discards",
        })
    if variant_discards >= 2:
        records.append({
            "display_name": display_name,
            "canonical_name": canonical_name,
            "price_brl_real": real_price,
            "price_brl_estimated": estimated_price,
            "price_source": price_source,
            "price_confidence": price_confidence,
            "query_strategy": query_strategy,
            "audit_reason": "many_variant_conflicts",
        })
    plausible = [float(c["price_brl"]) for c in candidates if not c.get("is_accessory") and float(c.get("match_score", 0.0)) >= 0.55]
    if real_price is not None and plausible:
        median = float(np.median(np.asarray(plausible, dtype=float)))
        if real_price < median * 0.6:
            records.append({
                "display_name": display_name,
                "canonical_name": canonical_name,
                "price_brl_real": real_price,
                "price_brl_estimated": estimated_price,
                "price_source": price_source,
                "price_confidence": price_confidence,
                "query_strategy": query_strategy,
                "audit_reason": "real_price_far_below_candidate_median",
            })
    if estimated_price is not None and real_price is None and any(float(c.get("match_score", 0.0)) >= 0.55 for c in candidates):
        records.append({
            "display_name": display_name,
            "canonical_name": canonical_name,
            "price_brl_real": real_price,
            "price_brl_estimated": estimated_price,
            "price_source": price_source,
            "price_confidence": price_confidence,
            "query_strategy": query_strategy,
            "audit_reason": "estimated_after_strong_candidate_conflict",
        })
    return records


def resolve_price(
    display_name: str,
    *payloads: Any,
    require_direct_source: bool = True,
    query_used: Optional[str] = None,
    query_strategy: Optional[str] = None,
) -> dict[str, Any]:
    candidates = normalize_candidates(list(payloads))
    canonical_name = canonicalize_headphone_name(display_name)
    variant_group = infer_variant_group(display_name)
    empty_base = {
        "display_name": display_name,
        "canonical_name": canonical_name,
        "price_brl_real": None,
        "price_brl_estimated": None,
        "price_confidence": "missing",
        "price_source": None,
        "price_source_type": None,
        "price_match_score": 0.0,
        "candidates_summary": [],
        "updated_at": now_iso(),
        "ttl_until": ttl_until_for("estimated"),
        "source_health": "missing_price",
        "failure_reason": "no_candidates",
        "last_success_source": None,
        "last_success_price": None,
        "query_used": query_used,
        "query_strategy": query_strategy,
        "audit_records": [],
        "brand_median_price": None,
    }
    if not candidates:
        return empty_base

    pool = [
        c for c in candidates
        if not c.get("is_accessory")
        and not c.get("variant_conflict")
        and not c.get("brand_conflict")
        and not c.get("numeric_conflict")
        and str(c.get("condition", "unknown")) != "used"
    ]
    if require_direct_source:
        direct = [c for c in pool if source_rank(str(c.get("source", ""))) < 99]
        if direct:
            pool = direct

    strong = [c for c in pool if float(c.get("match_score", 0.0)) >= _strong_match_threshold(c, variant_group)]
    strong.sort(key=lambda c: (source_rank(str(c.get("source", ""))), -float(c.get("match_score", 0.0)), float(c.get("price_brl", 0.0))))
    if len(strong) >= 4:
        values = np.asarray([float(c["price_brl"]) for c in strong], dtype=float)
        q1, q3 = np.percentile(values, [25, 75])
        iqr = float(q3 - q1)
        lower = max(0.0, float(q1 - 1.5 * iqr))
        upper = float(q3 + 1.5 * iqr)
        strong = [c for c in strong if lower <= float(c["price_brl"]) <= upper]

    real = None
    estimated = None
    confidence = "estimated_low"
    best = None
    failure_reason = None
    source_health = "healthy"
    if strong:
        best = strong[0]
        unique_sources = len({str(c.get("source", "")) for c in strong})
        floor = 80.0 if unique_sources < 2 else 35.0
        if float(best["price_brl"]) >= floor:
            real = round(float(best["price_brl"]), 2)
            confidence = "real_high" if source_rank(str(best.get("source", ""))) <= 1 and float(best.get("match_score", 0.0)) >= 0.8 else "real_medium"
        else:
            failure_reason = "strong_candidates_below_floor"
    else:
        failure_reason = "no_strong_candidates"

    if real is None:
        estimated = estimate_from_candidates(pool) or estimate_from_candidates(candidates)
        source_health = "missing_price" if estimated is None else "healthy"

    chosen_source_type = best.get("source_type") if best and real is not None else ("estimated" if estimated is not None else None)
    ttl_type = chosen_source_type or "estimated"
    source_counter = Counter(str(c.get("source", "unknown")) for c in candidates)
    brand_prices = [float(c["price_brl"]) for c in pool]
    brand_median_price = round(float(np.median(np.asarray(brand_prices, dtype=float))), 2) if brand_prices else None
    audit_records = build_audit_records(
        display_name,
        canonical_name,
        candidates,
        real_price=real,
        estimated_price=estimated,
        price_source=best.get("source") if best and real is not None else None,
        price_confidence=confidence if real is not None or estimated is not None else "missing",
        query_strategy=query_strategy,
    )

    return {
        "display_name": display_name,
        "canonical_name": canonical_name,
        "price_brl_real": real,
        "price_brl_estimated": estimated,
        "price_confidence": confidence if real is not None or estimated is not None else "missing",
        "price_source": best.get("source") if best and real is not None else None,
        "price_source_type": chosen_source_type,
        "price_match_score": round(float(best.get("match_score", 0.0)), 3) if best and real is not None else 0.0,
        "candidates_summary": summarize_candidates(candidates),
        "updated_at": now_iso(),
        "ttl_until": ttl_until_for(ttl_type),
        "source_health": source_health,
        "failure_reason": failure_reason,
        "last_success_source": best.get("source") if best and real is not None else None,
        "last_success_price": real or estimated,
        "query_used": query_used,
        "query_strategy": query_strategy,
        "audit_records": audit_records,
        "brand_median_price": brand_median_price,
        "source_counts": dict(source_counter),
    }
