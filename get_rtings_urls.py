import requests
from bs4 import BeautifulSoup
import json
import os

SITEMAP_URL = "https://www.rtings.com/sitemap_en_headphones.xml"
HEADERS     = {'User-Agent': 'Mozilla/5.0'}


def fetch_rtings_database():
    """
    Crawls the RTINGS headphone sitemap and extracts reviewer slugs
    (format: "brand/model") for use in fetch_rtings_metrics().
    Saves to data/rtings_library.json.
    """
    print(f"Acessando sitemap RTINGS: {SITEMAP_URL}")
    try:
        r = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Falha ({r.status_code}). Tentando sitemap alternativo...")
            # Fallback: generic sitemap index
            r = requests.get("https://www.rtings.com/sitemap.xml",
                             headers=HEADERS, timeout=15)

        soup  = BeautifulSoup(r.text, 'lxml-xml')
        urls  = [loc.text for loc in soup.find_all('loc')]

        slugs = []
        for url in urls:
            # Match URLs like: .../headphones/reviews/brand/model
            if '/headphones/reviews/' in url:
                slug = url.split('/headphones/reviews/')[-1].rstrip('/')
                if slug and '/' in slug:   # must have brand/model format
                    slugs.append(slug)

        print(f"{len(slugs)} URLs de fones encontradas.")
        os.makedirs('data', exist_ok=True)
        with open("data/rtings_library.json", "w", encoding="utf-8") as f:
            json.dump(slugs, f, indent=4, ensure_ascii=False)
        return slugs

    except Exception as e:
        print(f"Erro: {e}")
        return []


if __name__ == "__main__":
    fetch_rtings_database()