import os
from pathlib import Path
from collections import defaultdict

# Ajuste esse caminho se o clone ficou em outro lugar
REPO_PATH = Path("autoeq_repo/measurements")

if not REPO_PATH.exists():
    print(f"[ERRO] Pasta nao encontrada: {REPO_PATH}")
    print("Rode primeiro: git clone --depth=1 https://github.com/jaakkopasanen/AutoEq.git autoeq_repo")
    exit(1)

def contar_csvs(source_path, label):
    """Conta CSVs raw (sem compensated/target) e agrupa por rig."""
    path = REPO_PATH / source_path
    if not path.exists():
        print(f"[{label}] Pasta nao encontrada: {path}")
        return [], {}

    csvs = [
        p for p in path.rglob("*.csv")
        if "compensated" not in p.name.lower()
        and "target" not in p.name.lower()
        and "README" not in p.name
    ]

    # Agrupa pelo primeiro nivel de subpasta (rig)
    by_rig = defaultdict(list)
    for csv in csvs:
        rel = csv.relative_to(path)
        parts = rel.parts
        rig = parts[0] if len(parts) > 1 else "(raiz)"
        by_rig[rig].append(csv)

    print(f"\n=== {label} ({len(csvs)} CSVs raw) ===")
    for rig, files in sorted(by_rig.items()):
        print(f"  [{rig}]  {len(files)} fones")
        for f in sorted(files)[:2]:
            print(f"    {f.name}")
        if len(files) > 2:
            print(f"    ... +{len(files)-2} mais")

    return csvs, by_rig

# Diagnostico por fonte
crinacle_csvs, crinacle_rigs = contar_csvs("crinacle", "crinacle")
oratory_csvs, oratory_rigs  = contar_csvs("oratory1990", "oratory1990")
rtings_csvs,  rtings_rigs   = contar_csvs("Rtings", "Rtings")

total = len(set(
    [str(p) for p in crinacle_csvs] +
    [str(p) for p in oratory_csvs]  +
    [str(p) for p in rtings_csvs]
))

print(f"\n=== TOTAL GERAL (3 fontes) ===")
print(f"crinacle:    {len(crinacle_csvs)}")
print(f"oratory1990: {len(oratory_csvs)}")
print(f"Rtings:      {len(rtings_csvs)}")
print(f"Total unico: {total}")
print()

# Mostra estrutura completa de pastas para o collector
print("=== ESTRUTURA DE PASTAS (para o collector) ===")
sources = [
    ("crinacle",    crinacle_rigs),
    ("oratory1990", oratory_rigs),
    ("Rtings",      rtings_rigs),
]
for label, rigs in sources:
    print(f"\n{label}/")
    for rig in sorted(rigs.keys()):
        print(f"  {rig}/")