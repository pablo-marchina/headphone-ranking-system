import json, os, re, difflib


def load_json(path):
    if not os.path.exists(path): return None
    with open(path, encoding="utf-8") as f: return json.load(f)


def normalize(s):
    """Lowercase, remove punctuation, collapse spaces, expand abbreviations."""
    s = s.lower()
    s = re.sub(r'\bbt\b',       'bluetooth', s)
    s = re.sub(r'\banc\b',      'noise cancelling', s)
    s = re.sub(r'\bnc\b',       'noise cancelling', s)
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-_]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def slug_to_model(slug):
    """'sennheiser/hd-600' → model='hd 600', brand='sennheiser'"""
    parts = slug.split('/', 1)
    brand = parts[0] if len(parts) > 1 else ''
    model = parts[-1]
    return normalize(model), normalize(brand)


def autoeq_to_parts(name):
    """'Sennheiser HD 600' → full_norm, brand='sennheiser', model='hd 600'"""
    norm   = normalize(name)
    tokens = norm.split()
    brand  = tokens[0] if tokens else ''
    model  = ' '.join(tokens[1:]) if len(tokens) > 1 else norm
    return norm, brand, model


def is_valid_rtings_slug(slug):
    """
    Rejects editorial/category pages that pollute the fuzzy match pool.

    Examples rejected:
        best/by-feature/noise-cancelling
        best/headphones
        best/by-price/under-200
        best/gaming-headsets-under-100
    """
    if slug.startswith('best/'):
        return False
    # Also reject anything that doesn't look like brand/model
    parts = slug.split('/')
    if len(parts) < 2:
        return False
    return True


def build_mapping():
    print("=== Mapeamento AutoEQ -> RTINGS ===")

    autoeq = load_json("data/headphone_library.json")
    rtings = load_json("data/rtings_library.json")

    if not autoeq:
        print("headphone_library.json nao encontrado.")
        return
    rtings = rtings or []

    # Pre-compute normalised forms — filter editorial/category slugs first
    rtings_meta = []
    rejected = 0
    for slug in rtings:
        if not is_valid_rtings_slug(slug):
            rejected += 1
            continue
        model_norm, brand_norm = slug_to_model(slug)
        rtings_meta.append({
            'slug':       slug,
            'model_norm': model_norm,
            'brand_norm': brand_norm,
            'full_norm':  normalize(slug.replace('/', ' ')),
        })

    print(f"Pool RTINGS: {len(rtings_meta)} slugs validos ({rejected} editoriais removidos)")

    mapping         = {}
    matched         = 0
    strategy_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for item in autoeq:
        name                    = item['name']
        full_norm, brand, model = autoeq_to_parts(name)

        best_slug  = None

        # --- Strategy 1: Exact full normalised match ---
        for rm in rtings_meta:
            if full_norm == rm['full_norm']:
                best_slug = rm['slug']
                strategy_counts[1] += 1
                break

        # --- Strategy 2: Brand match + model fuzzy (cutoff 0.70) ---
        if not best_slug:
            candidates = [rm for rm in rtings_meta if rm['brand_norm'] == brand]
            if candidates:
                models = [rm['model_norm'] for rm in candidates]
                close  = difflib.get_close_matches(model, models, n=1, cutoff=0.70)
                if close:
                    idx       = models.index(close[0])
                    best_slug = candidates[idx]['slug']
                    strategy_counts[2] += 1

        # --- Strategy 3: Full string fuzzy (cutoff 0.65) ---
        if not best_slug:
            all_fulls = [rm['full_norm'] for rm in rtings_meta]
            close     = difflib.get_close_matches(full_norm, all_fulls, n=1, cutoff=0.65)
            if close:
                idx       = all_fulls.index(close[0])
                best_slug = rtings_meta[idx]['slug']
                strategy_counts[3] += 1

        # --- Strategy 4: Model-only fuzzy across all RTINGS (cutoff 0.80) ---
        if not best_slug:
            all_models = [rm['model_norm'] for rm in rtings_meta]
            close      = difflib.get_close_matches(model, all_models, n=1, cutoff=0.80)
            if close:
                idx       = all_models.index(close[0])
                best_slug = rtings_meta[idx]['slug']
                strategy_counts[4] += 1

        if best_slug:
            matched += 1

        mapping[name] = best_slug   # None when no match found

    os.makedirs('data', exist_ok=True)
    with open("data/name_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    total = len(autoeq)
    print(f"\nConcluido: {matched}/{total} ({100*matched//total if total else 0}%) mapeados.")
    print(f"  Estrategia 1 (exato):              {strategy_counts[1]}")
    print(f"  Estrategia 2 (marca+modelo 0.70):  {strategy_counts[2]}")
    print(f"  Estrategia 3 (full fuzzy 0.65):    {strategy_counts[3]}")
    print(f"  Estrategia 4 (modelo 0.80):        {strategy_counts[4]}")
    print(f"  Sem match:                         {total - matched}")
    print("Salvo em data/name_mapping.json")


if __name__ == "__main__":
    build_mapping()