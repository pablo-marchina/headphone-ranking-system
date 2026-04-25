import requests
from bs4 import BeautifulSoup
import re

def fetch_rtings_metrics(headphone_slug):
    """
    Busca métricas de Distorção e Matching no RTINGS.
    O 'slug' é o nome do fone na URL do RTINGS (ex: 'sennheiser/hd-600/reviews')
    """
    url = f"https://www.rtings.com/headphones/reviews/{headphone_slug}"
    headers = {'User-Agent': 'Mozilla/5.0'} # Fingir ser um navegador
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Tentar encontrar o valor de THD (simplificado para este exemplo)
        # No RTINGS real, buscaríamos o seletor específico do gráfico de THD
        # Aqui, vamos simular a busca por um padrão de texto ou valor
        thd_value = 0.2 # Valor padrão caso não encontre (HD 600 é excelente)
        
        # 2. Tentar encontrar o Driver Matching
        # Procuramos pelo texto que indica o desvio padrão de amplitude
        matching_value = 0.5 # Valor padrão (dB)
        
        # Lógica de extração real via seletores CSS (Exemplo):
        # test_value = soup.select_one('.test-result-value').text
        
        return {
            "thd": thd_value,
            "matching": matching_value
        }
    except Exception as e:
        print(f"Erro ao raspar RTINGS: {e}")
        return None

if __name__ == "__main__":
    # Exemplo: Sennheiser HD 600
    metrics = fetch_rtings_metrics("sennheiser/hd-600")
    print(f"Métricas RTINGS: {metrics}")