import numpy as np
from scipy.interpolate import interp1d
from src.constants import MIN_FREQ, MAX_FREQ, hz_to_erb, erb_to_hz


def generate_erb_grid(min_f=MIN_FREQ, max_f=MAX_FREQ, num_points=500):
    """Uniform grid in ERB-rate space (Glasberg & Moore, 1990)."""
    erb_grid = np.linspace(hz_to_erb(min_f), hz_to_erb(max_f), num_points)
    return erb_to_hz(erb_grid)


def interpolate_to_erb(freqs, magnitudes, num_points=500):
    """
    Resample a frequency-response curve onto the ERB-rate grid.
    Uses linear interpolation in log-frequency; edge values are held
    constant (no extrapolation error at band limits).
    """
    erb_freqs = generate_erb_grid(num_points=num_points)
    interp = interp1d(
        freqs, magnitudes,
        kind='linear',
        bounds_error=False,
        fill_value=(magnitudes[0], magnitudes[-1])
    )
    return erb_freqs, interp(erb_freqs)