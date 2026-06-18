"""Shopee Brasil price collector.

Tries multiple approaches:
1. HTML search page (shopee.com.br/search?keyword=...)
2. Legacy API endpoint (shopee.com.br/api/v4/search/search_items)

All failures are logged and silently caught.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import quote_plus

from .base import BaseCollector

log = logging.getLogger(__name__)

SHOPEE_SEARCH_URL = "https://shopee.com.br/api/v4/search/search_items"
SHOPEE_HTML_URL = "https://shopee.com.br/search?keyword={query}"


class ShopeeCollector(BaseCollector):
    source_name = "shopee"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        max_results = int(kwargs.get("limit", 60)) if "limit" in kwargs else 60

        # Approach 1: try the HTML search page first
        results = self._fetch_html(name, max_results)
        if results:
            log.debug("[shopee] %s: %d hits from HTML", name, len(results))
            return results

        # Approach 2: fallback to API
        results = self._fetch_api(name, max_results)
        if results:
            log.debug("[shopee] %s: %d hits from API", name, len(results))
            return results

        log.debug("[shopee] %s: no results from any method", name)
        return None

    def _fetch_html(self, name: str, limit: int) -> Optional[list[dict[str, Any]]]:
        url = SHOPEE_HTML_URL.format(query=quote_plus(name))
        html = self._get_text(url)
        if not html:
            return None

        results: list[dict[str, Any]] = []
        try:
            # Try to find embedded JSON data in the page
            # Look for product data in __NEXT_DATA__ or __INITIAL_STATE__
            markers = ("__NEXT_DATA__", "__INITIAL_STATE__")
            for marker in markers:
                idx = html.find(marker)
                if idx == -1:
                    continue
                try:
                    start = html.index("{", idx)
                    depth = 0
                    for i, ch in enumerate(html[start:], start):
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if depth == 0:
                                blob = html[start:i+1]
                                data = json.loads(blob.replace("undefined", "null"))
                                results.extend(self._walk_state(data, name))
                                break
                except (ValueError, json.JSONDecodeError):
                    continue
                if results:
                    break

            # Fallback: regex for BRL prices in raw HTML
            if not results:
                for m in re.finditer(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:[\.,][0-9]{2})?)", html):
                    price = self._parse_brl_text(m.group(0))
                    if price and 10 < price < 50000:
                        results.append(self.build_price_candidate(name, price_brl=price, title="", url="", source_type="marketplace"))
                        if len(results) >= limit:
                            break

        except Exception as exc:
            log.debug("[shopee] HTML parse error for '%s': %s", name, exc)
            return []

        return results[:limit] if results else None

    def _walk_state(self, data: Any, name: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        def _walk(obj):
            if isinstance(obj, dict):
                for key in ("price", "price_min", "price_max"):
                    if key in obj:
                        val = obj[key]
                        if isinstance(val, (int, float)) and val > 0:
                            price = self._decode_shopee_price(val)
                            if price and 10 < price < 50000:
                                title = str(obj.get("name", obj.get("title", "")))
                                results.append(self.build_price_candidate(name, price_brl=price, title=title, url="", source_type="marketplace"))
                for v in obj.values():
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)
        try:
            _walk(data)
        except Exception:
            pass
        return results

    @staticmethod
    def _parse_brl_text(text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.strip().replace("R$", "").replace("\xa0", " ")
        cleaned = cleaned.replace(".", "").replace(",", ".")
        m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        return float(m.group(0)) if m and float(m.group(0)) > 0 else None

    def _fetch_api(self, name: str, limit: int) -> Optional[list[dict[str, Any]]]:
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
                results.append(self.build_price_candidate(
                    name,
                    price_brl=float(price),
                    title=title,
                    url=self._build_item_url(item_basic),
                    source_type="marketplace",
                ))
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
