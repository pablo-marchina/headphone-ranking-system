import os
import json

REPO_MEASUREMENTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "autoeq_repo", "measurements"
))

# crinacle only has a name_index.tsv — no actual measurement CSVs
SKIP_REVIEWERS = {"crinacle"}


def detect_category(folder_name):
    n = folder_name.lower()
    if "in-ear" in n or "iem" in n: return "in-ear"
    if "on-ear" in n:               return "on-ear"
    return "over-ear"


def make_entry(name, reviewer, path_prefix, nested, category):
    slug = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    return {"name": name, "slug": slug, "reviewer": reviewer,
            "path_prefix": path_prefix, "nested": nested, "category": category}


def scan_for_csvs(abs_folder, reviewer, path_prefix, category):
    """
    Returns headphone entries from a folder.
    - Flat: CSVs live directly here  → nested=False
    - Nested: each headphone has its own subfolder → nested=True
    """
    if not os.path.isdir(abs_folder):
        return []
    entries   = os.listdir(abs_folder)
    csv_files = [e for e in entries if e.endswith('.csv')]
    sub_dirs  = [e for e in entries if os.path.isdir(os.path.join(abs_folder, e))]

    if csv_files:
        return [make_entry(f[:-4], reviewer, path_prefix, False, category)
                for f in csv_files]
    if sub_dirs:
        return [make_entry(d, reviewer, path_prefix, True, category)
                for d in sub_dirs
                if any(f.endswith('.csv')
                       for f in os.listdir(os.path.join(abs_folder, d)))]
    return []


def discover_reviewer(reviewer):
    """
    Handles three common layouts:

    Layout A — /data/{category}/*.csv          (oratory1990, most reviewers)
    Layout B — /data/{category}/{rig}/*.csv    (Rtings — extra rig subfolder)
    Layout C — /{category}/*.csv               (Headphone.com Legacy, Innerfidelity)
    """
    reviewer_root = os.path.join(REPO_MEASUREMENTS, reviewer)
    all_hp = []

    # --- Try /data/ subfolder first (Layouts A & B) ---
    data_dir = os.path.join(reviewer_root, "data")
    if os.path.isdir(data_dir):
        for cat_folder in sorted(os.listdir(data_dir)):
            cat_path = os.path.join(data_dir, cat_folder)
            if not os.path.isdir(cat_path):
                continue
            category    = detect_category(cat_folder)
            sub_entries = os.listdir(cat_path)
            has_csv  = any(e.endswith('.csv') for e in sub_entries)
            has_dirs = any(os.path.isdir(os.path.join(cat_path, e)) for e in sub_entries)

            if has_csv:
                # Layout A — flat
                prefix = f"{reviewer}/data/{cat_folder}"
                hp = scan_for_csvs(cat_path, reviewer, prefix, category)
                if hp: print(f"  [{prefix}] {len(hp)} fones")
                all_hp.extend(hp)
            elif has_dirs:
                # Layout B — rig subfolder
                for rig in sorted(sub_entries):
                    rig_path = os.path.join(cat_path, rig)
                    if not os.path.isdir(rig_path):
                        continue
                    prefix = f"{reviewer}/data/{cat_folder}/{rig}"
                    hp = scan_for_csvs(rig_path, reviewer, prefix, category)
                    if hp: print(f"  [{prefix}] {len(hp)} fones")
                    all_hp.extend(hp)
        if all_hp:
            return all_hp

    # --- Fallback: scan root directly (Layout C) ---
    skip = {'data', 'raw_data', 'resources', '.git', '__pycache__'}
    for folder in sorted(os.listdir(reviewer_root)):
        folder_path = os.path.join(reviewer_root, folder)
        if not os.path.isdir(folder_path) or folder in skip:
            continue
        category = detect_category(folder)
        prefix   = f"{reviewer}/{folder}"
        hp = scan_for_csvs(folder_path, reviewer, prefix, category)
        if hp: print(f"  [{prefix}] {len(hp)} fones")
        all_hp.extend(hp)

    return all_hp


def build_library():
    if not os.path.isdir(REPO_MEASUREMENTS):
        print("ERRO: autoeq_repo/measurements nao encontrado.")
        print("Execute: git clone https://github.com/jaakkopasanen/AutoEq autoeq_repo --depth 1")
        return []

    # Auto-discover all reviewer folders
    all_reviewers = sorted(
        d for d in os.listdir(REPO_MEASUREMENTS)
        if os.path.isdir(os.path.join(REPO_MEASUREMENTS, d))
        and d not in SKIP_REVIEWERS
    )
    print(f"Reviewers encontrados: {len(all_reviewers)}\n")

    all_hp, seen = [], set()
    for reviewer in all_reviewers:
        print(f"Indexando {reviewer}...")
        for h in discover_reviewer(reviewer):
            if h['name'] not in seen:
                all_hp.append(h)
                seen.add(h['name'])

    os.makedirs('data', exist_ok=True)
    with open("data/headphone_library.json", "w", encoding="utf-8") as f:
        json.dump(all_hp, f, indent=2, ensure_ascii=False)

    print(f"\nTotal: {len(all_hp)} fones unicos -> data/headphone_library.json")
    return all_hp


if __name__ == "__main__":
    build_library()