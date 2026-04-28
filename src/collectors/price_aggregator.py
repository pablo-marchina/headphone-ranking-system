"""JáCotei / Zoom price collector.

This collector prefers Zoom/JáCotei search pages and embedded JSON payloads.
There is no dependency on a private API: the implementation is intentionally
scraping-oriented and resilient to layout changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .base import BaseCollector

SEARCH_URLS = (
    "https://www.zoom.com.br/search?q={query}",
    "https://www.jacotei.com.br/busca?q={query}",
    "https://www.jacotei.com.br/search?q={query}",
)

PRICE_KEYS = (
    "price",
    "salePrice",
    "currentPrice",
    "finalPrice",
    "priceValue",
    "value",
    "spotPrice",
    "bestPrice",
    "amount",
)


@dataclass(frozen=True)
class PriceHit:
    price_brl: float
    source: str
    title: str = ""
    url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "price_brl": float(self.price_brl),
            "source": self.source,
            "title": self.title,
            "url": self.url,
        }


class ZoomJacoteiCollector(BaseCollector):
    source_name = "zoom_jacotei"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        try:
            max_items = int(kwargs.get("max_items", 20))
        except Exception:
            max_items = 20

        hits: list[dict[str, Any]] = []
        for template in SEARCH_URLS:
            url = template.format(query=quote_plus(name))
            html = self._get_text(url)
            if not html:
                continue
            hits.extend(self._parse_html(html, source=url, max_items=max_items))
            if hits:
                break

        return hits if hits else []

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def _parse_html(self, html: str, *, source: str, max_items: int) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            # 1) Structured data
            for script in soup.find_all("script", attrs={"type": re.compile(r"application/(ld\+json|json)", re.I)}):
                text = script.string or script.get_text(" ", strip=True)
                hits.extend(self._extract_prices_from_blob(text, source=source))
                if len(hits) >= max_items:
                    return hits[:max_items]

            # 2) Common product cards
            text_nodes = soup.get_text(" ", strip=True)
            hits.extend(self._extract_prices_from_blob(text_nodes, source=source))
            if hits:
                return hits[:max_items]
        except Exception:
            return []
        return hits[:max_items]

    def _extract_prices_from_blob(self, blob: str, *, source: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        if not blob:
            return hits

        # JSON fragments first.
        for match in re.finditer(r"\{.*?\}", blob, flags=re.DOTALL):
            text = match.group(0)
            try:
                data = json.loads(text)
            except Exception:
                continue
            hits.extend(self._walk_json_for_prices(data, source=source))

        # Generic currency patterns.
        for match in re.finditer(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:[\.,][0-9]{2})?)", blob):
            price = self._parse_brl_number(match.group(1))
            if price is not None:
                hits.append(PriceHit(price, self.source_name, url=source).as_dict())
        return hits

    def _walk_json_for_prices(self, payload: Any, *, source: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []

        def visit(obj: Any) -> None:
            if isinstance(obj, dict):
                # common price keys
                for key in PRICE_KEYS:
                    if key in obj:
                        price = self._parse_maybe_price(obj.get(key))
                        if price is not None:
                            title = self._pick_string(obj.get("title") or obj.get("name") or obj.get("productName") or "") or ""
                            hits.append(PriceHit(price, self.source_name, title=title, url=source).as_dict())
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, list):
                for item in obj:
                    visit(item)
            elif isinstance(obj, str):
                price = self._parse_brl_number(obj)
                if price is not None and "R$" in obj:
                    hits.append(PriceHit(price, self.source_name, url=source).as_dict())

        try:
            visit(payload)
        except Exception:
            return []
        return hits

    @staticmethod
    def _parse_maybe_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            number = float(value)
            # Some payloads use cents, others use fixed-point.
            if number > 100000:
                number = number / 100.0
            return number if number > 0 else None
        if isinstance(value, str):
            return ZoomJacoteiCollector._parse_brl_number(value)
        if isinstance(value, dict):
            for key in ("value", "amount", "price", "salePrice"):
                if key in value:
                    return ZoomJacoteiCollector._parse_maybe_price(value[key])
        return None

    @staticmethod
    def _parse_brl_number(text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.strip()
        cleaned = cleaned.replace("R$", "").replace("\xa0", " ").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not match:
            return None
        try:
            value = float(match.group(0))
            return value if value > 0 else None
        except Exception:
            return None

    @staticmethod
    def _pick_string(value: Any) -> Optional[str]:
        return value.strip() if isinstance(value, str) and value.strip() else None


# Backward-compatible functional helper.
def fetch_zoom_jacotei_prices_list(headphone_name: str, max_items: int = 20, debug: bool = False):
    collector = ZoomJacoteiCollector()
    try:
        result = collector.fetch(headphone_name, max_items=max_items)
        if debug:
            print(f"[Zoom/JáCotei] {headphone_name}: {len(result) if result else 0} hits")
        return result
    except Exception:
        return None
