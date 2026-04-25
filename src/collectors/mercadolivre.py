import requests

ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"

BLACKLIST = [
    'cabo', 'case', 'almofada', 'earpad', 'substituição', 'usado',
    'parts', 'peça', 'adaptador', 'cabo auxiliar', 'espuma', 'grip',
    'protetor', 'suporte', 'stand', 'hanger',
]


def fetch_br_prices_list(headphone_name, pages=3):
    """
    Returns a list of valid prices (float, BRL) using the official
    Mercado Livre search API — no HTML scraping.

    Filters applied per item:
        • condition == 'new'
        • title does not contain accessory keywords
        • price > 0

    pages: number of API pages to fetch (50 items each, max 150 total).
    """
    all_prices = []

    for page in range(pages):
        params = {
            'q':         headphone_name,
            'limit':     50,
            'offset':    page * 50,
            'condition': 'new',
        }
        try:
            r = requests.get(ML_SEARCH_URL, params=params, timeout=10)
            if r.status_code != 200:
                break
            data    = r.json()
            results = data.get('results', [])
            if not results:
                break

            for item in results:
                price = item.get('price')
                if not price or price <= 0:
                    continue

                title = item.get('title', '').lower()
                if any(w in title for w in BLACKLIST):
                    continue

                all_prices.append(float(price))

        except Exception as e:
            print(f"  [ML API] Erro na página {page}: {e}")
            break

    return all_prices