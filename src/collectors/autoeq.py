"""
src/collectors/autoeq.py — Local disk reader for AutoEQ measurements.

Reads CSVs from a local clone of https://github.com/jaakkopasanen/AutoEq
Expected location: <project_root>/autoeq_repo/measurements/

Run once to clone:
    git clone https://github.com/jaakkopasanen/AutoEq autoeq_repo --depth 1
"""

import os
import numpy as np
from scipy.interpolate import interp1d

# Two levels up from src/collectors/ → project root → autoeq_repo/measurements
LOCAL_REPO = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "autoeq_repo", "measurements"
))


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _read(path):
    """Return file text or None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _parse_csv(text):
    """
    Parse a two-column (freq, magnitude) CSV.
    Returns (freqs_array, mags_array) or None if too few valid rows.
    Deduplicates frequencies and sorts ascending.
    """
    rows = []
    for line in text.strip().splitlines():
        p = line.split(",")
        if len(p) < 2:
            continue
        try:
            rows.append((float(p[0]), float(p[1])))
        except ValueError:
            continue
    if len(rows) < 10:
        return None
    arr          = np.array(rows)
    arr          = arr[np.argsort(arr[:, 0])]
    _, idx       = np.unique(arr[:, 0], return_index=True)
    return arr[idx, 0], arr[idx, 1]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_folder(path_prefix, headphone_name, nested):
    """
    Build the absolute path to the folder that contains the measurement CSV(s).

    nested=False  →  LOCAL_REPO / path_prefix /             (CSV lives here directly)
    nested=True   →  LOCAL_REPO / path_prefix / {name} /    (each headphone has subfolder)

    Example (nested=True):
        path_prefix = "oratory1990/data/over-ear"
        name        = "Sennheiser HD 600"
        result      = .../autoeq_repo/measurements/oratory1990/data/over-ear/Sennheiser HD 600/
    """
    if nested:
        return os.path.join(LOCAL_REPO, path_prefix, headphone_name)
    else:
        return os.path.join(LOCAL_REPO, path_prefix)


# ---------------------------------------------------------------------------
# Source fetching
# ---------------------------------------------------------------------------

def _try_fetch(path_prefix, name, nested, sources, label):
    """
    Try to load L+R pair, falling back to mono CSV.
    Appends a source dict to `sources` if successful.
    """
    folder = _resolve_folder(path_prefix, name, nested)

    # Attempt L + R pair
    l_text = _read(os.path.join(folder, f"{name} L.csv"))
    r_text = _read(os.path.join(folder, f"{name} R.csv"))

    if l_text and r_text:
        left  = _parse_csv(l_text)
        right = _parse_csv(r_text)
        if left and right:
            # Align right channel to left channel's frequency grid
            ir   = interp1d(right[0], right[1], bounds_error=False,
                            fill_value=(right[1][0], right[1][-1]))
            r_al = ir(left[0])
            sources.append({
                'freqs':      left[0],
                'mags':       (left[1] + r_al) / 2.0,
                'left_mags':  left[1],
                'right_mags': r_al,
                'source':     label,
            })
            return

    # Fallback: mono CSV
    m_text = _read(os.path.join(folder, f"{name}.csv"))
    if m_text:
        mono = _parse_csv(m_text)
        if mono:
            sources.append({
                'freqs':      mono[0],
                'mags':       mono[1],
                'left_mags':  mono[1],
                'right_mags': mono[1],
                'source':     label,
            })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_autoeq_data(headphone_name, library_entry=None):
    """
    Load FR measurement(s) for a headphone from the local AutoEQ clone.

    Parameters
    ----------
    headphone_name : str
        Exact name as it appears in headphone_library.json (and as the CSV filename).

    library_entry : dict | None
        Entry from headphone_library.json.  Expected keys:
            path_prefix  — relative path under LOCAL_REPO to measurement folder
                           e.g. "oratory1990/data/over-ear"
            nested       — bool. True = CSV is inside its own subfolder named
                           after the headphone. False = CSV is directly in path_prefix.
            reviewer     — used only for the log label.
            category     — used only for the log label.

        When None, falls back to oratory1990/data/over-ear (non-nested).

    Returns
    -------
    list of source dicts, each with keys:
        freqs, mags, left_mags, right_mags, source
    Empty list if no data found.
    """
    sources = []

    if library_entry:
        prefix = library_entry.get('path_prefix', '')
        nested = library_entry.get('nested', False)
        label  = (f"{library_entry.get('reviewer', '?')}/"
                  f"{library_entry.get('category', '?')}")
        if prefix:
            _try_fetch(prefix, headphone_name, nested, sources, label)
        else:
            # Malformed library entry — try common fallback paths
            for fallback_prefix, fb_nested in [
                ("oratory1990/data/over-ear", False),
                ("oratory1990/data/in-ear",   False),
            ]:
                _try_fetch(fallback_prefix, headphone_name, fb_nested,
                           sources, f"fallback/{fallback_prefix}")
                if sources:
                    break
    else:
        # Called without library entry (e.g. from main.py)
        _try_fetch("oratory1990/data/over-ear", headphone_name, False,
                   sources, "oratory1990/over-ear")

    if sources:
        tags = [s['source'] for s in sources]
        print(f"  [AutoEQ] '{headphone_name}': {len(sources)} fonte(s) — {tags}")
    else:
        print(f"  [AutoEQ] Sem dados locais para '{headphone_name}'")

    return sources