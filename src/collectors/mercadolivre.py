import re
import unicodedata
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

BLACKLIST = [
    'cabo', 'case', 'almofada', 'earpad', 'substituição', 'usado',
    'parts', 'peça', 'adaptador', 'espuma', 'grip',
    'protetor', 'suporte', 'stand', 'hanger',
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


def fetch_br_prices_list(headphone_name, max_items=40, debug=False):
    """
    Coleta preços do Mercado Livre via API pública com fallback de queries.
    """
    prices = []
    queries = generate_queries(headphone_name)

    for q in queries:
        url = f"{ML_SEARCH_BASE}/{quote(q.replace(' ', '-'))}"

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

        for item in items[:max_items]:
            title_el = item.select_one("h3") or item.select_one("h2")
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)

            if not _title_looks_relevant(title, headphone_name):
                continue

            price_el = item.select_one("span.andes-money-amount__fraction")
            if not price_el:
                continue

            price = re.sub(r"[^\d]", "", price_el.get_text(strip=True))
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue

            if price > 0:
                prices.append(price)
                if debug:
                    print(f"  ✔ {title[:60]}... -> R$ {price}")

        # Se já coletou preços suficientes, para cedo.
        if len(prices) >= 10:
            break

    return prices