import os
import numpy as np
from scipy.interpolate import interp1d

# src/collectors/autoeq.py está 2 níveis abaixo da raiz do projeto
# (src/collectors/ → src/ → raiz/)  portanto dois ".." chegam na raiz
LOCAL_REPO = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "autoeq_repo", "measurements"
))


def _parse_csv(text):
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
    arr = np.array(rows)
    arr = arr[np.argsort(arr[:, 0])]
    _, idx = np.unique(arr[:, 0], return_index=True)
    return arr[idx, 0], arr[idx, 1]


def _read(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _try_fetch(path_prefix, name, nested, sources, label):
    """
    nested=False → CSV está direto em LOCAL_REPO/path_prefix/
    nested=True  → CSV está em LOCAL_REPO/path_prefix/{name}/
    """
    if nested:
        folder = os.path.join(LOCAL_REPO, path_prefix, name)
    else:
        folder = os.path.join(LOCAL_REPO, path_prefix)

    l_path = os.path.join(folder, f"{name} L.csv")
    r_path = os.path.join(folder, f"{name} R.csv")
    m_path = os.path.join(folder, f"{name}.csv")

    l_text, r_text = _read(l_path), _read(r_path)
    if l_text and r_text:
        left, right = _parse_csv(l_text), _parse_csv(r_text)
        if left and right:
            ir   = interp1d(right[0], right[1], bounds_error=False,
                            fill_value=(right[1][0], right[1][-1]))
            r_al = ir(left[0])
            sources.append({
                'freqs':      left[0],
                'mags':       (left[1] + r_al) / 2,
                'left_mags':  left[1],
                'right_mags': r_al,
                'source':     label,
            })
            return

    m_text = _read(m_path)
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


def fetch_autoeq_data(headphone_name, library_entry=None):
    """
    Busca medições FR no clone local do AutoEQ.

    library_entry (do headphone_library.json) tem as chaves:
        path_prefix → caminho relativo a LOCAL_REPO até a pasta de medições
                      ex: "Auriculares Argentina/data/in-ear"
        nested      → bool — True se o CSV está dentro de uma subpasta com o nome do fone
        reviewer    → usado como label no log
        category    → usado como label no log
    """
    sources = []

    if library_entry:
        prefix = library_entry.get('path_prefix', '')
        nested = library_entry.get('nested', False)
        label  = f"{library_entry.get('reviewer', '?')}/{library_entry.get('category', '?')}"
        _try_fetch(prefix, headphone_name, nested, sources, label)
    else:
        _try_fetch("oratory1990/data/over-ear", headphone_name, False,
                   sources, "oratory1990/over-ear")

    if sources:
        print(f"  [AutoEQ] '{headphone_name}': {len(sources)} fonte(s) — local")
    else:
        print(f"  [AutoEQ] Sem dados para '{headphone_name}'")

    return sources