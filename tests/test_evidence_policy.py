import pytest

from carwise.config import Settings
from carwise.knowledge import KnowledgeBase


@pytest.mark.parametrize("question", [
    "秦L车主售后满意度是多少？",
    "秦L每万辆车投诉率是多少？",
    "秦L真实道路油耗是多少？",
    "秦L全国实际成交均价是多少？",
])
def test_unsupported_metrics_are_not_answered_from_manuals(question):
    kb = KnowledgeBase(Settings())
    assert kb.search(question, ["byd-2026-qin-l-dm-i-1668"]) == []

