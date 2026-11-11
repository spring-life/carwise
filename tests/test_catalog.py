from datetime import date

import pytest

from carwise.catalog import Catalog
from carwise.config import Settings
from carwise.models import VehicleVariant


def make_variant(vehicle_id: str, market: str = "中国大陆", **overrides) -> VehicleVariant:
    data = {
        "id": vehicle_id,
        "market": market,
        "make": "测试品牌",
        "model": "测试车型",
        "year": 2026,
        "trim": "标准版",
        "msrp": 100000,
        "currency": "CNY",
        "sources": {
            "specs": {"title": "官方配置", "url": "https://example.com/specs", "observed_on": date(2026, 11, 11)},
            "price": {"title": "官方价格", "url": "https://example.com/price", "observed_on": date(2026, 11, 11)},
        },
    }
    data.update(overrides)
    return VehicleVariant.model_validate(data)


def test_catalog_keeps_trim_identity_and_rejects_cross_market():
    china = make_variant("china-2026-standard")
    china_premium = make_variant("china-2026-premium", trim="高配版", msrp=120000)
    us = make_variant("us-2026-standard", market="美国")
    catalog = Catalog([china, china_premium, us])

    assert [item.id for item in catalog.compare([china.id, china_premium.id])] == [china.id, china_premium.id]
    with pytest.raises(ValueError, match="different markets"):
        catalog.compare([china.id, us.id])
    with pytest.raises(ValueError, match="distinct"):
        catalog.compare([china.id, china.id])


def test_price_and_consumption_require_provenance():
    with pytest.raises(ValueError, match="price source"):
        make_variant("missing-price-source", sources={"specs": {"title": "配置", "url": "https://example.com", "observed_on": date(2026, 11, 11)}})
    with pytest.raises(ValueError, match="unit, standard, and source"):
        make_variant("missing-fuel-source", fuel_consumption=3.0)


def test_official_snapshot_has_distinct_versions_and_cited_fields():
    catalog = Catalog.from_file(Settings().data_dir / "catalog.json")
    variants = catalog.list()
    assert len(variants) >= 7
    assert len({item.id for item in variants}) == len(variants)
    assert len({item.model for item in variants}) >= 10
    assert all(item.year == 2026 and item.msrp for item in variants)
    assert sum(bool(item.features) for item in variants) >= 35
    assert all(item.sources["price"].url.host == "www.byd.com" for item in variants)


def test_question_narrows_selected_models_and_rejects_wrong_year_or_trim():
    catalog = Catalog.from_file(Settings().data_dir / "catalog.json")
    qin_l = next(v for v in catalog.list() if v.model == "秦L DM-i" and v.trim == "128KM进取型")
    qin_plus = next(v for v in catalog.list() if v.model == "秦PLUS DM-i" and v.trim == "128KM进取型")
    selected = [qin_l.id, qin_plus.id]
    assert catalog.scope_for_question("秦L的胎压故障灯是什么意思？", selected) == [qin_l.id]
    assert catalog.scope_for_question("秦PLUS的胎压故障灯是什么意思？", selected) == [qin_plus.id]
    assert catalog.scope_for_question("2025款秦L有什么故障？", selected) == []
    assert catalog.scope_for_question("秦L 210KM超越型有什么故障？", selected) == []

