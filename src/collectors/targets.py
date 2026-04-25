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
# IEM brand / keyword heuristics for automatic category detection
# Extend this list as the dataset grows.
# ---------------------------------------------------------------------------
_IEM_KEYWORDS = [
    'iem', 'in-ear', 'in ear',
    'kz ',  'cca ',  'trn ',  'blon', 'moondrop', 'truthear',
    'letshuoer', 'simgot', 'tin hifi', 'thieaudio', 'hifiman re',
    'etymotic', 'shure se', 'campfire', 'andromeda', 'solaris',
    'final e', 'ikko', 'tripowin', 'tangzu', 'dunu', 'fiio fd',
    'fiio fh', 'jabra evolve', '7hz',
]


def detect_category(headphone_name: str) -> str:
    """
    Returns 'in-ear' if the name matches known IEM brands/patterns,
    'over-ear' otherwise.  Used to select the correct Harman target.
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