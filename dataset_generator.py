import os
import json
import time
import pandas as pd
from pipeline import run_evaluation_pipeline
from src.collectors.autoeq       import fetch_autoeq_data
from src.collectors.targets      import get_harman_target, detect_category
from src.collectors.rtings       import fetch_rtings_metrics
from src.collectors.mercadolivre import fetch_br_prices_list
from src.preprocessing.price_cleaner import clean_price_data
from src.scoring.final_score     import rank_scores


def load_mapping():
    path = "data/name_mapping.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_dataset(limit=None):
    with open("data/headphone_library.json", "r", encoding="utf-8") as f:
        library = json.load(f)

    name_map   = load_mapping()
    results    = []
    to_process = library[:limit] if limit else library

    print(f"Iniciando dataset para {len(to_process)} fones...\n")

    for i, item in enumerate(to_process):
        name = item['name']
        slug = name_map.get(name) or item.get('slug', '')
        print(f"[{i+1}/{len(to_process)}] {name}")

        try:
            # 1. Acoustic data — use exact rig_folder from library
            sources = fetch_autoeq_data(name, library_entry=item)
            if not sources:
                print("  Sem dados acústicos — pulando.\n")
                continue

            # 2. Category-appropriate Harman target
            category = detect_category(name)
            t_f, t_m = get_harman_target(category)

            # 3. THD from RTINGS (optional)
            rtings = fetch_rtings_metrics(slug) if slug else None
            thd    = rtings['thd'] if rtings else None

            # 4. Price from Mercado Livre API
            raw_prices = fetch_br_prices_list(name)
            price      = clean_price_data(raw_prices, name)

            # 5. Full pipeline
            result = run_evaluation_pipeline(
                name=name,
                sources_data=sources,
                target_freqs=t_f,
                target_mags=t_m,
                thd_data=thd,
                price=price,
            )

            if result:
                result['category'] = category
                results.append(result)
                score_str = f"{result['score']}" if result['score'] else "N/A (sem preço)"
                print(f"  ✓ Score={score_str} | E_total={result['e_total']} "
                      f"| w_conf={result['w_conf']} | P=R${price}\n")

        except Exception as e:
            print(f"  ✗ Erro: {e}\n")

        time.sleep(1.5)   # responsible rate limiting

    # --- Rank and export ---
    ranked = rank_scores(results)

    # Column order for the CSV
    cols = [
        'rank', 'name', 'category', 'score', 'percentile',
        'e_total', 'e_fr', 'e_thd', 'e_match',
        'e_unc', 'w_conf', 'price_brl',
        'n_sources', 'thd_available', 'match_available',
    ]
    df = pd.DataFrame(ranked)
    # Keep only columns that exist
    df = df[[c for c in cols if c in df.columns]]

    os.makedirs('output', exist_ok=True)
    df.to_csv("output/ranking.csv", index=False, encoding='utf-8-sig')
    print(f"\nDataset concluído: {len(ranked)} fones rankeados → output/ranking.csv")
    return df


if __name__ == "__main__":
    # Smoke-test with 10 headphones first
    build_dataset(limit=10)