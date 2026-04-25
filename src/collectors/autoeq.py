import os
import requests
import numpy as np
from urllib.parse import quote
from scipy.interpolate import interp1d

BASE_RAW = "https://raw.githubusercontent.com/jaakkopasanen/AutoEq/master/measurements"


def _auth_headers():
    """
    Returns Authorization header if GITHUB_TOKEN is set.
    Without token: 60 req/hour. With token: 5000 req/hour.

    Set before running:
        set GITHUB_TOKEN=ghp_yourToken        (Windows CMD)
        export GITHUB_TOKEN=ghp_yourToken     (Linux/macOS)
    """
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return {"Authorization": f"token {token}"}
    return {}


def _get(url, timeout=10):
    try:
        r = requests.get(url, headers=_auth_headers(), timeout=timeout)
        if r.status_code == 403:
            print("  [AutoEQ] Rate limit. Defina GITHUB_TOKEN.")
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def _parse_csv(text):
    rows = []
    for line in text.strip().splitlines():
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    if len(rows) < 10:
        return None
    arr = np.array(rows)
    arr = arr[np.argsort(arr[:, 0])]
    _, idx = np.unique(arr[:, 0], return_index=True)
    return arr[idx, 0], arr[idx, 1]


def fetch_autoeq_data(headphone_name, library_entry=None):
    """
    Fetch RAW FR measurements for a headphone.

    If library_entry is provided (from headphone_library.json), it uses the
    exact reviewer + rig_folder recorded there — no guessing needed.

    Otherwise falls back to probing common paths.

    Returns list of source dicts:
        { freqs, mags, left_mags, right_mags, source }
    """
    sources = []
    enc = quote(headphone_name)

    # --- Primary path: use exact rig_folder from library ---
    if library_entry and library_entry.get('rig_folder'):
        reviewer   = library_entry['reviewer']
        rig_folder = quote(library_entry['rig_folder'])
        base = f"{BASE_RAW}/{reviewer}/data/{rig_folder}/{enc}"
        _try_fetch(base, f"{reviewer}/{library_entry['rig_folder']}", sources)

    # --- Fallback: probe oratory1990 over-ear (most common case) ---
    if not sources:
        base = f"{BASE_RAW}/oratory1990/data/over-ear/{enc}"
        _try_fetch(base, "oratory1990/over-ear", sources)

    if sources:
        tags = [s['source'] for s in sources]
        print(f"  [AutoEQ] '{headphone_name}': {len(sources)} fonte(s) — {tags}")
    else:
        print(f"  [AutoEQ] Sem dados para '{headphone_name}'")

    return sources


def _try_fetch(base_url, source_label, sources):
    """
    Try L+R pair first, then mono. Appends to sources list if found.
    """
    l_text = _get(f"{base_url} L.csv")
    r_text = _get(f"{base_url} R.csv")

    if l_text and r_text:
        left  = _parse_csv(l_text)
        right = _parse_csv(r_text)
        if left and right:
            interp_r  = interp1d(right[0], right[1],
                                 bounds_error=False,
                                 fill_value=(right[1][0], right[1][-1]))
            r_aligned = interp_r(left[0])
            sources.append({
                'freqs':       left[0],
                'mags':        (left[1] + r_aligned) / 2.0,
                'left_mags':   left[1],
                'right_mags':  r_aligned,
                'source':      source_label,
            })
            return

    mono_text = _get(f"{base_url}.csv")
    if mono_text:
        mono = _parse_csv(mono_text)
        if mono:
            sources.append({
                'freqs':       mono[0],
                'mags':        mono[1],
                'left_mags':   mono[1],
                'right_mags':  mono[1],
                'source':      source_label,
            })