"""Headphones.com / Revel collector.

The public site is scraped opportunistically. The collector searches for
candidate review/product pages, then tries to extract structured measurement
payloads from HTML, JSON-LD, or downloadable assets.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from .base import BaseCollector


class HeadphonesComCollector(BaseCollector):
    source_name = "Headphones.com"

    BASE_URL = "https://headphones.com"

    def is_available(self) -> bool:
        return self._get_text(self.BASE_URL) is not None

    def _search_urls(self, name: str) -> list[str]:
        slug = quote_plus(name)
        return [
            f"{self.BASE_URL}/search?q={slug}",
            f"{self.BASE_URL}/search?type=product,article&q={slug}",
        ]

    def _extract_candidate_links(self, html: str) -> list[str]:
        links: list[str] = []
        if not html:
            return links
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not isinstance(href, str):
                continue
            if any(k in href.lower() for k in ("review", "blog", "products", "product", "headphone")):
                links.append(urljoin(self.BASE_URL, href))
        # Also look for plain URLs in the HTML.
        for match in re.finditer(r'https?://[^\"\'\s>]+', html):
            links.append(match.group(0))
        deduped = []
        seen = set()
        for link in links:
            if link not in seen:
                deduped.append(link)
                seen.add(link)
        return deduped

    def _extract_from_page(self, url: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        html = self._get_text(url)
        if not html:
            return results
        for blob in self._extract_json_blocks(html):
            results.extend(self._coerce_measurement(blob, self.source_name))
        # Downloadable assets linked from the page.
        for candidate in self._find_urls(html):
            if isinstance(candidate, str) and candidate.lower().endswith((".csv", ".json")):
                if candidate.lower().endswith(".csv"):
                    txt = self._get_text(candidate)
                    if txt:
                        parsed = self.parse_csv_text(txt)
                        if parsed:
                            results.append(self.make_source(parsed[0], parsed[1], source=self.source_name))
                else:
                    payload = self._get_json(candidate)
                    results.extend(self._coerce_measurement(payload, self.source_name))
        return results

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        try:
            results: list[dict[str, Any]] = []
            explicit_urls = kwargs.get("urls") or []
            for url in explicit_urls:
                if not isinstance(url, str):
                    continue
                results.extend(self._extract_from_page(url))
            if results:
                return results

            for search_url in self._search_urls(name):
                html = self._get_text(search_url)
                if not html:
                    continue
                for link in self._extract_candidate_links(html):
                    if self.normalize_name(name) not in self.normalize_name(link):
                        # keep broad matching, but prefer the exact headphone name.
                        pass
                    results.extend(self._extract_from_page(link))
                if results:
                    return results

            return []
        except Exception:
            return []
