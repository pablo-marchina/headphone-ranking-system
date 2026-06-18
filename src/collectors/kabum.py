"""Kabum price collector.

Uses the Next.js __NEXT_DATA__ embedded state on Kabum's search pages
to extract product names and prices.

Data path: __NEXT_DATA__ → props.pageProps.data.catalogServer.data[]
Each product has: name, price, priceWithDiscount, available
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import quote

from .base import BaseCollector

log = logging.getLogger(__name__)

KABUM_SEARCH_URL = "https://www.kabum.com.br/busca/{query}"


class KabumPriceCollector(BaseCollector):
    source_name = "kabum"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        url = KABUM_SEARCH_URL.format(query=quote(name))
        html = self._get_text(url)
        if not html:
            log.debug("[kabum] %s: empty response", name)
            return None

        try:
            match = re.search(
                r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html, re.DOTALL,
            )
            if not match:
                log.debug("[kabum] %s: __NEXT_DATA__ not found", name)
                return None

            data = json.loads(match.group(1))
            products = (
                data.get("props", {})
                .get("pageProps", {})
                .get("data", {})
                .get("catalogServer", {})
                .get("data", [])
            )

            if not isinstance(products, list):
                log.debug("[kabum] %s: products is not a list", name)
                return None

            results: list[dict[str, Any]] = []
            for item in products:
                if not isinstance(item, dict):
                    continue
                # Only include available products
                if not item.get("available", False):
                    continue

                title = str(item.get("name", "")).strip()
                if not title:
                    continue

                # Reject accessories — products *for* the headphone, not the headphone itself.
                n_title = self._normalize_target(title)
                accessory_keywords = (
                    "almofada", "earpad", "ear pad", "capa", "case", "bolsa", "estojo",
                    "cabo", "carregador", "fonte", "adaptador", "suporte", "pelicula",
                    "filtro", "protetor", "plug", "conector", "ponta", "espuma",
                    "replacement", "reposicao", "peça", "peca", "acessorio", "acessório",
                )
                if any(kw in n_title for kw in accessory_keywords):
                    continue

                # Only accept products whose name contains the headphone name.
                # This prevents unrelated accessories or different models from leaking in.
                if not self._match_name(title, name):
                    continue

                price = self._safe_float(item.get("priceWithDiscount") or item.get("price"))
                if price is None or price <= 0:
                    continue

                results.append(self.build_price_candidate(
                    name,
                    price_brl=price,
                    title=title,
                    url=f"https://www.kabum.com.br/{item.get('friendlyName', '')}",
                    availability="available",
                    source_type="structured_search",
                ))

            log.debug("[kabum] %s: %d results", name, len(results))
            return results if results else None

        except Exception as exc:
            log.debug("[kabum] %s: parse error: %s", name, exc)
            return None
