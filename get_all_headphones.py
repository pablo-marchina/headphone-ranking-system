import requests
import json

def get_autoeq_library():
    """
    Explora a API do GitHub para listar todas as pastas dentro dos 
    resultados do oratory1990 (referência de alta qualidade).
    """
    # URL da API do GitHub para a árvore de diretórios do oratory1990
    api_url = "https://api.github.com/repos/jaakkopasanen/AutoEq/contents/results/oratory1990/harman_over-ear_2018"
    
    print("A aceder à biblioteca AutoEQ... Isto pode demorar alguns segundos.")
    response = requests.get(api_url)
    
    if response.status_code != 200:
        print("Erro ao aceder à API do GitHub.")
        return []

    items = response.json()
    headphone_list = []

    for item in items:
        if item['type'] == 'dir':
            # Criamos o dicionário necessário para o nosso dataset_generator
            # O 'slug' do RTINGS será tratado como uma aproximação baseada no nome
            name = item['name']
            slug_guess = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
            
            headphone_list.append({
                "name": name,
                "slug": slug_guess
            })

    print(f"Sucesso! {len(headphone_list)} fones encontrados.")
    return headphone_list

if __name__ == "__main__":
    library = get_autoeq_library()
    # Guarda a lista num ficheiro JSON para uso posterior
    with open("data/headphone_library.json", "w", encoding="utf-8") as f:
        json.dump(library, f, indent=4, ensure_ascii=False)
    print("Lista guardada em data/headphone_library.json")