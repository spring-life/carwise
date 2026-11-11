from carwise.extraction import FactExtractor, classify_fact
from carwise.config import Settings
from carwise.knowledge import load_manifest


def test_classifier_corrects_obvious_fault_signal():
    quote = "当胎压故障警告灯点亮时，表示胎压系统有故障。"
    assert classify_fact(quote, "配置说明") == "故障信号"


def test_extraction_drops_quotes_missing_from_source():
    settings = Settings()
    record = load_manifest(settings.data_dir / "documents.json")[0]
    extractor = FactExtractor(settings)
    extractor.chat._complete = lambda messages: '{"facts": [{"fact_type": "风险", "quote": "这款车的电池一定会在两年内发生故障。"}]}'
    result = extractor.extract(record, 62, "本页只说明胎压故障警告灯的含义。")
    assert result.mode == "no_facts"
    assert result.facts == []

