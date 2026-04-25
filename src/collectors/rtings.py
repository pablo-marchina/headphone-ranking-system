import requests
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; headphone-ranking-bot/1.0)'}


def _parse_percent(text):
    """Extract the first float followed by % from a string."""
    m = re.search(r'([\d.]+)\s*%', text)
    return float(m.group(1)) if m else None


def fetch_rtings_metrics(headphone_slug):
    """
    Attempts to scrape THD and driver-matching values from RTINGS.
    headphone_slug: e.g. "sennheiser/hd-600"

    Returns dict {'thd': float, 'matching': float} or None on failure.
    THD is reported as percentage (e.g. 0.1 for 0.1 %).
    matching is reported as dB std-dev between channels.

    Note: RTINGS does not provide a public API. This scraper targets their
    structured review pages and may break if their layout changes.
    Falls back to conservative defaults rather than crashing the pipeline.
    """
    url = f"https://www.rtings.com/headphones/reviews/{headphone_slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, 'html.parser')

        # --- THD ---
        # RTINGS embeds test scores in elements like:
        # <div class="test-result">...</div>  containing the label and value
        thd_value     = 0.3   # Conservative default (audible but not bad)
        matching_value = 1.0  # 1 dB default (acceptable)

        all_text = soup.get_text(separator=' ')

        # Try to extract THD % from page text
        thd_match = re.search(
            r'(?:Total Harmonic Distortion|THD)[^\d]*([\d.]+)\s*%',
            all_text, re.IGNORECASE
        )
        if thd_match:
            thd_value = float(thd_match.group(1))

        # Try to extract driver matching std-dev
        match_match = re.search(
            r'(?:Driver Matching|Channel Matching)[^\d]*([\d.]+)\s*dB',
            all_text, re.IGNORECASE
        )
        if match_match:
            matching_value = float(match_match.group(1))

        return {'thd': thd_value, 'matching': matching_value}

    except Exception as e:
        print(f"  [RTINGS] Erro ao raspar '{headphone_slug}': {e}")
        return None