"""Shopee Brasil price collector.

Uses the public search endpoint when available and falls back gracefully to []
or None on request failures.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus

from .base import BaseCollector

SHOPEE_SEARCH_URL = "https://shopee.com.br/api/v4/search/search_items"


class ShopeeCollector(BaseCollector):
    source_name = "shopee"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        try:
            limit = int(kwargs.get("limit", 60))
        except Exception:
            limit = 60

        params = {
            "by": "relevancy",
            "keyword": name,
            "limit": max(1, min(limit, 100)),
            "newest": 0,
            "order": "desc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }

        data = self._get_json(SHOPEE_SEARCH_URL, params=params)
        if data is None:
            return None

        try:
            items = data.get("items", []) if isinstance(data, dict) else []
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for item in items:
            try:
                item_basic = item.get("item_basic", item) if isinstance(item, dict) else None
                if not isinstance(item_basic, dict):
                    continue
                title = self._pick_string(item_basic.get("name") or item_basic.get("item_name") or "") or ""
                price = self._extract_price(item_basic)
                if price is None or price <= 0:
                    continue
                results.append({
                    "price_brl": float(price),
                    "source": self.source_name,
                    "title": title,
                    "url": self._build_item_url(item_basic),
                })
            except Exception:
                continue
        return results

    @staticmethod
    def _pick_string(value: Any) -> Optional[str]:
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _extract_price(self, item_basic: dict[str, Any]) -> Optional[float]:
        for key in ("price_min", "price_before_discount", "price", "price_max", "price_median"):
            raw = item_basic.get(key)
            price = self._decode_shopee_price(raw)
            if price is not None:
                return price
        return None

    @staticmethod
    def _decode_shopee_price(raw: Any) -> Optional[float]:
        if raw is None:
            return None
        try:
            if isinstance(raw, str):
                cleaned = raw.strip().replace("R$", "").replace(".", "").replace(",", ".")
                m = re.search(r"\d+(?:\.\d+)?", cleaned)
                return float(m.group(0)) if m else None
            value = float(raw)
            if value <= 0:
                return None
            # Shopee often returns values in fixed-point minor units.
            if value > 100000:
                return value / 100000.0
            if value > 10000:
                return value / 1000.0
            if value > 1000:
                return value / 100.0
            return value
        except Exception:
            return None

    @staticmethod
    def _build_item_url(item_basic: dict[str, Any]) -> str:
        shopid = item_basic.get("shopid") or item_basic.get("shop_id") or ""
        itemid = item_basic.get("itemid") or item_basic.get("item_id") or ""
        if shopid and itemid:
            return f"https://shopee.com.br/product/{shopid}/{itemid}"
        return ""
