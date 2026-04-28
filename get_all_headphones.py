import os
import json
from collections import OrderedDict

REPO_MEASUREMENTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "autoeq_repo", "measurements"
))

# Crinacle is handled separately through its TSV index.
SKIP_REVIEWERS = set()


def detect_category(folder_name):
    n = folder_name.lower()
    if "in-ear" in n or "iem" in n:
        return "in-ear"
    if "on-ear" in n:
        return "on-ear"
    return "over-ear"


def make_source(name, reviewer, path_prefix, nested, category, rig=None):
    slug = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    source = {
        "name": name,
        "slug": slug,
        "reviewer": reviewer,
        "path_prefix": path_prefix,
        "nested": nested,
        "category": category,
    }
    if rig:
        source["rig"] = rig
    return source


def scan_for_csvs(abs_folder, reviewer, path_prefix, category, rig=None):
    """
    Returns headphone source records from a folder.
    - Flat: CSVs live directly here  → nested=False
    - Nested: each headphone has its own subfolder → nested=True
    """
    if not os.path.isdir(abs_folder):
        return []
    entries = os.listdir(abs_folder)
    csv_files = [e for e in entries if e.endswith('.csv')]
    sub_dirs = [e for e in entries if os.path.isdir(os.path.join(abs_folder, e))]

    if csv_files:
        return [make_source(f[:-4], reviewer, path_prefix, False, category, rig=rig)
                for f in csv_files]
    if sub_dirs:
        return [make_source(d, reviewer, path_prefix, True, category, rig=rig)
                for d in sub_dirs
                if any(f.endswith('.csv')
                       for f in os.listdir(os.path.join(abs_folder, d)))]
    return []


def _normalize_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y"}:
        return True
    if v in {"0", "false", "no", "n"}:
        return False
    return None


def _parse_crinacle_tsv(tsv_path, reviewer):
    """Parse Crinacle's TSV index and preserve rig as part of the source identity."""
    sources = []
    if not os.path.isfile(tsv_path):
        return sources

    with open(tsv_path, encoding='utf-8-sig') as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]

    if not lines:
        return sources

    header = [h.strip().lower() for h in lines[0].split('\t')]
    rows = [line.split('\t') for line in lines[1:]] if len(lines) > 1 else []

    def get_row_value(row_dict, *candidates):
        for key in candidates:
            if key in row_dict and row_dict[key].strip():
                return row_dict[key].strip()
        return ""

    for row in rows:
        row = row + [""] * max(0, len(header) - len(row))
        row_dict = {
            header[i]: row[i].strip() if i < len(row) else ""
            for i in range(len(header))
        }

        name = get_row_value(row_dict, 'name', 'title', 'headphone', 'item')
        if not name:
            continue

        rig = get_row_value(row_dict, 'rig', 'measurement_rig', 'measure_rig', 'fixture', 'coupler')
        category = get_row_value(row_dict, 'category', 'type', 'form_factor') or 'over-ear'
        category = detect_category(category)

        path_prefix = get_row_value(row_dict, 'path_prefix', 'path', 'folder', 'directory', 'csv', 'file')
        nested_raw = get_row_value(row_dict, 'nested')
        nested = _normalize_bool(nested_raw)

        if not path_prefix:
            base = f"{reviewer}/data"
            if category == 'in-ear':
                base = f"{base}/in-ear"
            elif category == 'on-ear':
                base = f"{base}/on-ear"
            else:
                base = f"{base}/over-ear"
            if rig:
                path_prefix = f"{base}/{rig}"
            else:
                path_prefix = base

        if nested is None:
            nested = bool(rig)

        sources.append(make_source(name, reviewer, path_prefix, nested, category, rig=rig or None))

    return sources


