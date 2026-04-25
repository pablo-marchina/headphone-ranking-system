import requests
import os

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

# Baixa e examina o name_index.tsv
print("=== name_index.tsv (primeiras 20 linhas) ===")
r = requests.get(
    "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/measurements/crinacle/name_index.tsv"
)
lines = r.text.strip().split("\n")
print(f"Total de linhas: {len(lines)}")
print()
for line in lines[:20]:
    print(repr(line))

print()
print("=== Testando squig.link API ===")

# Testa o endpoint do squig.link com o primeiro nome do index
# O formato tipico e: https://squig.link/?share={nome}
# Mas a API de dados brutos e diferente

# Tenta o endpoint de dados do squig.link
test_names = ["Moondrop Aria", "KZ ZEX Pro", "Sennheiser HD 600"]

for name in test_names:
    # Formato 1: API direta
    url1 = f"https://squig.link/data/{name}.json"
    r1 = requests.get(url1)
    print(f"{name} -> squig.link/data/: HTTP {r1.status_code}")

    # Formato 2: crinacle raw data
    url2 = f"https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/measurements/crinacle/{name}/{name}.csv"
    r2 = requests.get(url2, headers=HEADERS)
    print(f"{name} -> AutoEQ csv direto: HTTP {r2.status_code}")
    print()