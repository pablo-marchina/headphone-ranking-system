import os
import json
import time
import pandas as pd
import numpy as np
from pipeline import run_evaluation_pipeline
from src.collectors.autoeq import fetch_autoeq_data
from src.collectors.targets import get_harman_target
from src.collectors.rtings import fetch_rtings_metrics
from src.collectors.mercadolivre import fetch_br_prices_list
from src.preprocessing.price_cleaner import clean_price_data

def load_mapping():
    path = "data/name_mapping.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def build_huge_dataset(limit=None):
    # Carregar dados
    with open("data/headphone_library.json", "r", encoding="utf-8") as f:
        full_library = json.load(f)
    
    name_map = load_mapping()
    target_f, target_m = get_harman_target()
    results = []

    to_process = full_library[:limit] if limit else full_library
    print(f"Iniciando Dataset para {len(to_process)} fones...")

    for i, item in enumerate(to_process):
        name = item['name']
        slug = name_map.get(name) or item['slug'] # Usa o mapa ou o slug padrão
        
        print(f"[{i+1}/{len(to_process)}] Processando: {name}")
        
        try:
            # 1. Dados Técnicos
            freqs, mags = fetch_autoeq_data(name)
            if freqs is None: continue
            
            rtings = fetch_rtings_metrics(slug)
            
            # 2. Preço Limpo
            raw_prices = fetch_br_prices_list(name)
            price = clean_price_data(raw_prices, name)

            # 3. Score via Pipeline
            score = run_evaluation_pipeline(
                name=name, raw_freqs=freqs, raw_mags=mags,
                target_freqs=target_f, target_mags=target_m,
                thd_data=rtings['thd'] if rtings else 0.5
            )

            # 4. Salvar resultado
            results.append({
                "Modelo": name,
                "Nota_Tecnica": round(score, 2),
                "Preco_BRL": round(price, 2) if price else None,
                "Custo_Beneficio": round((score**2 / np.log10(price)), 2) if price else None
            })
            
            time.sleep(2) # Pausa ética

        except Exception as e:
            print(f"Erro em {name}: {e}")

    df = pd.DataFrame(results).sort_values(by="Nota_Tecnica", ascending=False)
    if not os.path.exists('output'): os.makedirs('output')
    df.to_csv("output/dataset_final.csv", index=False, encoding='utf-8-sig')
    print("Dataset concluído em output/dataset_final.csv")

if __name__ == "__main__":
    # Teste com 10 fones primeiro
    build_huge_dataset(limit=10)