def discover_reviewer(reviewer):
    """
    Handles three common layouts:

    Layout A — /data/{category}/*.csv          (oratory1990, most reviewers)
    Layout B — /data/{category}/{rig}/*.csv    (extra rig subfolder)
    Layout C — /{category}/*.csv               (Headphone.com Legacy, Innerfidelity)
    """
    reviewer_root = os.path.join(REPO_MEASUREMENTS, reviewer)
    all_hp = []

    if reviewer.lower() == 'crinacle':
        candidates = []
        for root, _, files in os.walk(reviewer_root):
            for file in files:
                if file.lower() == 'name_index.tsv':
                    candidates.append(os.path.join(root, file))
        for tsv_path in sorted(candidates):
            hp = _parse_crinacle_tsv(tsv_path, reviewer)
            if hp:
                print(f"  [{os.path.relpath(tsv_path, reviewer_root)}] {len(hp)} fones")
                all_hp.extend(hp)
        return all_hp

    # --- Try /data/ subfolder first (Layouts A & B) ---
    data_dir = os.path.join(reviewer_root, "data")
    if os.path.isdir(data_dir):
        for cat_folder in sorted(os.listdir(data_dir)):
            cat_path = os.path.join(data_dir, cat_folder)
            if not os.path.isdir(cat_path):
                continue
            category = detect_category(cat_folder)
            sub_entries = os.listdir(cat_path)
            has_csv = any(e.endswith('.csv') for e in sub_entries)
            has_dirs = any(os.path.isdir(os.path.join(cat_path, e)) for e in sub_entries)

            if has_csv:
                # Layout A — flat
                prefix = f"{reviewer}/data/{cat_folder}"
                hp = scan_for_csvs(cat_path, reviewer, prefix, category)
                if hp:
                    print(f"  [{prefix}] {len(hp)} fones")
                all_hp.extend(hp)
            elif has_dirs:
                # Layout B — rig subfolder
                for rig in sorted(sub_entries):
                    rig_path = os.path.join(cat_path, rig)
                    if not os.path.isdir(rig_path):
                        continue
                    prefix = f"{reviewer}/data/{cat_folder}/{rig}"
                    hp = scan_for_csvs(rig_path, reviewer, prefix, category, rig=rig)
                    if hp:
                        print(f"  [{prefix}] {len(hp)} fones")
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
        prefix = f"{reviewer}/{folder}"
        hp = scan_for_csvs(folder_path, reviewer, prefix, category)
        if hp:
            print(f"  [{prefix}] {len(hp)} fones")
        all_hp.extend(hp)

    return all_hp


def _source_signature(source):
    return (
        source.get('reviewer'),
        source.get('path_prefix'),
        bool(source.get('nested')),
        source.get('rig') or None,
    )


def build_library():
    if not os.path.isdir(REPO_MEASUREMENTS):
        print("ERRO: autoeq_repo/measurements nao encontrado.")
        print("Execute: git clone https://github.com/jaakkopasanen/AutoEq autoeq_repo --depth 1")
        return []

    # Auto-discover all reviewer folders
    all_reviewers = sorted(
        d for d in os.listdir(REPO_MEASUREMENTS)
        if os.path.isdir(os.path.join(REPO_MEASUREMENTS, d))
    )
    print(f"Reviewers encontrados: {len(all_reviewers)}\n")

    # Group by headphone name while preserving every source entry.
    library = OrderedDict()
    for reviewer in all_reviewers:
        print(f"Indexando {reviewer}...")
        for source in discover_reviewer(reviewer):
            name = source['name']
            if name not in library:
                library[name] = {
                    'name': name,
                    'slug': source['slug'],
                    'category': source['category'],
                    'reviewer': source['reviewer'],
                    'path_prefix': source['path_prefix'],
                    'nested': source['nested'],
                    'sources': [],
                }
                if source.get('rig'):
                    library[name]['rig'] = source['rig']

            signature = _source_signature(source)
            existing = {
                _source_signature(s)
                for s in library[name]['sources']
            }
            if signature not in existing:
                source_entry = {
                    'reviewer': source['reviewer'],
                    'path_prefix': source['path_prefix'],
                    'nested': source['nested'],
                }
                if source.get('rig'):
                    source_entry['rig'] = source['rig']
                library[name]['sources'].append(source_entry)

    all_hp = list(library.values())

    os.makedirs('data', exist_ok=True)
    with open("data/headphone_library.json", "w", encoding="utf-8") as f:
        json.dump(all_hp, f, indent=2, ensure_ascii=False)

    print(f"\nTotal: {len(all_hp)} fones unicos -> data/headphone_library.json")
    return all_hp


if __name__ == "__main__":
    build_library()
