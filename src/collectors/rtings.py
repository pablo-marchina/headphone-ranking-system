
"""RTINGS review-page parser for headphone metrics."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

import numpy as np
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; headphone-ranking-bot/1.0)"}
_NUM = r"([-+]?(?:\d+\.\d+|\d+))"

_METRIC_PATTERNS = {
    "thd": [
        rf"(?:Total Harmonic Distortion|THD)(?!\+N)[^\d]{{0,40}}{_NUM}\s*%",
    ],
    "thd_plus_n": [
        rf"(?:Total Harmonic Distortion\s*\+\s*N|THD\+N|THD\s*\+\s*N)[^\d]{{0,40}}{_NUM}\s*%",
    ],
    "imd": [
        rf"(?:Intermodulation Distortion|IMD)[^\d]{{0,40}}{_NUM}\s*%",
        rf"(?:Intermodulation Distortion|IMD)[^\d]{{0,40}}{_NUM}\s*dB",
    ],
    "sensitivity_db_mw": [
        rf"(?:Sensitivity|Efficiency)[^\d]{{0,40}}{_NUM}\s*dB\s*(?:SPL\s*)?/\s*mW",
        rf"(?:Sensitivity|Efficiency)[^\d]{{0,40}}{_NUM}\s*dB\s*/\s*mW",
    ],
    "impedance_ohms": [
        rf"(?:Impedance)[^\d]{{0,40}}{_NUM}\s*(?:ohms?|Ω)",
    ],
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)) and np.isfinite(float(value)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None
    except Exception:
        return None


def _search_patterns(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = _safe_float(match.group(1))
            if value is not None:
                return value
    return None


def _iter_script_payloads(soup: BeautifulSoup) -> Iterable[Any]:
    for script in soup.find_all("script"):
        text = script.string or script.get_text(" ", strip=False) or ""
        text = text.strip()
        if not text:
            continue

        if script.get("type") == "application/ld+json":
            try:
                yield json.loads(text)
            except Exception:
                pass
            continue

        if text.startswith("{") or text.startswith("["):
            try:
                yield json.loads(text)
                continue
            except Exception:
                pass

        if "__NEXT_DATA__" in text:
            m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', str(script), flags=re.DOTALL | re.IGNORECASE)
            if m:
                try:
                    yield json.loads(m.group(1))
                except Exception:
                    pass


def _iter_nested_values(obj: Any, key_tokens: tuple[str, ...]) -> Iterable[Any]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if any(token in key_l for token in key_tokens):
                yield value
            yield from _iter_nested_values(value, key_tokens)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_nested_values(item, key_tokens)


def _coerce_curve_points(value: Any) -> Optional[list[tuple[float, float]]]:
    points: list[tuple[float, float]] = []

    if isinstance(value, dict):
        for key in ("data", "series", "points", "values"):
            if key in value:
                coerced = _coerce_curve_points(value[key])
                if coerced is not None:
                    return coerced

        x = None
        y = None
        for key, val in value.items():
            lk = str(key).lower()
            if x is None and any(token in lk for token in ("x", "freq", "frequency", "hz")):
                x = val
            if y is None and any(token in lk for token in ("y", "value", "gain", "magnitude", "mag", "db")):
                y = val
        if x is not None and y is not None:
            try:
                x_arr = np.asarray(x, dtype=float)
                y_arr = np.asarray(y, dtype=float)
                if x_arr.shape == y_arr.shape and x_arr.size >= 2:
                    order = np.argsort(x_arr)
                    return [(float(x_arr[i]), float(y_arr[i])) for i in order]
            except Exception:
                pass

    if isinstance(value, list):
        if not value:
            return []
        if all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in value):
            for item in value:
                x = _safe_float(item[0])
                y = _safe_float(item[1])
                if x is not None and y is not None:
                    points.append((x, y))
        elif all(isinstance(item, dict) for item in value):
            for item in value:
                x = None
                y = None
                for key, val in item.items():
                    lk = str(key).lower()
                    if x is None and any(token in lk for token in ("x", "freq", "frequency", "hz")):
                        x = _safe_float(val)
                    if y is None and any(token in lk for token in ("y", "value", "gain", "magnitude", "mag", "db")):
                        y = _safe_float(val)
                if x is not None and y is not None:
                    points.append((x, y))
        if points:
            points = sorted(points, key=lambda p: p[0])
            return points

    return None


def _find_impedance_curve(soup: BeautifulSoup) -> list[tuple[float, float]]:
    for payload in _iter_script_payloads(soup):
        for candidate in _iter_nested_values(payload, ("impedance",)):
            curve = _coerce_curve_points(candidate)
            if curve:
                return curve
    return []


def _parse_page_metrics(text: str) -> dict[str, Any]:
    return {
        "thd": _search_patterns(text, _METRIC_PATTERNS["thd"]),
        "thd_plus_n": _search_patterns(text, _METRIC_PATTERNS["thd_plus_n"]),
        "imd": _search_patterns(text, _METRIC_PATTERNS["imd"]),
        "sensitivity_db_mw": _search_patterns(text, _METRIC_PATTERNS["sensitivity_db_mw"]),
        "impedance_ohms": _search_patterns(text, _METRIC_PATTERNS["impedance_ohms"]),
    }


def fetch_rtings_metrics(headphone_slug):
    """Fetch RTINGS metrics for a headphone slug.

    Returns None on network/parsing failure or when no useful metric could be
    extracted. When parsing succeeds, the returned dict can include:
        thd, thd_plus_n, imd, sensitivity_db_mw, impedance_ohms, impedance_curve
    """
    url = f"https://www.rtings.com/headphones/reviews/{headphone_slug}"
    try:
        import requests

        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        metrics = _parse_page_metrics(text)
        metrics["impedance_curve"] = _find_impedance_curve(soup)

        has_numeric = any(metrics.get(key) is not None for key in ("thd", "thd_plus_n", "imd", "sensitivity_db_mw", "impedance_ohms"))
        has_curve = bool(metrics.get("impedance_curve"))
        if not has_numeric and not has_curve:
            return None

        return metrics
    except Exception:
        return None


class RTINGSCollector(BaseCollector):
    source_name = "rtings"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs):
        slug = kwargs.get("slug") or kwargs.get("headphone_slug") or self.slugify(name)
        metrics = fetch_rtings_metrics(slug)
        if not metrics:
            return []

        return [
            {
                "name": name,
                "source": self.source_name,
                "metrics": metrics,
            }
        ]
