import requests
import numpy as np
import io

def fetch_autoeq_data(headphone_full_name):
    """
    Busca os dados de compensação (FR) do repositório AutoEQ.
    Exemplo de nome: "Sennheiser HD 600"
    Note: O AutoEQ usa uma nomenclatura específica nas pastas.
    """
    # URL base do AutoEQ (Resultados para a curva Harman Over-Ear 2018)
    base_url = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/results/"
    
    # Tratamento básico do nome para a URL (substituir espaços por hífens)
    folder_name = headphone_full_name.replace(" ", "%20")
    file_url = f"{base_url}oratory1990/harman_over-ear_2018/{folder_name}/{headphone_full_name}%20fixed%20band%20eq.csv"
    
    print(f"Buscando dados em: {file_url}")
    
    response = requests.get(file_url)
    
    if response.status_code != 200:
        print(f"Erro: Não foi possível encontrar o fone '{headphone_full_name}'.")
        return None, None

    # Lendo o CSV (Frequência, Ganho)
    # O AutoEQ fornece o CSV com os ajustes, mas também a curva original
    raw_data = np.genfromtxt(io.StringIO(response.text), delimiter=',', skip_header=1)
    
    freqs = raw_data[:, 0]
    mags = raw_data[:, 1] # Aqui pegamos a resposta bruta
    
    return freqs, mags

if __name__ == "__main__":
    # Teste real com um fone famoso
    f, m = fetch_autoeq_data("Sennheiser HD 600")
    if f is not None:
        print(f"Sucesso! Capturados {len(f)} pontos de dados para o HD 600.")