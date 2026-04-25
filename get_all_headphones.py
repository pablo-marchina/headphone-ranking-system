import os
import requests
import json

REVIEWERS = ["oratory1990", "crinacle", "Rtings"]

API_BASE = "https://api.github.com/repos/jaakkopasanen/AutoEq/contents/measurements"


def _auth_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return {"Authorization": f"token {token}"}
    return {}


def api_get(url):
    r = requests.get(url, headers=_auth_headers(), timeout=15)
    if r.status_code == 403:
        print("  Rate limit. Defina GITHUB_TOKEN.")
        return None
    return r.json() if r.status_code == 200 else None


def detect_category(folder_name):
    name = folder_name.lower()
    if "in-ear" in name or "iem" in name:
        return "in-ear"
    if "on-ear" in name:
        return "on-ear"
    return "over-ear"


def extract_csvs(items, reviewer, rig_folder, category):
    """Pull headphone entries from a list of GitHub API items."""
    result = []
    for item in items:
        if item['type'] == 'file' and item['name'].endswith('.csv'):
            name = item['name'][:-4]
            slug = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
            result.append({
                "name":       name,
                "slug":       slug,
                "reviewer":   reviewer,
                "rig_folder": rig_folder,
                "category":   category,
            })
    return result


def scan_folder(url, reviewer, rig_folder, category, depth=0):
    """
    Recursively scan a folder up to depth 1.
    - If it contains CSV files directly → return them.
    - If it contains subdirs (rig variants) → scan each subdir for CSVs.
    """
    items = api_get(url)
    if not items:
        return []

    csvs = extract_csvs(items, reviewer, rig_folder, category)
    if csvs:
        return csvs

    # No CSVs at this level — go one level deeper (rig subdirectories)
    if depth == 0:
        all_results = []
        for item in items:
            if item['type'] == 'dir':
                sub_rig = f"{rig_folder}/{item['name']}" if rig_folder else item['name']
                sub_cat = detect_category(item['name'])
                sub_results = scan_folder(
                    item['url'], reviewer, sub_rig, sub_cat, depth=1
                )
                if sub_results:
                    print(f"    [{reviewer}/{sub_rig}] {len(sub_results)} fones")
                all_results.extend(sub_results)
        return all_results

    return []


def discover_reviewer(reviewer):
    """
    Auto-discover the right base path for a reviewer.
    Tries /data/ first (oratory1990 style), then root level (crinacle/Rtings style).
    """
    # Strategy 1: measurements/{reviewer}/data/
    data_url = f"{API_BASE}/{reviewer}/data"
    subfolders = api_get(data_url)

    if subfolders and isinstance(subfolders, list):
        dirs = [i for i in subfolders if i['type'] == 'dir']
        if dirs:
            print(f"  [{reviewer}] Encontrado /data/ com {len(dirs)} subpasta(s)")
            all_headphones = []
            for sf in dirs:
                cat = detect_category(sf['name'])
                results = scan_folder(sf['url'], reviewer, sf['name'], cat)
                if results:
                    print(f"  [{reviewer}/{sf['name']}] {len(results)} fones")
                all_headphones.extend(results)
            return all_headphones

    # Strategy 2: measurements/{reviewer}/ directly (no /data/ subfolder)
    root_url = f"{API_BASE}/{reviewer}"
    root_items = api_get(root_url)
    if not root_items:
        print(f"  [{reviewer}] Sem acesso.")
        return []

    dirs = [i for i in root_items if i['type'] == 'dir'
            and i['name'] not in ('raw_data', 'resources', 'data')]

    if not dirs:
        print(f"  [{reviewer}] Nenhuma pasta de categoria encontrada.")
        return []

    print(f"  [{reviewer}] Sem /data/, escaneando raiz ({len(dirs)} pastas)...")
    all_headphones = []
    for sf in dirs:
        cat = detect_category(sf['name'])
        results = scan_folder(sf['url'], reviewer, sf['name'], cat)
        if results:
            print(f"  [{reviewer}/{sf['name']}] {len(results)} fones")
        all_headphones.extend(results)
    return all_headphones


def build_library():
    all_headphones = []
    seen = set()

    for reviewer in REVIEWERS:
        print(f"\nIndexando {reviewer}...")
        for h in discover_reviewer(reviewer):
            if h['name'] not in seen:
                all_headphones.append(h)
                seen.add(h['name'])

    os.makedirs('data', exist_ok=True)
    with open("data/headphone_library.json", "w", encoding="utf-8") as f:
        json.dump(all_headphones, f, indent=4, ensure_ascii=False)

    print(f"\nTotal: {len(all_headphones)} fones unicos -> data/headphone_library.json")
    return all_headphones


if __name__ == "__main__":
    build_library()