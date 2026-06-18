from datetime import timedelta

import dataset_generator
from src.collectors.product_matcher import (
    canonicalize_headphone_name,
    commercial_search_name,
    match_product,
    model_core_search_name,
    ultra_commercial_search_name,
)
from src.pricing import is_cache_entry_valid, now_utc, resolve_price, ttl_until_for


def test_canonical_name_collapses_measurement_variants():
    assert canonicalize_headphone_name("Beyerdynamic T1 (sample 1)") == "beyerdynamic t1"
    assert canonicalize_headphone_name("Moondrop Chu (serial number 123)") == "moondrop chu"
    assert commercial_search_name("Denon Perl Pro (ANC On, flat eq)") == "denon perl pro"
    assert ultra_commercial_search_name("Truthear x Crinacle Zero RED (Bass+)") == "truthear x crinacle zero red"
    assert model_core_search_name("Sennheiser HD 58X Jubilee") == "sennheiser hd 58x"
    assert model_core_search_name("HEDD HEDDphone (post-2020 earpads)") == "hedd heddphone"


def test_match_product_rejects_accessory_and_wrong_numeric_model():
    accessory = match_product("Sennheiser HD 600", "Almofada para Sennheiser HD 600")
    wrong_model = match_product("Sennheiser HD 600", "Sennheiser HD 25 Headphone")

    assert accessory.is_accessory is True
    assert accessory.match_score < 0.3
    assert accessory.brand_conflict is False
    assert wrong_model.match_score < 0.55
    assert wrong_model.numeric_conflict is True


def test_resolve_price_prefers_real_price_over_accessory_bait():
    resolution = resolve_price(
        "Sennheiser HD 600",
        [
            {
                "price_brl": 49.9,
                "source": "shopee",
                "title": "Almofada para Sennheiser HD 600",
                "source_type": "marketplace",
                "match_score": 0.9,
                "is_accessory": True,
            },
            {
                "price_brl": 1799.0,
                "source": "mercadolivre_api",
                "title": "Sennheiser HD 600 Novo Lacrado",
                "source_type": "official_api",
                "match_score": 0.95,
                "condition": "new",
            },
        ],
    )

    assert resolution["price_brl_real"] == 1799.0
    assert resolution["price_confidence"].startswith("real_")
    assert resolution["price_source"] == "mercadolivre_api"
    assert resolution["source_health"] == "healthy"


def test_resolve_price_falls_back_to_estimated_when_no_real_price_survives():
    resolution = resolve_price(
        "Sennheiser HD 600",
        [
            {
                "price_brl": 59.9,
                "source": "shopee",
                "title": "Case para Sennheiser HD 600",
                "source_type": "marketplace",
                "match_score": 0.9,
                "is_accessory": True,
            },
            {
                "price_brl": 1690.0,
                "source": "amazon_br",
                "title": "Sennheiser HD 600 usado",
                "source_type": "marketplace",
                "match_score": 0.92,
                "condition": "used",
            },
            {
                "price_brl": 1899.0,
                "source": "zoom_jacotei",
                "title": "Sennheiser HD 600 Headphone",
                "source_type": "structured_search",
                "match_score": 0.39,
                "condition": "new",
            },
            {
                "price_brl": 1999.0,
                "source": "kabum",
                "title": "Sennheiser HD 600 Headphone",
                "source_type": "structured_search",
                "match_score": 0.38,
                "condition": "new",
            },
        ],
    )

    assert resolution["price_brl_real"] is None
    assert resolution["price_brl_estimated"] == 1949.0
    assert resolution["price_source_type"] == "estimated"


def test_structured_search_can_resolve_variant_with_lower_match_threshold():
    resolution = resolve_price(
        "Denon Perl Pro (ANC On, flat eq)",
        [
            {
                "price_brl": 2199.0,
                "source": "zoom_jacotei",
                "title": "Denon Perl Pro Fone Bluetooth",
                "source_type": "structured_search",
                "match_score": 0.47,
                "condition": "new",
                "variant_group": "anc",
            },
            {
                "price_brl": 2299.0,
                "source": "kabum",
                "title": "Denon Perl Pro Bluetooth",
                "source_type": "structured_search",
                "match_score": 0.46,
                "condition": "new",
                "variant_group": "anc",
            },
        ],
    )

    assert resolution["price_brl_real"] == 2199.0
    assert resolution["price_confidence"] in {"real_medium", "real_high"}
    assert resolution["query_strategy"] is None


