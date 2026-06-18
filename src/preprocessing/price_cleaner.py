"""Consolida preços de múltiplas fontes e devolve o menor preço confiável.

This module intentionally does *not* compute a median. It aggregates candidates
from all sources, applies a light robust outlier filter, and then returns the
lowest trustworthy BRL price.
"""

from __future__ import annotations

from typing import Any, Optional

from src.pricing import resolve_price

SOURCE_PRIORITY = {
    "zoom": 0,
    "buscape": 0,
    "zoom_jacotei": 0,
    "shopee": 1,
    "mercadolivre": 1,
    "amazon_br": 2,
    "amazon": 2,
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


def clean_prices(
    *payloads: Any,
    require_direct_source: bool = True,
    min_price_brl: float = 35.0,
    single_source_floor: float = 80.0,
) -> Optional[float]:
    """Return the lowest trustworthy price in BRL.

    Parameters
    ----------
    payloads:
        Any nested mix of collector outputs, lists of floats, or dicts containing
        ``price_brl`` / ``source``.
    require_direct_source:
        When True, MSRP proxy entries are ignored if any direct market source is
        present.
    min_price_brl:
        Floor applied when 2+ independent sources agree on a price range.
        Defaults to R$35.
    single_source_floor:
        Stricter floor applied when only 1 source found a price.  A single
        low-price listing is likely an accessory or wrong product.
        Defaults to R$80.
    """

    resolution = resolve_price("unknown", *payloads, require_direct_source=require_direct_source)
    return resolution.get("price_brl_real") or resolution.get("price_brl_estimated")


def resolve_prices_for_headphone(
    headphone_name: str,
    *payloads: Any,
    require_direct_source: bool = True,
    query_used: Optional[str] = None,
    query_strategy: Optional[str] = None,
) -> dict[str, Any]:
    return resolve_price(
        headphone_name,
        *payloads,
        require_direct_source=require_direct_source,
        query_used=query_used,
        query_strategy=query_strategy,
    )


# Backward-compatible alias for older call sites.
def consolidate_prices(*payloads: Any, **kwargs) -> Optional[float]:
    return clean_prices(*payloads, **kwargs)
