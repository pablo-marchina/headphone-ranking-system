import os, json, time
import pandas as pd
from pipeline import run_evaluation_pipeline
from src.collectors.autoeq       import fetch_autoeq_data, LOCAL_REPO
from src.collectors.targets      import get_harman_target, detect_category
from src.collectors.rtings       import fetch_rtings_metrics
from src.collectors.mercadolivre import fetch_br_prices_list
from src.preprocessing.price_cleaner import clean_price_data
from src.scoring.final_score     import rank_scores

PRICE_CACHE_FILE = "data/price_cache.json"
LOCAL_MODE = os.path.isdir(LOCAL_REPO)   # True when autoeq_repo/ exists on disk


def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, encoding="utf-8") as f: return json.load(f)

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def load_mapping():
    """Always returns a dict {name: slug}."""
    data = load_json("data/name_mapping.json")
    # Guard against old list-of-dicts format
    if isinstance(data, list):
        return {item['autoeq_name']: item.get('rtings_slug') for item in data}
    return data if isinstance(data, dict) else {}

def get_price(name, cache):
    """Return cached price or fetch fresh from ML API."""
    if name in cache:
        return cache[name]
    raw    = fetch_br_prices_list(name)
    price  = clean_price_data(raw, name)
    cache[name] = price
    return price


def build_dataset(limit=None):
    library  = load_json("data/headphone_library.json")
    name_map = load_mapping()
    price_cache = load_json(PRICE_CACHE_FILE)

    if not library:
        print("headphone_library.json nao encontrado. Execute get_all_headphones.py primeiro.")
        return

    results    = []
    to_process = library[:limit] if limit else library
    mode_label = "local" if LOCAL_MODE else "remote"
    print(f"Iniciando dataset para {len(to_process)} fones (modo: {mode_label})...\n")

    for i, item in enumerate(to_process):
        name = item['name']
        slug = name_map.get(name) or item.get('slug', '')
        print(f"[{i+1}/{len(to_process)}] {name}")

        try:
            sources = fetch_autoeq_data(name, library_entry=item)
            if not sources:
                print("  Sem dados acusticos — pulando.\n")
                continue

            category = detect_category(name) if detect_category(name) != 'over-ear' \
                       else item.get('category', 'over-ear')
            t_f, t_m = get_harman_target(category)

            rtings = fetch_rtings_metrics(slug) if slug else None
            thd    = rtings['thd'] if rtings else None

            price  = get_price(name, price_cache)

            result = run_evaluation_pipeline(
                name=name, sources_data=sources,
                target_freqs=t_f, target_mags=t_m,
                thd_data=thd, price=price,
            )
            if result:
                result['category'] = category
                results.append(result)
                s = f"{result['score']:.6f}" if result['score'] else "N/A"
                print(f"  Score={s} | E_total={result['e_total']} | w_conf={result['w_conf']}\n")

        except Exception as e:
            print(f"  Erro: {e}\n")

        # Rate-limit sleep only when hitting remote APIs
        if not LOCAL_MODE:
            time.sleep(1.5)

    # Persist price cache for incremental runs
    save_json(PRICE_CACHE_FILE, price_cache)

    ranked = rank_scores(results)
    cols   = ['rank','name','category','score','percentile',
              'e_total','e_fr','e_thd','e_match',
              'e_unc','w_conf','price_brl',
              'n_sources','thd_available','match_available']
    df = pd.DataFrame(ranked)
    df = df[[c for c in cols if c in df.columns]]
    os.makedirs('output', exist_ok=True)
    df.to_csv("output/ranking.csv", index=False, encoding='utf-8-sig')
    print(f"\nConcluido: {len(ranked)} fones -> output/ranking.csv")
    return df


if __name__ == "__main__":
    build_dataset(limit=10)