def test_marketplace_threshold_stays_stricter_than_structured_search():
    resolution = resolve_price(
        "Denon Perl Pro (ANC On, flat eq)",
        [
            {
                "price_brl": 2199.0,
                "source": "shopee",
                "title": "Denon Perl Pro Bluetooth",
                "source_type": "marketplace",
                "match_score": 0.47,
                "condition": "new",
                "variant_group": "anc",
            },
        ],
    )

    assert resolution["price_brl_real"] is None
    assert resolution["price_brl_estimated"] == 2199.0


def test_cache_entry_validity_respects_ttl_and_health():
    valid = {
        "ttl_until": ttl_until_for("structured_search"),
        "source_health": "healthy",
    }
    invalid_health = {
        "ttl_until": ttl_until_for("structured_search"),
        "source_health": "source_unreachable",
    }
    expired = {
        "ttl_until": (now_utc() - timedelta(hours=1)).isoformat(),
        "source_health": "healthy",
    }

    assert is_cache_entry_valid(valid) is True
    assert is_cache_entry_valid(invalid_health) is False
    assert is_cache_entry_valid(expired) is False


def test_resolve_price_generates_audit_for_suspiciously_low_real_price():
    resolution = resolve_price(
        "Sennheiser HD 600",
        [
            {
                "price_brl": 999.0,
                "source": "mercadolivre_api",
                "title": "Sennheiser HD 600 novo",
                "source_type": "official_api",
                "match_score": 0.95,
                "condition": "new",
            },
            {
                "price_brl": 2199.0,
                "source": "zoom_jacotei",
                "title": "Sennheiser HD 600 Headphone",
                "source_type": "structured_search",
                "match_score": 0.9,
                "condition": "new",
            },
            {
                "price_brl": 2299.0,
                "source": "kabum",
                "title": "Sennheiser HD 600 Headphone",
                "source_type": "structured_search",
                "match_score": 0.92,
                "condition": "new",
            },
        ],
    )

    reasons = {record["audit_reason"] for record in resolution["audit_records"]}
    assert "real_price_far_below_candidate_median" in reasons


def test_write_csv_includes_updated_at_column(tmp_path):
    path = tmp_path / "ranking.csv"
    count = dataset_generator._write_csv([
        {
            "name": "Sennheiser HD 600",
            "category": "over-ear",
            "score": 0.5,
            "percentile": 100.0,
            "e_total": 1.0,
            "e_fr": 1.0,
            "e_thd": 0.0,
            "e_match": 0.0,
            "e_unc": 0.2,
            "w_conf": 0.8,
            "price_brl": 1999.0,
            "canonical_name": "sennheiser hd 600",
            "price_brl_real": 1999.0,
            "price_brl_estimated": None,
            "price_confidence": "real_high",
            "price_source": "mercadolivre_api",
            "price_source_type": "official_api",
            "price_match_score": 0.95,
            "updated_at": now_utc().isoformat(),
        }
    ], path)

    text = path.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "updated_at" in text.splitlines()[0]


def test_write_price_audit_includes_query_strategy(tmp_path):
    path = tmp_path / "price_audit.csv"
    count = dataset_generator._write_price_audit([
        {
            "display_name": "Denon Perl Pro (ANC On, flat eq)",
            "canonical_name": "denon perl pro",
            "price_brl_real": None,
            "price_brl_estimated": 2299.0,
            "price_source": None,
            "price_confidence": "estimated_low",
            "query_strategy": "commercial_query",
            "audit_reason": "estimated_after_strong_candidate_conflict",
        }
    ], path)

    text = path.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "query_strategy" in text.splitlines()[0]
