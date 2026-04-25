import json
import os
import difflib

def load_json_data(filepath):
    """Auxiliar para carregar ficheiros JSON com segurança."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_autoeq_to_rtings_map():
    print("=== Iniciando Mapeamento de Identidades (AutoEQ <-> RTINGS) ===")

    # 1. Carregar Biblioteca AutoEQ (Nomes de exibição)
    autoeq_data = load_json_data("data/headphone_library.json")
    if not autoeq_data:
        print("❌ Erro: 'data/headphone_library.json' não encontrado. Execute 'get_all_headphones.py' primeiro.")
        return

    # 2. Carregar Biblioteca RTINGS (URLs/Slugs extraídos do sitemap)
    rtings_slugs = load_json_data("data/rtings_library.json")
    if not rtings_slugs:
        print("❌ Erro: 'data/rtings_library.json' não encontrado. Execute 'get_rtings_urls.py' primeiro.")
        return

    mapping = {}
    total_autoeq = len(autoeq_data)
    matches_found = 0

    print(f"Processando {total_autoeq} fones do AutoEQ contra {len(rtings_slugs)} slugs do RTINGS...")

    for item in autoeq_data:
        autoeq_name = item['name']
        
        # Normalização para comparação:
        # Criamos uma versão "limpa" do nome (ex: "Sennheiser HD 600" -> "sennheiser-hd-600")
        search_term = autoeq_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        
        # O difflib procura a string mais parecida dentro da lista do RTINGS
        # n=1: Retorna apenas o melhor resultado
        # cutoff=0.5: Nível de rigor. 0.5 é equilibrado para lidar com variações de nomes.
        best_matches = difflib.get_close_matches(search_term, rtings_slugs, n=1, cutoff=0.5)
        
        if best_matches:
            mapping[autoeq_name] = best_matches[0]
            matches_found += 1
            # Log opcional para acompanhar o progresso (pode comentar se for muita poluição no terminal)
            if matches_found % 50 == 0:
                print(f"✅ {matches_found} fones mapeados...")
        else:
            # Caso não encontre nada, deixamos como None para o pipeline usar valores padrão
            mapping[autoeq_name] = None

    # 3. Guardar o resultado final
    output_path = "data/name_mapping.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)

    print("\n" + "="*40)
    print(f"MAPEAMENTO CONCLUÍDO!")
    print(f"Total AutoEQ: {total_autoeq}")
    print(f"Matches bem-sucedidos: {matches_found}")
    print(f"Taxa de sucesso: {(matches_found/total_autoeq)*100:.1f}%")
    print(f"Ficheiro guardado em: {output_path}")
    print("="*40)

if __name__ == "__main__":
    generate_autoeq_to_rtings_map()