import requests
from bs4 import BeautifulSoup

def fetch_br_prices_list(headphone_name):
    query = headphone_name.replace(" ", "-")
    url = f"https://lista.mercadolivre.com.br/{query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Captura todos os blocos de anúncios para verificar o título
        items = soup.find_all('div', {'class': 'ui-search-result__wrapper'})
        
        valid_prices = []
        for item in items:
            title = item.find('h2').text.lower()
            price_element = item.find('span', {'class': 'andes-money-amount__fraction'})
            
            if price_element:
                price = int(price_element.text.replace('.', ''))
                
                # FILTRO DE PALAVRAS-CHAVE:
                # Se o título contiver "cabo", "case", "almofada" ou "usado", ignoramos.
                blacklist = ['cabo', 'case', 'almofada', 'earpad', 'usado', 'substituição', 'parts']
                if any(word in title for word in blacklist):
                    continue
                
                valid_prices.append(price)
        
        return valid_prices
    except:
        return []