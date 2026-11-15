from fastapi.testclient import TestClient

from carwise.catalog import Catalog
from carwise.config import Settings
from carwise.knowledge import KnowledgeBase
from carwise.main import app
from carwise.specs import catalog_question_answer, engine_specs_answer


XIA_ID = "byd-2026-xia-1677"


def test_broad_engine_specs_for_selected_xia_uses_official_catalog():
    vehicle = Catalog.from_file(Settings().data_dir / "catalog.json").get(XIA_ID)
    result = engine_specs_answer("这款车发动机规格是什么", [vehicle])
    assert result is not None and result.mode == "catalog"
    assert "插混专用1.5T高效发动机" in result.answer
    assert "排量（L）：1.5Ti" in result.answer
    assert "发动机最大功率（kW）：115" in result.answer
    assert "发动机最大扭矩（N·m）：225" in result.answer
    assert result.citations[0].url.host == "www.byd.com"
    assert str(result.citations[0].published_on) == "2026-11-15"


def test_specific_engine_fields_and_unavailable_fields():
    catalog = Catalog.from_file(Settings().data_dir / "catalog.json")
    xia = catalog.get(XIA_ID)
    result = engine_specs_answer("这款车发动机型号和排量是多少", [xia])
    assert result is not None and result.mode == "catalog"
    assert "发动机型号" in result.answer and "排量（L）" in result.answer
    assert "发动机最大功率" not in result.answer
    qin = next(vehicle for vehicle in catalog.list() if vehicle.model == "秦L DM-i")
    assert engine_specs_answer("发动机规格是什么", [qin]) is None
    assert engine_specs_answer("发动机故障灯亮了怎么办", [xia]) is None


def test_broad_power_question_uses_available_fields_and_ambiguous_question_clarifies():
    vehicle = Catalog.from_file(Settings().data_dir / "catalog.json").get(XIA_ID)
    power = catalog_question_answer("这款车的动力参数有哪些？", [vehicle])
    assert power is not None and power.mode == "catalog"
    assert "动力类型" in power.answer
    assert "电机最大功率" in power.answer
    vague = catalog_question_answer("这款车怎么样？", [vehicle])
    assert vague is not None and vague.mode == "clarification"
    assert "价格配置" in vague.answer
    assert catalog_question_answer("发动机故障灯亮了怎么办", [vehicle]) is None
    engine = catalog_question_answer("这款车发动机怎么样？", [vehicle])
    assert engine is not None and engine.mode == "catalog"
    assert "发动机型号" in engine.answer


def test_ask_api_resolves_selected_xia_without_using_llm():
    with TestClient(app) as client:
        for question in ("这款车发动机规格是什么", "这款车发动机型号和排量是多少"):
            response = client.post("/api/ask", json={"question": question, "vehicle_ids": [XIA_ID]})
            assert response.status_code == 200
            data = response.json()
            assert data["mode"] == "catalog"
            assert len(data["citations"]) == 1
            assert data["citations"][0]["location"] == "100KM进取型"


def test_ask_api_clarifies_missing_or_ambiguous_selection():
    with TestClient(app) as client:
        for ids in ([], [XIA_ID, "byd-2026-xia-1678"]):
            response = client.post("/api/ask", json={"question": "这款车发动机规格是什么", "vehicle_ids": ids})
            assert response.status_code == 200
            assert response.json()["mode"] == "clarification"
        mismatch = client.post("/api/ask", json={"question": "秦L发动机规格是什么", "vehicle_ids": [XIA_ID]})
        assert mismatch.json()["mode"] == "clarification"


def test_ask_routes_other_official_specs_and_price_wording():
    with TestClient(app) as client:
        cases = (
            ("这款车轮胎规格多少？", "235/60 R18"),
            ("这款车的电池容量是多少？", "20.39"),
            ("这款车标称亏电油耗多少？", "4.9"),
            ("这款车的纯电续航有多少？", "100"),
            ("这款车售价多少？", "206,800"),
        )
        for question, expected in cases:
            data = client.post("/api/ask", json={"question": question, "vehicle_ids": [XIA_ID]}).json()
            assert data["mode"] == "catalog"
            assert expected in data["answer"]
            assert data["citations"][0]["document_id"] == f"catalog-{XIA_ID}"


def test_first_service_quote_works_when_items_continue_on_next_page(tmp_path):
    knowledge = KnowledgeBase(Settings(storage_dir=tmp_path))
    record = next(item for item in knowledge.records if item.id == "byd-qin-plus-manual-2026")
    body = "保养周期表\n首次保养\n车辆在 6 个月或 5000km(HEV 里程)进行首保，保养时间和保养里程以先到者为准。"
    knowledge.store.replace_document(record.id, ["first-service"], [body], [{
        "document_id": record.id, "title": record.title, "source_url": str(record.source_url),
        "source_type": record.source_type, "published_on": record.published_on.isoformat(),
        "location": "第 344 页", "applicability_note": "",
    }], [[1.0]])
    result = knowledge.first_service_answer(
        "秦PLUS DM-i首次保养看时间还是HEV里程？", ["byd-2026-qin-plus-dm-i-1684"]
    )
    assert result is not None and result.mode == "evidence_selected"
    assert "5000km" in result.answer
    assert result.citations[0].location == "第 344 页"
    assert knowledge.first_service_answer(
        "秦PLUS首保包括更换什么？", ["byd-2026-qin-plus-dm-i-1684"]
    ) is None
