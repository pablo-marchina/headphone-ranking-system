import numpy as np

# ---------------------------------------------------------------------------
# Harman Over-Ear 2018 target — key breakpoints (dB re 1 kHz)
# ---------------------------------------------------------------------------
_OE_F = np.array([
    20,   30,   40,   50,   60,   80,   100,  150,  200,  300,
    500,  700,  1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000,
    10000, 12000, 16000, 20000
])
_OE_M = np.array([
    5.5,  5.8,  6.0,  6.2,  6.0,  5.8,  5.5,  4.0,  3.0,  1.5,
    0.5,  0.2,  0.0,  1.0,  2.5,  7.5,  10.5, 6.5,  0.5,  -4.5,
    -8.0, -12.0, -16.0, -20.0
])

# ---------------------------------------------------------------------------
# Harman In-Ear 2019 target — key breakpoints (dB re 1 kHz)
# ---------------------------------------------------------------------------
_IEM_F = np.array([
    20,   30,   40,   60,   80,   100,  150,  200,  300,  500,
    700,  1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000,
    12000, 16000, 20000
])
_IEM_M = np.array([
    4.0,  4.5,  5.0,  5.0,  5.0,  5.0,  4.0,  3.5,  2.0,  1.5,
    0.5,  0.0,  2.0,  4.5,  9.0,  9.5,  7.0,  2.0,  -3.0, -7.0,
    -12.0, -16.0, -20.0
])

# ---------------------------------------------------------------------------
# IEM keyword heuristic — used ONLY as fallback when category is not
# pre-classified by get_all_headphones.py (folder-derived).
#
# Priority in dataset_generator.py:
#   1. item['category']  ← from folder name (most reliable)
#   2. detect_category() ← keyword heuristic below (fallback only)
#
# Keep this list comprehensive anyway — it's used by main.py (single-fone
# evaluation) which doesn't always have a library_entry.
# ---------------------------------------------------------------------------
_IEM_KEYWORDS = [
    # Generic
    'iem', 'in-ear', 'in ear', 'earbud', 'earphone',
    # Chinese budget IEM brands (heavily represented in Crinacle)
    'kz ', 'cca ', 'trn ', 'blon', 'tin hifi', 'tin audio',
    'moondrop', 'truthear', 'letshuoer', 'simgot', 'tangzu',
    'thieaudio', 'tripowin', 'ikko', 'dunu', 'fiio fd', 'fiio fh',
    '7hz', 'hidizs', 'tanchjim', 'kinera', 'jadeaudio', 'rose technics',
    'bgvp', 'tfz', 'qkz', 'crin', 'faaeal', 'salnotes',
    # Mid-range IEM brands
    'campfire', 'andromeda', 'solaris', 'ara ', 'holocene', 'honeydew',
    'final e', 'final audio e', 'final audio f', 'final audio b',
    'hidition', 'viento', 'meze rai', 'noble audio',
    '64 audio', 'vision ears', 'empire ears', 'custom art',
    'inear prophile', 'er4', 'er2', 'er3',
    # Flagship IEM brands
    'hifiman re', 'etymotic', 'shure se', 'westone',
    # Common model suffixes that almost always mean IEM
    'tws', 'true wireless', 'galaxy buds', 'airpods',
    'freebuds', 'linkbuds', 'wf-', 'liberty', 'momentum true',
]


def detect_category(headphone_name: str) -> str:
    """
    Keyword heuristic: returns 'in-ear' or 'over-ear'.

    IMPORTANT: in dataset_generator.py this is a FALLBACK only.
    The primary source of category is item['category'] from headphone_library.json,
    which is derived from the measurement folder name and is far more reliable.
    Use this function when no pre-classified category is available (e.g. main.py).
    """
    name_lower = headphone_name.lower()
    if any(k in name_lower for k in _IEM_KEYWORDS):
        return 'in-ear'
    return 'over-ear'


def get_harman_target(category: str = 'over-ear'):
    """
    Returns (freqs, mags) for the Harman target of the given category.
    'over-ear' and 'on-ear' → Harman OE 2018
    'in-ear'                → Harman IEM 2019
    """
    if category == 'in-ear':
        return _IEM_F.copy(), _IEM_M.copy()
    return _OE_F.copy(), _OE_M.copy()