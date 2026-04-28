"""MSRP USD × câmbio proxy collector.

Fetches the current USD/BRL rate from exchangerate-api.com and converts a
provided MSRP in USD into BRL. Returns None on request failure.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import BaseCollector

EXCHANGE_URL = "https://api.exchangerate-api.com/v4/latest/USD"


class MSRPProxyCollector(BaseCollector):
    source_name = "msrp_proxy"

    def is_available(self) -> bool:
        return True

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        msrp_usd = kwargs.get("msrp_usd", kwargs.get("msrp", kwargs.get("msrp_price")))
        usd = self._safe_float(msrp_usd)
        if usd is None or usd <= 0:
            return []

        data = self._get_json(EXCHANGE_URL)
        if data is None:
            return None

        try:
            rates = data.get("rates", {}) if isinstance(data, dict) else {}
            brl = self._safe_float(rates.get("BRL"))
            if brl is None or brl <= 0:
                return []
            price_brl = float(usd) * float(brl)
            return [{
                "price_brl": float(price_brl),
                "source": self.source_name,
                "title": f"MSRP USD {usd:.2f}",
                "url": EXCHANGE_URL,
            }]
        except Exception:
            return []
