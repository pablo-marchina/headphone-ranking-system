import requests
from bs4 import BeautifulSoup
import json
import os

def fetch_rtings_database():
    # O RTINGS divide o sitemap. Este é o sitemap específico para reviews de produtos.
    # Nota: URLs de sitemaps podem mudar, mas esta é a estrutura padrão.
    sitemap_url = "https://www.rtings.com/sitemap_reviews.xml"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"Acedendo ao Sitemap do RTINGS: {sitemap_url}")
    
    try:
        response = requests.get(sitemap_url, headers=headers)
        if response.status_code != 200:
            print("Erro ao aceder ao sitemap.")
            return []

        # O sitemap é um XML
        soup = BeautifulSoup(response.text, 'xml')
        urls = soup.find_all('loc')
        
        # Filtramos apenas os links que são de reviews de headphones
        # Queremos o formato: 'marca/modelo'
        headphone_slugs = []
        for url in urls:
            link = url.text
            if '/headphones/reviews/' in link:
                # Extrai apenas a parte final: 'sennheiser/hd-600'
                slug = link.split('/headphones/reviews/')[-1]
                if slug: # Evita strings vazias
                    headphone_slugs.append(slug)
        
        print(f"Sucesso! {len(headphone_slugs)} URLs de fones encontradas no RTINGS.")
        
        # Guardar para o mapeador usar
        if not os.path.exists('data'): os.makedirs('data')
        with open("data/rtings_library.json", "w", encoding="utf-8") as f:
            json.dump(headphone_slugs, f, indent=4, ensure_ascii=False)
            
        return headphone_slugs

    except Exception as e:
        print(f"Erro no scraper de sitemap: {e}")
        return []

if __name__ == "__main__":
    fetch_rtings_database()