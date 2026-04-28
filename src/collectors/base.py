"""Shared base class and parsing helpers for headphone data collectors.

Every collector in this phase must inherit from :class:`BaseCollector` and must
never let network or parsing failures escape the public ``fetch`` method.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import numpy as np
import requests

DEFAULT_TIMEOUT = 20
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


@dataclass(frozen=True)
class SourceData:
    freqs: np.ndarray
    mags: np.ndarray
    left_mags: np.ndarray
    right_mags: np.ndarray
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "freqs": self.freqs,
            "mags": self.mags,
            "left_mags": self.left_mags,
            "right_mags": self.right_mags,
            "source": self.source,
        }


class BaseCollector(ABC):
    """Base class for any external-data collector.

    Public methods must return lists and never raise exceptions on network or
    parsing failure. Subclasses can accept arbitrary keyword arguments so they
    stay pluggable with future pipeline changes.
    """

    source_name: str = "base"

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT):
        self.session = session or requests.Session()
        self.timeout = timeout

    @abstractmethod
    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------
    def _request(self, url: str, *, method: str = "GET", **kwargs) -> Optional[requests.Response]:
        try:
            request_kwargs = {
                "timeout": kwargs.pop("timeout", self.timeout),
                "headers": {**DEFAULT_HEADERS, **kwargs.pop("headers", {})},
                **kwargs,
            }
            response = self.session.request(method, url, **request_kwargs)
            response.raise_for_status()
            return response
        except Exception:
            return None

    def _get_text(self, url: str, **kwargs) -> Optional[str]:
        response = self._request(url, **kwargs)
        if response is None:
            return None
        try:
            response.encoding = response.encoding or "utf-8"
            return response.text
        except Exception:
            return None

    def _get_json(self, url: str, **kwargs) -> Any:
        response = self._request(url, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except Exception:
            try:
                return json.loads(response.text)
            except Exception:
                return None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_name(name: str) -> str:
        text = name.lower().strip()
        text = text.replace("&", " and ")
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def slugify(name: str) -> str:
        text = BaseCollector.normalize_name(name)
        return text.replace(" ", "-")

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                if math.isnan(float(value)):
                    return None
                return float(value)
            text = str(value).strip().replace(",", ".")
            if text == "":
                return None
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if not match:
                return None
            return float(match.group(0))
        except Exception:
            return None

    @classmethod
    def parse_csv_text(cls, text: str) -> Optional[tuple[np.ndarray, np.ndarray]]:
        try:
            rows: list[tuple[float, float]] = []
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                if len(row) < 2:
                    continue
                f = cls._safe_float(row[0])
                m = cls._safe_float(row[1])
                if f is None or m is None:
                    continue
                rows.append((f, m))
            if len(rows) < 8:
                return None
            arr = np.asarray(rows, dtype=float)
            order = np.argsort(arr[:, 0])
            arr = arr[order]
            uniq_freqs, uniq_idx = np.unique(arr[:, 0], return_index=True)
            arr = arr[np.sort(uniq_idx)]
            return arr[:, 0], arr[:, 1]
        except Exception:
            return None

    @staticmethod
    def merge_lr(
        left_freqs: np.ndarray,
        left_mags: np.ndarray,
        right_freqs: np.ndarray,
        right_mags: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        try:
            from scipy.interpolate import interp1d

            interp = interp1d(
                right_freqs,
                right_mags,
                bounds_error=False,
                fill_value=(float(right_mags[0]), float(right_mags[-1])),
            )
            aligned_right = np.asarray(interp(left_freqs), dtype=float)
            return (
                np.asarray(left_freqs, dtype=float),
                np.asarray(left_mags, dtype=float),
                np.asarray(left_freqs, dtype=float),
                aligned_right,
            )
        except Exception:
            # Fallback: use the overlap of both arrays with interpolation-free slicing.
            n = min(len(left_freqs), len(right_freqs))
            if n == 0:
                return left_freqs, left_mags, right_freqs, right_mags
            return (
                np.asarray(left_freqs[:n], dtype=float),
                np.asarray(left_mags[:n], dtype=float),
                np.asarray(right_freqs[:n], dtype=float),
                np.asarray(right_mags[:n], dtype=float),
            )

    def make_source(
        self,
        freqs: np.ndarray,
        mags: np.ndarray,
        *,
        left_mags: Optional[np.ndarray] = None,
        right_mags: Optional[np.ndarray] = None,
        source: str,
    ) -> dict[str, Any]:
        freqs = np.asarray(freqs, dtype=float)
        mags = np.asarray(mags, dtype=float)
        left = np.asarray(left_mags if left_mags is not None else mags, dtype=float)
        right = np.asarray(right_mags if right_mags is not None else mags, dtype=float)
        return SourceData(freqs=freqs, mags=mags, left_mags=left, right_mags=right, source=source).as_dict()

    @staticmethod
    def _pick_string(value: Any) -> Optional[str]:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _iter_strings(self, obj: Any) -> Iterable[str]:
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, dict):
            for value in obj.values():
                yield from self._iter_strings(value)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                yield from self._iter_strings(item)

    def _find_urls(self, obj: Any) -> list[str]:
        urls: list[str] = []
        for text in self._iter_strings(obj):
            if text.startswith("http://") or text.startswith("https://"):
                urls.append(text)
            elif text.lower().endswith((".csv", ".json", ".txt")):
                urls.append(text)
        deduped = []
        seen = set()
        for url in urls:
            if url not in seen:
                deduped.append(url)
                seen.add(url)
        return deduped

    def _coerce_measurement(self, payload: Any, source: str) -> list[dict[str, Any]]:
        """Try to coerce many common payload shapes into the project contract."""
        results: list[dict[str, Any]] = []

        def add_from_arrays(freqs: Any, mags: Any, left: Any = None, right: Any = None):
            try:
                f = np.asarray(freqs, dtype=float)
                m = np.asarray(mags, dtype=float)
                if f.size < 8 or m.size < 8:
                    return
                if left is None:
                    left_arr = m
                else:
                    left_arr = np.asarray(left, dtype=float)
                if right is None:
                    right_arr = m
                else:
                    right_arr = np.asarray(right, dtype=float)
                n = min(len(f), len(m), len(left_arr), len(right_arr))
                if n < 8:
                    return
                results.append(
                    self.make_source(
                        f[:n],
                        m[:n],
                        left_mags=left_arr[:n],
                        right_mags=right_arr[:n],
                        source=source,
                    )
                )
            except Exception:
                return

        try:
            if payload is None:
                return []
            if isinstance(payload, str):
                parsed = self.parse_csv_text(payload)
                if parsed:
                    add_from_arrays(parsed[0], parsed[1])
                return results
            if isinstance(payload, dict):
                # Common explicit shapes
                for freq_key, mag_key in [
                    ("freqs", "mags"),
                    ("frequencies", "magnitudes"),
                    ("frequency", "magnitude"),
                    ("x", "y"),
                ]:
                    if freq_key in payload and mag_key in payload:
                        add_from_arrays(payload[freq_key], payload[mag_key], payload.get("left_mags"), payload.get("right_mags"))
                        if results:
                            return results
                # Nested series shapes
                for key in ("series", "data", "measurements", "points", "response"):
                    if key in payload:
                        nested = payload[key]
                        if isinstance(nested, list):
                            for item in nested:
                                results.extend(self._coerce_measurement(item, source))
                            if results:
                                return results
                # Search recursively for arrays
                if any(isinstance(v, (list, tuple)) for v in payload.values()):
                    arrays = {k: v for k, v in payload.items() if isinstance(v, (list, tuple))}
                    keys = list(arrays)
                    if len(keys) >= 2:
                        add_from_arrays(arrays[keys[0]], arrays[keys[1]])
                        if results:
                            return results
                # Search urls in payload if it references downloadable data.
                for url in self._find_urls(payload):
                    if url.lower().endswith(".csv"):
                        txt = self._get_text(url)
                        if txt:
                            parsed = self.parse_csv_text(txt)
                            if parsed:
                                add_from_arrays(parsed[0], parsed[1])
                    elif url.lower().endswith(".json"):
                        nested = self._get_json(url)
                        if nested is not None:
                            results.extend(self._coerce_measurement(nested, source))
                return results
            if isinstance(payload, list):
                # List of [freq, mag] pairs
                if payload and all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in payload):
                    try:
                        arr = np.asarray([[item[0], item[1]] for item in payload], dtype=float)
                        add_from_arrays(arr[:, 0], arr[:, 1])
                        if results:
                            return results
                    except Exception:
                        pass
                for item in payload:
                    results.extend(self._coerce_measurement(item, source))
                return results
        except Exception:
            return []

        return results

    def _extract_json_blocks(self, html: str) -> list[Any]:
        candidates: list[Any] = []
        if not html:
            return candidates
        # JSON-LD and obvious embedded JSON blobs.
        patterns = [
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__NEXT_DATA__\s*=\s*({.*?});',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE | re.DOTALL):
                blob = match.group(1).strip()
                try:
                    candidates.append(json.loads(blob))
                except Exception:
                    # very defensive, the blobs may contain single quotes or JS trailing commas.
                    try:
                        blob = re.sub(r",\s*([}\]])", r"\1", blob)
                        candidates.append(json.loads(blob))
                    except Exception:
                        continue
        return candidates

    @staticmethod
    def _normalize_target(name: str) -> str:
        return BaseCollector.normalize_name(name)

    def _match_name(self, candidate: Any, name: str) -> bool:
        target = self._normalize_target(name)
        if isinstance(candidate, str):
            return target in self._normalize_target(candidate)
        if isinstance(candidate, dict):
            hay = " ".join(str(v) for v in candidate.values() if isinstance(v, (str, int, float)))
            return target in self._normalize_target(hay)
        return False
