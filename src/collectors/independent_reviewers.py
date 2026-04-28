"""Independent reviewers with structured public data.

This file contains a generic collector that can read from reviewer-specific API
endpoints, GitHub CSVs, or explicit raw URLs. Only reviewers with accessible
structured sources should be registered here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseCollector


@dataclass
class ReviewerConfig:
    name: str
    api_urls: list[str] = field(default_factory=list)
    csv_urls: list[str] = field(default_factory=list)
    json_urls: list[str] = field(default_factory=list)
    github_owner: str | None = None
    github_repo: str | None = None
    github_paths: list[str] = field(default_factory=list)


class IndependentReviewerCollector(BaseCollector):
    source_name = "IndependentReviewers"

    # Intentionally conservative. Populate through kwargs or config when a real
    # structured source is known.
    REGISTRY: dict[str, ReviewerConfig] = {
        # Examples of future additions when verified structured sources exist:
        # "precogvision": ReviewerConfig(name="Precogvision", github_owner="...", github_repo="..."),
    }

    def is_available(self) -> bool:
        return bool(self.REGISTRY)

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        try:
            reviewer_key = kwargs.get("reviewer", "")
            config = self.REGISTRY.get(str(reviewer_key).lower()) if reviewer_key else None
            if config is None and reviewer_key:
                return []

            results: list[dict[str, Any]] = []
            csv_urls = kwargs.get("csv_urls") or (config.csv_urls if config else [])
            json_urls = kwargs.get("json_urls") or (config.json_urls if config else [])
            api_urls = kwargs.get("api_urls") or (config.api_urls if config else [])

            for url in csv_urls:
                if isinstance(url, str):
                    text = self._get_text(url)
                    if not text:
                        continue
                    parsed = self.parse_csv_text(text)
                    if parsed:
                        results.append(self.make_source(parsed[0], parsed[1], source=config.name if config else self.source_name))
            if results:
                return results

            for url in json_urls + api_urls:
                if not isinstance(url, str):
                    continue
                payload = self._get_json(url)
                results.extend(self._coerce_measurement(payload, config.name if config else self.source_name))
            if results:
                return results

            github_owner = kwargs.get("github_owner") or (config.github_owner if config else None)
            github_repo = kwargs.get("github_repo") or (config.github_repo if config else None)
            github_paths = kwargs.get("github_paths") or (config.github_paths if config else [])
            if github_owner and github_repo:
                # Reuse the same GitHub content API pattern as the other collectors.
                for path in github_paths or [""]:
                    api = f"https://api.github.com/repos/{github_owner}/{github_repo}/contents/{path}".rstrip("/")
                    payload = self._get_json(api)
                    if not isinstance(payload, list):
                        continue
                    target = self.normalize_name(name)
                    for item in payload:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") != "file":
                            continue
                        file_name = item.get("name", "")
                        if not isinstance(file_name, str):
                            continue
                        if target not in self.normalize_name(file_name):
                            continue
                        download_url = item.get("download_url")
                        if not isinstance(download_url, str):
                            continue
                        if download_url.lower().endswith(".csv"):
                            text = self._get_text(download_url)
                            if text:
                                parsed = self.parse_csv_text(text)
                                if parsed:
                                    results.append(self.make_source(parsed[0], parsed[1], source=config.name if config else self.source_name))
                        else:
                            payload2 = self._get_json(download_url)
                            results.extend(self._coerce_measurement(payload2, config.name if config else self.source_name))
                    if results:
                        return results

            return []
        except Exception:
            return []
