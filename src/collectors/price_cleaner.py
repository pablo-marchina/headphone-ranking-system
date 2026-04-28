"""Consolida preços de múltiplas fontes e devolve o menor preço confiável.

This module intentionally does *not* compute a median. It aggregates candidates
from all sources, applies a light robust outlier filter, and then returns the
lowest trustworthy BRL price.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional

import numpy as np

SOURCE_PRIORITY = {
    "zoom": 0,
    "jacotei": 0,
    "zoom_jacotei": 0,
    "shopee": 1,
    "mercadolivre": 1,
    "amazon_br": 2,
    "amazon": 2,
    "msrp_proxy": 99,
}


def _source_rank(source: str) -> int:
    source = (source or "").lower()
    for key, rank in SOURCE_PRIORITY.items():
        if key in source:
            return rank
    return 50


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
    if isinstance(candidate, (list, tuple)):
        for item in candidate:
            price = _extract_price(item)
            if price is not None:
                return price
    try:
        value = float(str(candidate).strip())
        return value if value > 0 else None
    except Exception:
        return None


def _extract_source(candidate: Any) -> str:
    if isinstance(candidate, dict):
        for key in ("source", "collector", "vendor"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "unknown"


def _normalize_inputs(payload: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            price = _extract_price(obj)
            if price is not None:
                items.append({"price_brl": price, "source": _extract_source(obj)})
                return
            for value in obj.values():
                visit(value)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                visit(item)
        else:
            price = _extract_price(obj)
            if price is not None:
                items.append({"price_brl": price, "source": "unknown"})

    visit(payload)
    return items


def clean_prices(*payloads: Any, require_direct_source: bool = True) -> Optional[float]:
    """Return the lowest trustworthy price in BRL.

    Parameters
    ----------
    payloads:
        Any nested mix of collector outputs, lists of floats, or dicts containing
        ``price_brl`` / ``source``.
    require_direct_source:
        When True, MSRP proxy entries are ignored if any direct market source is
        present.
    """

    candidates: list[dict[str, Any]] = []
    for payload in payloads:
        candidates.extend(_normalize_inputs(payload))

    candidates = [c for c in candidates if c.get("price_brl") is not None and float(c["price_brl"]) > 0]
    if not candidates:
        return None

    direct = [c for c in candidates if _source_rank(str(c.get("source", ""))) < 99]
    pool = direct if (require_direct_source and direct) else candidates

    values = np.asarray([float(c["price_brl"]) for c in pool], dtype=float)
    if values.size == 0:
        return None

    if values.size >= 4:
        q1, q3 = np.percentile(values, [25, 75])
        iqr = float(q3 - q1)
        lower = max(0.0, float(q1 - 1.5 * iqr))
        upper = float(q3 + 1.5 * iqr)
        filtered = [c for c in pool if lower <= float(c["price_brl"]) <= upper]
        if filtered:
            pool = filtered

    pool.sort(key=lambda c: (_source_rank(str(c.get("source", ""))), float(c["price_brl"])))
    return float(pool[0]["price_brl"])


# Backward-compatible alias for older call sites.
def consolidate_prices(*payloads: Any, **kwargs) -> Optional[float]:
    return clean_prices(*payloads, **kwargs)
