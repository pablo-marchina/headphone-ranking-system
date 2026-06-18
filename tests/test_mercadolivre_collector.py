from __future__ import annotations

from types import SimpleNamespace

import dataset_generator
from src.collectors.mercadolivre import MercadoLivrePriceCollector


class DummyResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ("" if payload is None else str(payload))

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_mercadolivre_reads_only_fixed_env_vars(monkeypatch):
    monkeypatch.delenv("MERCADOLIVRE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("MERCADOLIVRE_TOKEN", "alias-should-not-be-used")

    collector = MercadoLivrePriceCollector()
    creds = collector._credentials()

    assert creds["access_token"] == ""


def test_mercadolivre_refreshes_access_token_on_401(monkeypatch):
    monkeypatch.setenv("MERCADOLIVRE_ACCESS_TOKEN", "expired-token")
    monkeypatch.setenv("MERCADOLIVRE_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_SECRET", "client-secret")

    collector = MercadoLivrePriceCollector()
    calls = {"search": 0, "refresh": 0}

    def fake_request(url, *, method="GET", **kwargs):
        if "oauth/token" in url:
            calls["refresh"] += 1
            return DummyResponse(200, {"access_token": "renewed-token"})
        calls["search"] += 1
        auth = kwargs.get("headers", {}).get("Authorization", "")
        if auth == "Bearer expired-token":
            return DummyResponse(401, {"message": "expired"})
        if auth == "Bearer renewed-token":
            return DummyResponse(200, {
                "results": [
                    {
                        "price": 1999.0,
                        "title": "Sennheiser HD 600 Novo",
                        "permalink": "https://example.com/item",
                        "seller": {"nickname": "Loja"},
                        "available_quantity": 1,
                        "condition": "new",
                    }
                ]
            })
        raise AssertionError(f"unexpected auth header: {auth}")

    monkeypatch.setattr(collector, "_request", fake_request)

    results = collector.fetch("Sennheiser HD 600")

    assert results is not None
    assert len(results) == 1
    assert results[0]["source"] == "mercadolivre_api"
    assert collector.last_refresh_status == "refreshed"
    assert calls == {"search": 2, "refresh": 1}


def test_mercadolivre_returns_none_when_refresh_still_leads_to_401(monkeypatch):
    monkeypatch.setenv("MERCADOLIVRE_ACCESS_TOKEN", "expired-token")
    monkeypatch.setenv("MERCADOLIVRE_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_SECRET", "client-secret")

    collector = MercadoLivrePriceCollector()
    calls = {"search": 0, "refresh": 0}

    def fake_request(url, *, method="GET", **kwargs):
        if "oauth/token" in url:
            calls["refresh"] += 1
            return DummyResponse(200, {"access_token": "still-bad-token"})
        calls["search"] += 1
        auth = kwargs.get("headers", {}).get("Authorization", "")
        if auth == "Bearer expired-token":
            return DummyResponse(401, {"message": "expired"})
        if auth == "Bearer still-bad-token":
            return DummyResponse(401, {"message": "still expired"})
        raise AssertionError(f"unexpected auth header: {auth}")

    monkeypatch.setattr(collector, "_request", fake_request)

    results = collector.fetch("Sennheiser HD 600")

    assert results is None
    assert calls == {"search": 2, "refresh": 1}


def test_mercadolivre_reports_operational_failure(monkeypatch):
    collector = MercadoLivrePriceCollector()
    monkeypatch.setattr(collector, "_request", lambda *args, **kwargs: DummyResponse(403, {"message": "forbidden"}))

    results = collector.fetch("Sennheiser HD 600")

    assert results is None
    assert collector.last_failure_reason == "403"
    assert collector.last_api_status == 403


def test_mercadolivre_does_not_refresh_on_403(monkeypatch):
    monkeypatch.setenv("MERCADOLIVRE_ACCESS_TOKEN", "valid-token")
    monkeypatch.setenv("MERCADOLIVRE_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOLIVRE_CLIENT_SECRET", "client-secret")

    collector = MercadoLivrePriceCollector()
    calls = {"search": 0, "refresh": 0}

    def fake_request(url, *, method="GET", **kwargs):
        if "oauth/token" in url:
            calls["refresh"] += 1
            return DummyResponse(200, {"access_token": "renewed-token"})
        calls["search"] += 1
        return DummyResponse(403, {"message": "forbidden"})

    monkeypatch.setattr(collector, "_request", fake_request)

    results = collector.fetch("Sennheiser HD 600")

    assert results is None
    assert calls == {"search": 1, "refresh": 0}


def test_fetch_prices_falls_back_when_mercadolivre_fails_without_contaminating_cache(monkeypatch):
    original_zoom = dataset_generator._ZOOM
    original_ml = dataset_generator._MERCADOLIVRE
    original_kabum = dataset_generator._KABUM
    original_shopee = dataset_generator._SHOPEE
    original_amazon = dataset_generator._AMAZON
    try:
        dataset_generator._MERCADOLIVRE = SimpleNamespace(fetch=lambda name: None)
        dataset_generator._ZOOM = SimpleNamespace(fetch=lambda name: [{
            "price_brl": 1899.0,
            "source": "zoom_jacotei",
            "title": "Sennheiser HD 600 Headphone",
            "source_type": "structured_search",
            "match_score": 0.9,
            "condition": "new",
        }])
        dataset_generator._KABUM = None
        dataset_generator._SHOPEE = None
        dataset_generator._AMAZON = None

        cache = {}
        resolution = dataset_generator._fetch_prices("Sennheiser HD 600", "", cache)

        assert resolution["price_brl_real"] == 1899.0
        assert resolution["price_source"] == "zoom_jacotei"
        assert "sennheiser hd 600" in cache
        assert cache["sennheiser hd 600"]["price_source"] == "zoom_jacotei"
    finally:
        dataset_generator._ZOOM = original_zoom
        dataset_generator._MERCADOLIVRE = original_ml
        dataset_generator._KABUM = original_kabum
        dataset_generator._SHOPEE = original_shopee
        dataset_generator._AMAZON = original_amazon


def test_expired_cache_entry_is_ignored(monkeypatch):
    original_zoom = dataset_generator._ZOOM
    try:
        dataset_generator._ZOOM = SimpleNamespace(fetch=lambda name: [{
            "price_brl": 2099.0,
            "source": "zoom_jacotei",
            "title": "Sennheiser HD 600 Headphone",
            "source_type": "structured_search",
            "match_score": 0.91,
            "condition": "new",
        }])
        cache = {
            "sennheiser hd 600": {
                "canonical_name": "sennheiser hd 600",
                "price_brl_real": 999.0,
                "ttl_until": "2000-01-01T00:00:00+00:00",
                "source_health": "healthy",
            }
        }
        resolution = dataset_generator._fetch_prices("Sennheiser HD 600", "", cache)
        assert resolution["price_brl_real"] == 2099.0
    finally:
        dataset_generator._ZOOM = original_zoom


def test_fetch_prices_retries_with_commercial_search_name(monkeypatch):
    original_zoom = dataset_generator._ZOOM
    original_kabum = dataset_generator._KABUM
    original_shopee = dataset_generator._SHOPEE
    original_ml = dataset_generator._MERCADOLIVRE
    original_amazon = dataset_generator._AMAZON
    seen_queries = []
    try:
        def fake_zoom_fetch(query):
            seen_queries.append(query)
            if query == "Denon Perl Pro (ANC On, flat eq)":
                return None
            if query == "denon perl pro":
                return [{
                    "price_brl": 2299.0,
                    "source": "zoom_jacotei",
                    "title": "Denon Perl Pro Bluetooth",
                    "source_type": "structured_search",
                    "match_score": 0.47,
                    "condition": "new",
                }]
            return None

        dataset_generator._ZOOM = SimpleNamespace(fetch=fake_zoom_fetch)
        dataset_generator._KABUM = None
        dataset_generator._SHOPEE = None
        dataset_generator._MERCADOLIVRE = None
        dataset_generator._AMAZON = None

        cache = {}
        resolution = dataset_generator._fetch_prices("Denon Perl Pro (ANC On, flat eq)", "", cache)

        assert resolution["price_brl_real"] == 2299.0
        assert resolution["query_strategy"] == "commercial_query"
        assert resolution["query_used"] == "denon perl pro"
        assert seen_queries == ["Denon Perl Pro (ANC On, flat eq)", "denon perl pro"]
    finally:
        dataset_generator._ZOOM = original_zoom
        dataset_generator._KABUM = original_kabum
        dataset_generator._SHOPEE = original_shopee
        dataset_generator._MERCADOLIVRE = original_ml
        dataset_generator._AMAZON = original_amazon


def test_fetch_prices_deduplicates_equivalent_queries(monkeypatch):
    original_zoom = dataset_generator._ZOOM
    original_kabum = dataset_generator._KABUM
    original_shopee = dataset_generator._SHOPEE
    original_ml = dataset_generator._MERCADOLIVRE
    original_amazon = dataset_generator._AMAZON
    seen_queries = []
    try:
        def fake_zoom_fetch(query):
            seen_queries.append(query)
            if query == "hedd heddphone":
                return [{
                    "price_brl": 6999.0,
                    "source": "zoom_jacotei",
                    "title": "HEDD HEDDphone",
                    "source_type": "structured_search",
                    "match_score": 0.92,
                    "condition": "new",
                }]
            return None

        dataset_generator._ZOOM = SimpleNamespace(fetch=fake_zoom_fetch)
        dataset_generator._KABUM = None
        dataset_generator._SHOPEE = None
        dataset_generator._MERCADOLIVRE = None
        dataset_generator._AMAZON = None

        cache = {}
        resolution = dataset_generator._fetch_prices("HEDD HEDDphone (post-2020 earpads)", "", cache)

        assert resolution["price_brl_real"] == 6999.0
        assert resolution["query_strategy"] == "ultra_commercial_query"
        assert seen_queries == ["HEDD HEDDphone (post-2020 earpads)", "hedd heddphone post 2020", "hedd heddphone"]
    finally:
        dataset_generator._ZOOM = original_zoom
        dataset_generator._KABUM = original_kabum
        dataset_generator._SHOPEE = original_shopee
        dataset_generator._MERCADOLIVRE = original_ml
        dataset_generator._AMAZON = original_amazon
