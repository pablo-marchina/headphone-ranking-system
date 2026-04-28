"""Amazon Brasil price collector.

This is a resilient HTML scraper that extracts candidate prices from search
results and structured-data blocks.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .base import BaseCollector

AMAZON_SEARCH_URL = "https://www.amazon.com.br/s?k={query}"


class AmazonBrasilCollector(BaseCollector):
    source_name = "amazon_br"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        url = AMAZON_SEARCH_URL.format(query=quote_plus(name))
        html = self._get_text(url)
        if html is None:
            return None
        return self._parse_results(html, source=url)

    def _parse_results(self, html: str, *, source: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Structured data
            for script in soup.find_all("script", attrs={"type": re.compile(r"application/(ld\+json|json)", re.I)}):
                text = script.string or script.get_text(" ", strip=True)
                results.extend(self._extract_from_blob(text, source=source))

            # Search result cards
            for card in soup.select('div[data-component-type="s-search-result"]'):
                title = self._pick_string(
                    card.get("aria-label")
                    or self._text_or_empty(card.select_one("h2 a span"))
                    or self._text_or_empty(card.select_one("h2 span"))
                ) or ""
                price = self._extract_card_price(card)
                if price is None:
                    continue
                results.append({
                    "price_brl": float(price),
                    "source": self.source_name,
                    "title": title,
                    "url": source,
                })

            if results:
                return results

            # Fallback to regex over the page text
            text = soup.get_text(" ", strip=True)
            results.extend(self._extract_from_blob(text, source=source))
        except Exception:
            return []
        return results

    def _extract_card_price(self, card) -> Optional[float]:
        for selector in (
            "span.a-price span.a-offscreen",
            "span.a-price-whole",
            ".a-price .a-offscreen",
        ):
            node = card.select_one(selector)
            if node:
                price = self._parse_brl_text(node.get_text(" ", strip=True))
                if price is not None:
                    return price
        return None

    def _extract_from_blob(self, blob: str, *, source: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not blob:
            return results

        for match in re.finditer(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})|[0-9]+(?:[\.,][0-9]{2})?)", blob):
            price = self._parse_brl_text(match.group(0))
            if price is not None:
                results.append({"price_brl": price, "source": self.source_name, "title": "", "url": source})

        # JSON blobs with offers
        for match in re.finditer(r"\{.*?\}", blob, flags=re.DOTALL):
            try:
                data = json.loads(match.group(0))
            except Exception:
                continue
            results.extend(self._walk_json(data, source=source))
        return results

    def _walk_json(self, payload: Any, *, source: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        def visit(obj: Any) -> None:
            if isinstance(obj, dict):
                if any(k in obj for k in ("price", "lowPrice", "highPrice", "offers", "priceSpecification")):
                    for key in ("price", "lowPrice", "highPrice"):
                        if key in obj:
                            price = self._parse_maybe_price(obj.get(key))
                            if price is not None:
                                results.append({"price_brl": price, "source": self.source_name, "title": "", "url": source})
                    if isinstance(obj.get("offers"), dict):
                        visit(obj["offers"])
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, list):
                for item in obj:
                    visit(item)
            elif isinstance(obj, str):
                price = self._parse_brl_text(obj)
                if price is not None and "R$" in obj:
                    results.append({"price_brl": price, "source": self.source_name, "title": "", "url": source})

        try:
            visit(payload)
        except Exception:
            return []
        return results

    @staticmethod
    def _parse_maybe_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            number = float(value)
            if number > 100000:
                number = number / 100.0
            return number if number > 0 else None
        if isinstance(value, str):
            return AmazonBrasilCollector._parse_brl_text(value)
        if isinstance(value, dict):
            for key in ("value", "amount", "price"):
                if key in value:
                    return AmazonBrasilCollector._parse_maybe_price(value[key])
        return None

    @staticmethod
    def _parse_brl_text(text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = text.strip().replace("R$", "").replace("\xa0", " ")
        cleaned = cleaned.replace(".", "").replace(",", ".")
        m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if not m:
            return None
        try:
            value = float(m.group(0))
            return value if value > 0 else None
        except Exception:
            return None

    @staticmethod
    def _text_or_empty(node: Any) -> str:
        try:
            return node.get_text(" ", strip=True) if node else ""
        except Exception:
            return ""

    @staticmethod
    def _pick_string(value: Any) -> Optional[str]:
        return value.strip() if isinstance(value, str) and value.strip() else None
