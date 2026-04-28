"""Compatibility wrapper for older imports.

New code should import from src.preprocessing.loudness_model.
"""

from .loudness_model import generate_loudness_grid, interpolate_to_erb, interpolate_to_loudness_grid

__all__ = ["generate_loudness_grid", "interpolate_to_erb", "interpolate_to_loudness_grid"]
