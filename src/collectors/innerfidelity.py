"""InnerFidelity archive collector.

The original InnerFidelity site is retired; this collector therefore supports
GitHub-hosted CSV archives and any explicit raw URLs you pass in via kwargs.
"""

from __future__ import annotations

from typing import Any

from .base import BaseCollector


class InnerFidelityCollector(BaseCollector):
    source_name = "InnerFidelity"

    def is_available(self) -> bool:
        # This archive is only considered available when a configured source or
        # a GitHub contents API endpoint responds.
        return False

    def _github_contents(self, owner: str, repo: str, path: str = "") -> list[dict[str, Any]]:
        api = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}".rstrip("/")
        payload = self._get_json(api)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _collect_csv_from_url(self, url: str, source_label: str) -> list[dict[str, Any]]:
        text = self._get_text(url)
        if not text:
            return []
        parsed = self.parse_csv_text(text)
        if not parsed:
            return []
        return [self.make_source(parsed[0], parsed[1], source=source_label)]

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        try:
            results: list[dict[str, Any]] = []
            target = self.normalize_name(name)

            # Explicit URLs supplied by the pipeline/config take precedence.
            for url in kwargs.get("csv_urls", []) or []:
                if isinstance(url, str):
                    results.extend(self._collect_csv_from_url(url, self.source_name))
            if results:
                return results

            for url in kwargs.get("json_urls", []) or []:
                payload = self._get_json(url) if isinstance(url, str) else None
                if payload is not None:
                    results.extend(self._coerce_measurement(payload, self.source_name))
            if results:
                return results

            # GitHub repository probing: default to the repo referenced in the plan.
            owner = kwargs.get("github_owner", "markalex")
            repo = kwargs.get("github_repo", "innerfidelity")
            search_roots = kwargs.get("github_paths") or [""]
            file_exts = (".csv", ".json", ".txt")

            for root in search_roots:
                try:
                    items = self._github_contents(owner, repo, root)
                except Exception:
                    items = []
                for item in items:
                    if item.get("type") == "file":
                        name_on_disk = item.get("name", "")
                        if not isinstance(name_on_disk, str):
                            continue
                        if target in self.normalize_name(name_on_disk) and name_on_disk.lower().endswith(file_exts):
                            download_url = item.get("download_url")
                            if isinstance(download_url, str):
                                if name_on_disk.lower().endswith(".csv"):
                                    results.extend(self._collect_csv_from_url(download_url, self.source_name))
                                else:
                                    payload = self._get_json(download_url)
                                    results.extend(self._coerce_measurement(payload, self.source_name))
                    elif item.get("type") == "dir":
                        # Recurse one level at a time.
                        sub_items = self._github_contents(owner, repo, item.get("path", ""))
                        for sub in sub_items:
                            if sub.get("type") != "file":
                                continue
                            n = sub.get("name", "")
                            if isinstance(n, str) and target in self.normalize_name(n) and n.lower().endswith(file_exts):
                                download_url = sub.get("download_url")
                                if isinstance(download_url, str):
                                    if n.lower().endswith(".csv"):
                                        results.extend(self._collect_csv_from_url(download_url, self.source_name))
                                    else:
                                        payload = self._get_json(download_url)
                                        results.extend(self._coerce_measurement(payload, self.source_name))
                if results:
                    return results

            # As a last resort, allow direct URLs on the kwargs.
            for url in kwargs.get("urls", []) or []:
                if not isinstance(url, str):
                    continue
                if url.lower().endswith(".csv"):
                    results.extend(self._collect_csv_from_url(url, self.source_name))
                else:
                    payload = self._get_json(url)
                    results.extend(self._coerce_measurement(payload, self.source_name))
                if results:
                    return results

            return []
        except Exception:
            return []
