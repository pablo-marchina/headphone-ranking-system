"""Mercado Livre price collector with quality filters.

Keeps backward-compatible helper functions from the existing standalone module,
but adds a class-based collector and seller/listing quality rules.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector

BLACKLIST = [
    "cabo", "case", "almofada", "earpad", "substituição", "usado",
    "parts", "peça", "adaptador", "espuma", "grip",
    "protetor", "suporte", "stand", "hanger",
]

ML_SEARCH_BASE = "https://lista.mercadolivre.com.br"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


class MercadoLivrePriceCollector(BaseCollector):
    source_name = "mercadolivre"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        try:
            max_items = int(kwargs.get("max_items", 40))
            min_active_listings = int(kwargs.get("min_active_listings", 5))
        except Exception:
            max_items = 40
            min_active_listings = 5

        seller_types = kwargs.get("seller_types")
        if seller_types is None:
            seller_types = {"official", "loja oficial", "official_store"}
        else:
            seller_types = {str(s).strip().lower() for s in seller_types}

        prices = fetch_br_prices_list(
            name,
            max_items=max_items,
            min_active_listings=min_active_listings,
            seller_types=seller_types,
        )
        if prices is None:
            return None
        return [{"price_brl": float(p), "source": self.source_name, "title": "", "url": ""} for p in prices]


# ---------------------------------------------------------------------------
# Existing helpers
# ---------------------------------------------------------------------------

def _normalize(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def generate_queries(name):
    """
    Gera múltiplas variações do nome para aumentar chance de encontrar no ML
    """
    queries = [
        name,
        name.replace("7Hz", "").strip(),
        name.replace("Salnotes", "").strip(),
        name.replace("Sennheiser", "").strip(),
        name.replace("Moondrop", "").strip(),
    ]

    # fallback agressivo
    words = name.split()
    if len(words) >= 1:
        queries.append(words[-1])  # última palavra (ex: "Zero", "600")

    # remove duplicados e vazios (preservando ordem)
    deduped = []
    seen = set()
    for q in queries:
        q = q.strip()
        if not q or q in seen:
            continue
        seen.add(q)
        deduped.append(q)
    return deduped


def _title_looks_relevant(title, headphone_name):
    n_title = _normalize(title)
    n_name = _normalize(headphone_name)

    if any(w in n_title for w in BLACKLIST):
        return False

    name_tokens = [t for t in n_name.split() if len(t) >= 3]
    if not name_tokens:
        return True

    matches = sum(1 for token in name_tokens if token in n_title)
    min_matches = 2 if len(name_tokens) >= 2 else 1
    return matches >= min_matches


def _extract_seller_type(card_text: str) -> str:
    text = _normalize(card_text)
    if "loja oficial" in text or "official store" in text or "mercado l" in text:
        return "official"
    if "envio full" in text or "full" in text:
        return "marketplace"
    return "unknown"


def _parse_price_text(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = text.strip().replace("R$", "").replace(".", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        value = float(match.group(0))
        return value if value > 0 else None
    except Exception:
        return None


def fetch_br_prices_list(headphone_name, max_items=40, debug=False, min_active_listings=5, seller_types=None):
    """
    Coleta preços do Mercado Livre via página pública com filtros de qualidade.

    Regras de qualidade:
    - exige um mínimo de anúncios relevantes antes de aceitar a fonte;
    - filtra por tipo de vendedor quando essa informação aparece na card/page.
    """
    prices = []
    queries = generate_queries(headphone_name)
    seller_types = {str(s).strip().lower() for s in (seller_types or {"official"})}

    for q in queries:
        url = f"{ML_SEARCH_BASE}/{quote_plus(q.replace(' ', '-'))}"

        if debug:
            print(f"[ML] Tentando: {q}")
            print(f"[ML] URL: {url}")

        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            if debug:
                print(f"[ML] erro API: {e}")
            continue

        items = soup.select("li.ui-search-layout__item")
        if debug:
            print(f"[ML] Itens encontrados: {len(items)}")

        if len(items) < min_active_listings:
            # Qualidade mínima: não usar uma busca com poucos anúncios.
            continue

        for item in items[:max_items]:
            text_blob = item.get_text(" ", strip=True)
            title_el = item.select_one("h3") or item.select_one("h2")
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)

            if not _title_looks_relevant(title, headphone_name):
                continue

            seller_type = _extract_seller_type(text_blob)
            if seller_types and seller_type not in seller_types:
                continue

            price_el = item.select_one("span.andes-money-amount__fraction")
            if not price_el:
                # fallback: parse first BRL in the whole card
                price = _parse_price_text(text_blob)
            else:
                price = _parse_price_text(price_el.get_text(strip=True))

            if price is None or price <= 0:
                continue

            prices.append(price)
            if debug:
                print(f"  ✔ {title[:60]}... -> R$ {price}")

        # Se já coletou preços suficientes, para cedo.
        if len(prices) >= 10:
            break

    return prices
