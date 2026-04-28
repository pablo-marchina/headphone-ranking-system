"""Squig.link collector.

This collector is intentionally defensive. It first tries to resolve a public
``phone_book*.json`` index (a structured public source) and only falls back to
HTML scraping if needed.
"""

from __future__ import annotations

import re
from typing import Any

from .base import BaseCollector


class SquigCollector(BaseCollector):
    source_name = "squig.link"

    DEFAULT_BASE_URLS = (
        "https://squig.link",
        "https://csi-zone.squig.link",
    )

    def is_available(self) -> bool:
        try:
            for base in self.DEFAULT_BASE_URLS:
                if self._get_text(base) is not None:
                    return True
        except Exception:
            return False
        return False

    def _candidate_indexes(self, base_url: str) -> list[str]:
        base = base_url.rstrip("/")
        return [
            f"{base}/phone_book.json",
            f"{base}/phone_book_hp.json",
            f"{base}/phone_book_buds.json",
        ]

    def _recursive_search(self, obj: Any, name: str) -> list[Any]:
        found: list[Any] = []
        if isinstance(obj, dict):
            if self._match_name(obj, name):
                found.append(obj)
            for value in obj.values():
                found.extend(self._recursive_search(value, name))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(self._recursive_search(item, name))
        elif isinstance(obj, str):
            if self._normalize_target(name) in self._normalize_target(obj):
                found.append(obj)
        return found

    def _extract_measurements_from_entry(self, entry: Any, source_label: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if isinstance(entry, dict):
            # Direct arrays or nested datasets.
            results.extend(self._coerce_measurement(entry, source_label))
            # Collect downloadable links and try those.
            for url in self._find_urls(entry):
                if url.lower().endswith(".csv"):
                    text = self._get_text(url)
                    if text:
                        results.extend(self._coerce_measurement(text, source_label))
                elif url.lower().endswith(".json"):
                    payload = self._get_json(url)
                    results.extend(self._coerce_measurement(payload, source_label))
        elif isinstance(entry, str):
            if entry.lower().endswith(".csv"):
                text = self._get_text(entry)
                if text:
                    results.extend(self._coerce_measurement(text, source_label))
            elif entry.lower().endswith(".json"):
                payload = self._get_json(entry)
                results.extend(self._coerce_measurement(payload, source_label))
        return results

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        try:
            base_urls = tuple(kwargs.get("base_urls") or self.DEFAULT_BASE_URLS)
            index_urls = kwargs.get("index_urls")
            if not index_urls:
                index_urls = [u for base in base_urls for u in self._candidate_indexes(base)]

            results: list[dict[str, Any]] = []
            target = self.normalize_name(name)

            for idx_url in index_urls:
                payload = self._get_json(idx_url)
                if payload is None:
                    continue
                matches = self._recursive_search(payload, name)
                # Sometimes a phone_book object is keyed by normalized name.
                if isinstance(payload, dict) and target in {self.normalize_name(k) for k in payload.keys() if isinstance(k, str)}:
                    matches.append(payload.get(next(k for k in payload.keys() if isinstance(k, str) and self.normalize_name(k) == target)))
                for match in matches:
                    results.extend(self._extract_measurements_from_entry(match, self.source_name))

                if results:
                    return self._dedupe_sources(results)

            # HTML fallback: look for embedded JSON / links on the base pages.
            for base in base_urls:
                html = self._get_text(base)
                if not html:
                    continue
                for blob in self._extract_json_blocks(html):
                    matches = self._recursive_search(blob, name)
                    for match in matches:
                        results.extend(self._extract_measurements_from_entry(match, self.source_name))
                if results:
                    return self._dedupe_sources(results)

            return []
        except Exception:
            return []

    @staticmethod
    def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        out = []
        for src in sources:
            freqs = tuple(np.round(src["freqs"], 6)) if "freqs" in src else None
            mags = tuple(np.round(src["mags"], 6)) if "mags" in src else None
            key = (freqs, mags, src.get("source"))
            if key in seen:
                continue
            seen.add(key)
            out.append(src)
        return out


try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None
