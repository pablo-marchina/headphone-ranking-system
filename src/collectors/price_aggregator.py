"""Zoom / Buscapé price collector.

Collects prices from Zoom.com.br and Buscapé.com.br search pages using
embedded JSON-LD and structured data payloads.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .base import BaseCollector

log = logging.getLogger(__name__)

SEARCH_URLS = (
    "https://www.zoom.com.br/search?q={query}",
    "https://www.buscape.com.br/search?q={query}",
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


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _title_matches(title: str, headphone_name: str) -> bool:
    """Return True when a product title plausibly corresponds to the headphone.
    
    Matching rules:
      1. At least 50% of significant tokens (>= 3 chars) from the headphone name
         must appear in the product title.
      2. If the headphone name contains any numeric model identifier (a token with
         at least one digit), at least one such numeric token must appear in the
         title. This prevents matching unrelated products from the same brand
         (e.g. "Sennheiser HD 600" won't match "Sennheiser HD 25").
      3. Products whose title contains accessory-related keywords are rejected.
    """
    if not title:
        return False
    n_title = _normalize(title)
    n_name  = _normalize(headphone_name)
    tokens  = [t for t in n_name.split() if len(t) >= 3]
    if not tokens:
        return True

    # Reject accessories — these are products *for* the headphone, not the headphone itself.
    accessory_keywords = (
        "almofada", "earpad", "ear pad", "capa", "case", "bolsa", "estojo",
        "cabo", "carregador", "fonte", "adaptador", "suporte", "pelicula",
        "filtro", "protetor", "plug", "conector", "ponta", "espuma",
        "replacement", "reposicao", "peça", "peca", "acessorio", "acessório",
    )
    if any(kw in n_title for kw in accessory_keywords):
        return False

    matches     = sum(1 for t in tokens if t in n_title)
    threshold   = max(1, round(len(tokens) * 0.5))
    if matches < threshold:
        return False

    numeric_tokens = [t for t in tokens if re.search(r"\d", t)]
    if numeric_tokens:
        return any(t in n_title for t in numeric_tokens)

    return True


class ZoomJacoteiCollector(BaseCollector):
    source_name = "zoom_jacotei"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        try:
            max_items = int(kwargs.get("max_items", 40))
        except Exception:
            max_items = 40

        hits: list[dict[str, Any]] = []
        sources_tried = []
        for template in SEARCH_URLS:
            url  = template.format(query=quote_plus(name))
            sources_tried.append(url.split("/")[2])
            html = self._get_text(url)
            if not html:
                log.debug("[zoom] %s: empty response from %s", name, url)
                continue
            parsed = self._parse_html(html, source=url,
                                      max_items=max_items,
                                      headphone_name=name)
            if parsed:
                log.debug("[zoom] %s: %d hits from %s", name, len(parsed), url)
                hits.extend(parsed)
            else:
                log.debug("[zoom] %s: no prices parsed from %s", name, url)
            if hits:
                break

        log.debug("[zoom] %s: %d total hits from %s", name, len(hits), sources_tried)
        return hits if hits else []

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def _parse_html(self, html: str, *, source: str,
                    max_items: int, headphone_name: str = "") -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            # 1. Try __NEXT_DATA__ (Next.js apps — Zoom, Buscapé)
            nd_script = soup.find("script", id="__NEXT_DATA__")
            if nd_script and nd_script.string:
                try:
                    ndata = json.loads(nd_script.string.strip())
                    # Zoom stores product hits in initialReduxState.hits.hits
                    redux = ndata.get("props", {}).get("initialReduxState", {})
                    for key in ("hits", "products", "items"):
                        container = redux.get(key, {})
                        if isinstance(container, dict):
                            items_list = container.get("hits", container.get("items", []))
                        elif isinstance(container, list):
                            items_list = container
                        else:
                            continue
                        if isinstance(items_list, list):
                            for item in items_list:
                                if isinstance(item, dict):
                                    price = item.get("price") or item.get("priceValue") or item.get("salePrice")
                                    price = self._safe_float(price)
                                    if price is not None and price > 0:
                                        title = self._pick_string(item.get("name") or item.get("title") or "") or ""
                                        if not headphone_name or _title_matches(title, headphone_name):
                                            hits.append(self.build_price_candidate(
                                                headphone_name,
                                                price_brl=float(price),
                                                title=title,
                                                url=item.get("url", ""),
                                                source_type="structured_search",
                                            ))
                        if hits:
                            return hits[:max_items]

                    # Fallback: walk entire __NEXT_DATA__ for any price keys
                    nd_hits = self._walk_json_for_prices(ndata, source=source, headphone_name=headphone_name)
                    if headphone_name:
                        nd_hits = [h for h in nd_hits if _title_matches(h.get("title", ""), headphone_name)]
                    hits.extend(nd_hits)
                    if hits:
                        return hits[:max_items]
                except (json.JSONDecodeError, Exception):
                    pass

            # 2. Try JSON-LD / structured data scripts
            for script in soup.find_all(
                "script",
                attrs={"type": re.compile(r"application/(ld\+json|json)", re.I)},
            ):
                text = script.string or script.get_text(" ", strip=True)
                hits.extend(
                    self._extract_prices_from_blob(
                        text, source=source, headphone_name=headphone_name
                    )
                )
                if len(hits) >= max_items:
                    return hits[:max_items]
        except Exception:
            return []
        return hits[:max_items]

    def _extract_prices_from_blob(self, blob: str, *, source: str,
                                   headphone_name: str = "") -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        if not blob:
            return hits

        for match in re.finditer(r"\{.*?\}", blob, flags=re.DOTALL):
            text = match.group(0)
            try:
                data = json.loads(text)
            except Exception:
                continue
            for hit in self._walk_json_for_prices(data, source=source, headphone_name=headphone_name):
                # Only keep hits whose title matches the headphone being searched
                if not headphone_name or _title_matches(hit.get("title", ""), headphone_name):
                    hits.append(hit)

        return hits

    def _walk_json_for_prices(self, payload: Any, *, source: str, headphone_name: str = "") -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []

        def visit(obj: Any) -> None:
            if isinstance(obj, dict):
                # common price keys
                for key in PRICE_KEYS:
                    if key in obj:
                        price = self._parse_maybe_price(obj.get(key))
                        if price is not None:
                            title = self._pick_string(obj.get("title") or obj.get("name") or obj.get("productName") or "") or ""
                            hits.append(self.build_price_candidate(
                                headphone_name or title,
                                price_brl=price,
                                title=title,
                                url=source,
                                source_type="structured_search",
                            ))
                for value in obj.values():
                    visit(value)
            elif isinstance(obj, list):
                for item in obj:
                    visit(item)
            elif isinstance(obj, str):
                price = self._parse_brl_number(obj)
                if price is not None and "R$" in obj:
                    hits.append(self.build_price_candidate(
                        headphone_name or "",
                        price_brl=price,
                        title="",
                        url=source,
                        source_type="structured_search",
                    ))

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
def fetch_zoom_jacotei_prices_list(headphone_name: str, max_items: int = 40, debug: bool = False):
    collector = ZoomJacoteiCollector()
    try:
        result = collector.fetch(headphone_name, max_items=max_items)
        if debug:
            log.info("[zoom] %s: %d hits", headphone_name, len(result) if result else 0)
        return result
    except Exception as exc:
        log.debug("[zoom] %s: fetch error: %s", headphone_name, exc)
        return None
