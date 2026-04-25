"""
Baixa CSVs raw do crinacle via GitHub API, pasta por pasta.
Salva em autoeq_repo/measurements/crinacle/{rig}/{nome}.csv
com nomes sanitizados para evitar problemas de path no Windows.
"""

import requests
import os
import time
from pathlib import Path

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
API_BASE = "https://api.github.com/repos/jaakkopasanen/AutoEq/contents/measurements/crinacle"
OUT_BASE = Path("autoeq_repo/measurements/crinacle")

SKIP_KEYWORDS = ["compensated", "target", "README"]

def sanitize(name, max_len=80):
    """Encurta nomes longos mantendo legibilidade."""
    name = name.replace("?", "").replace(":", "").replace("*", "").replace("|", "")
    if len(name) > max_len:
        name = name[:max_len]
    return name.strip()

def api_get(url, retries=3):
    for attempt in range(retries):
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 403:
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            print(f"  [rate limit] aguardando {wait:.0f}s...")
            time.sleep(wait)
        else:
            print(f"  [HTTP {r.status_code}] {url}")
            return None
    return None

def download_csv(url, out_path):
    r = requests.get(url)
    if r.status_code == 200:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return True
    return False

# 1. Lista rigs (primeiro nível)
print("Listando rigs do crinacle...")
items = api_get(API_BASE)
if not items:
    print("[ERRO] Nao foi possivel listar o crinacle. Verifique GITHUB_TOKEN.")
    exit(1)

rigs = [i for i in items if i["type"] == "dir"]
print(f"Encontrados {len(rigs)} rigs: {[r['name'] for r in rigs]}\n")

total_ok = 0
total_skip = 0
total_err = 0

for rig in rigs:
    rig_name = sanitize(rig["name"], max_len=60)
    print(f"[{rig_name}] Listando fones...")

    headphones = api_get(rig["url"])
    if not headphones:
        print(f"  [ERRO] Nao foi possivel listar {rig_name}")
        continue

    hp_dirs = [h for h in headphones if h["type"] == "dir"]
    hp_csvs = [h for h in headphones if h["type"] == "file"
               and h["name"].endswith(".csv")
               and not any(k in h["name"].lower() for k in SKIP_KEYWORDS)]

    print(f"  {len(hp_dirs)} subpastas, {len(hp_csvs)} CSVs diretos")

    # CSVs direto na pasta do rig (sem subpasta de headphone)
    for csv_item in hp_csvs:
        out_path = OUT_BASE / rig_name / sanitize(csv_item["name"])
        if out_path.exists():
            total_skip += 1
            continue
        ok = download_csv(csv_item["download_url"], out_path)
        if ok:
            total_ok += 1
        else:
            total_err += 1
            print(f"  [ERR] {csv_item['name']}")

    # Desce um nivel para pastas de headphone
    for hp in hp_dirs:
        hp_name = sanitize(hp["name"], max_len=60)
        contents = api_get(hp["url"])
        if not contents:
            total_err += 1
            continue

        csvs = [c for c in contents
                if c["type"] == "file"
                and c["name"].endswith(".csv")
                and not any(k in c["name"].lower() for k in SKIP_KEYWORDS)]

        for csv_item in csvs:
            out_path = OUT_BASE / rig_name / hp_name / sanitize(csv_item["name"])
            if out_path.exists():
                total_skip += 1
                continue
            ok = download_csv(csv_item["download_url"], out_path)
            if ok:
                total_ok += 1
            else:
                total_err += 1
                print(f"  [ERR] {csv_item['name']}")

        time.sleep(0.05)  # evita rate limit

    print(f"  -> ok={total_ok} skip={total_skip} err={total_err}")

print(f"\n=== CONCLUIDO ===")
print(f"Baixados: {total_ok}")
print(f"Pulados (ja existiam): {total_skip}")
print(f"Erros: {total_err}")

# Contagem final
csvs = list(OUT_BASE.rglob("*.csv"))
print(f"Total de CSVs em {OUT_BASE}: {len(csvs)}")