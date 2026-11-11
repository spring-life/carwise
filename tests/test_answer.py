from datetime import date

from carwise.config import Settings
from carwise.llm import ChatModel
from carwise.models import Citation


def citation() -> Citation:
    return Citation(
        id="S1",
        document_id="manual-1",
        title="测试手册",
        url="https://example.com/manual.pdf",
        source_type="official",
        published_on=date(2026, 4, 1),
        location="第 62 页",
        excerpt="当胎压故障警告灯点亮或闪烁，\n同时仪表显示请检查胎压监测系统。",
    )


def test_answer_accepts_only_verifiable_quote():
    model = ChatModel(Settings())
    model._complete = lambda messages: '{"quotes": [{"id": "S1", "quote": "当胎压故障警告灯点亮或闪烁，同时仪表显示请检查胎压监测系统。"}]}'
    result = model.answer("胎压灯亮了？", [citation()])
    assert result.mode == "evidence_selected"
    assert result.citations[0].location == "第 62 页"


def test_answer_rejects_model_invention():
    model = ChatModel(Settings())
    model._complete = lambda messages: '{"quotes": [{"id": "S1", "quote": "车辆必须立刻报废，并且不能驾驶。"}]}'
    result = model.answer("胎压灯亮了？", [citation()])
    assert result.mode == "no_evidence"
    assert result.citations == []

