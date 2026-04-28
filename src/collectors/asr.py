"""Audio Science Review collector.

ASR has no public measurement API. This collector performs cautious forum
scraping and only returns data when it can infer structured FR / THD payloads.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from .base import BaseCollector


class ASRCollector(BaseCollector):
    source_name = "Audio Science Review"

    BASE_URL = "https://www.audiosciencereview.com/forum/index.php"

    def is_available(self) -> bool:
        return self._get_text(self.BASE_URL) is not None

    def _search_urls(self, name: str) -> list[str]:
        q = quote_plus(name)
        # XenForo search paths vary; probe the generic forum search endpoint.
        return [
            f"{self.BASE_URL}?search/{q}/",
            f"{self.BASE_URL}?search/search&keywords={q}",
            f"{self.BASE_URL}?search/1/?q={q}",
        ]

    def _candidate_thread_links(self, html: str) -> list[str]:
        links: list[str] = []
        if not html:
            return links
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not isinstance(href, str):
                continue
            low = href.lower()
            if any(key in low for key in ("/threads/", "review", "headphone")):
                links.append(urljoin(self.BASE_URL, href))
        for match in re.finditer(r'https?://[^\"\'\s>]+', html):
            url = match.group(0)
            if any(key in url.lower() for key in ("/threads/", "review")):
                links.append(url)
        deduped = []
        seen = set()
        for link in links:
            if link not in seen:
                deduped.append(link)
                seen.add(link)
        return deduped

    def _extract_measurements(self, html: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not html:
            return results
        for blob in self._extract_json_blocks(html):
            results.extend(self._coerce_measurement(blob, self.source_name))
        soup = BeautifulSoup(html, "html.parser")
        # Tables on some review pages can contain structured frequency / THD rows.
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) >= 2:
                    rows.append(cells[:2])
            if rows:
                parsed = self.parse_csv_text("\n".join(",".join(r) for r in rows))
                if parsed:
                    results.append(self.make_source(parsed[0], parsed[1], source=self.source_name))
        # Downloadable assets referenced in the page.
        for link in self._find_urls(html):
            if link.lower().endswith(".csv"):
                txt = self._get_text(link)
                if txt:
                    parsed = self.parse_csv_text(txt)
                    if parsed:
                        results.append(self.make_source(parsed[0], parsed[1], source=self.source_name))
            elif link.lower().endswith(".json"):
                payload = self._get_json(link)
                results.extend(self._coerce_measurement(payload, self.source_name))
        return results

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]]:
        try:
            results: list[dict[str, Any]] = []
            explicit_urls = kwargs.get("urls") or []
            for url in explicit_urls:
                if isinstance(url, str):
                    html = self._get_text(url)
                    if html:
                        results.extend(self._extract_measurements(html))
            if results:
                return results

            for search_url in self._search_urls(name):
                html = self._get_text(search_url)
                if not html:
                    continue
                for link in self._candidate_thread_links(html):
                    # Gentle filter: keep links that look related to the target.
                    if self.normalize_name(name) not in self.normalize_name(link):
                        # Still worth checking, because XenForo search pages may not include exact names.
                        pass
                    page = self._get_text(link)
                    if not page:
                        continue
                    results.extend(self._extract_measurements(page))
                if results:
                    return results
            return []
        except Exception:
            return []
