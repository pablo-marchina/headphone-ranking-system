import json
import os
import difflib


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_mapping():
    """
    Fuzzy-match AutoEQ headphone names to RTINGS slugs.
    Writes data/name_mapping.json: {autoeq_name → rtings_slug | null}.

    The mapping is used only to fetch THD from RTINGS; if a match isn't
    found the pipeline still runs (E_THD = 0, E_unc inflated).
    """
    print("=== Mapeamento AutoEQ → RTINGS ===")

    autoeq = load_json("data/headphone_library.json")
    rtings = load_json("data/rtings_library.json")

    if not autoeq:
        print("❌  data/headphone_library.json não encontrado. Execute get_all_headphones.py primeiro.")
        return
    if not rtings:
        print("⚠️  data/rtings_library.json não encontrado. Mapeamento RTINGS será vazio.")
        rtings = []

    mapping = {}
    matched = 0

    for item in autoeq:
        name = item['name']
        # Normalise: lowercase, spaces → hyphens, drop parentheses
        norm = name.lower().replace(" ", "-").replace("(", "").replace(")", "")

        # difflib compares against the final segment of each RTINGS slug
        rtings_models = [s.split('/')[-1] for s in rtings]
        best = difflib.get_close_matches(norm, rtings_models, n=1, cutoff=0.55)

        if best:
            # Recover the full slug from the matched model segment
            idx = rtings_models.index(best[0])
            mapping[name] = rtings[idx]
            matched += 1
        else:
            mapping[name] = None

    with open("data/name_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)

    total = len(autoeq)
    print(f"Concluído: {matched}/{total} ({100*matched//total}%) mapeados.")
    print("Arquivo salvo em data/name_mapping.json")


if __name__ == "__main__":
    generate_mapping()