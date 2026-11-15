from datetime import date

from carwise.config import Settings
from carwise.llm import ChatModel, NO_VERIFIED_QUOTE, UNCONFIRMED_RETRIEVAL
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
    assert result.answer == NO_VERIFIED_QUOTE


def test_answer_keeps_only_verified_source_prefix_when_table_tail_is_misquoted():
    model = ChatModel(Settings())
    source = citation()
    source.excerpt = "发动机参数\n发动机型号 BYD472QC\n发动机型式 点燃式\n排量(L) 1.498\n发动机额定功\n率/转速(kW/\nrpm)\n74/6000\n最大扭矩 126/4500"
    model._complete = lambda messages: '{"quotes": [{"id": "S1", "quote": "发动机型号 BYD472QC\\n发动机型式 点燃式\\n排量(L) 1.498\\n发动机额定功率/转速(kW/rpm) 74/6000\\n最大扭矩 999/4500"}]}'
    result = model.answer("这款车发动机规格是什么", [source])
    assert result.mode == "evidence_selected"
    assert "发动机型号 BYD472QC" in result.answer
    assert "排量(L) 1.498" in result.answer
    assert "74/6000" in result.answer
    assert "999/4500" not in result.answer
    assert "最大扭矩" not in result.answer
    assert result.citations == [source]


def test_answer_shows_retrieved_source_when_model_returns_no_quotes():
    model = ChatModel(Settings())
    model._complete = lambda messages: '{"quotes": []}'
    result = model.answer("这款车有什么提示？", [citation()])
    assert result.mode == "retrieval_only"
    assert result.answer == UNCONFIRMED_RETRIEVAL
    assert result.citations == [citation()]


def test_answer_recovers_source_span_from_string_quote_with_skipped_table_row():
    model = ChatModel(Settings())
    source = citation()
    source.excerpt = "发动机参数\n项目 参数\n产品型号 BYD7153WT6HEV6\n发动机型号 BYD472QC\n发动机型式 点燃式\n排量(L) 1.498\n发动机额定功\n率/转速(kW/\nrpm)\n74/6000"
    model._complete = lambda messages: '{"quotes": ["{S1}\\n项目 参数\\n发动机型号 BYD472QC\\n发动机型式 点燃式\\n排量(L) 1.498\\n发动机额定功率/转速(kW/rpm) 74/6000"]}'
    result = model.answer("这款车发动机规格是什么", [source])
    assert result.mode == "evidence_selected"
    assert "发动机型号 BYD472QC" in result.answer
    assert "排量(L) 1.498" in result.answer
    assert result.answer.split("[S1] ", 1)[1] in source.excerpt


def test_answer_handles_unexpected_quote_format():
    model = ChatModel(Settings())
    model._complete = lambda messages: '{"quotes": [123, null]}'
    result = model.answer("胎压灯亮了？", [citation()])
    assert result.mode == "no_evidence"
    assert result.answer == NO_VERIFIED_QUOTE


def test_answer_flags_unconfirmed_manual_applicability():
    model = ChatModel(Settings())
    source = citation()
    source.applicability_note = "官网未标年款，2026 款适用性待核。"
    model._complete = lambda messages: '{"quotes": [{"id": "S1", "quote": "当胎压故障警告灯点亮或闪烁，同时仪表显示请检查胎压监测系统。"}]}'
    result = model.answer("这款车胎压灯亮了怎么办？", [source])
    assert result.mode == "evidence_selected"
    assert result.answer.startswith("资料适用性提示：官网未标年款")

