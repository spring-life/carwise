import json
import re

import httpx
from langchain_core.prompts import ChatPromptTemplate

from .config import Settings
from .llm import ChatModel
from .models import DocumentRecord, ExtractedFact, ExtractResponse


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """从这页汽车手册中抽取对购车用户有用的事实。只允许以下类型：故障信号、风险、建议操作、保养周期、配置说明。
返回 JSON 对象，facts 为数组，每项包含 fact_type 和 quote。quote 必须是原文中连续的完整句子，最多五项。
不要改写，不要从其他页面补充，不要把警告推断成故障率。没有合适事实时返回 {{\"facts\": []}}。"""),
    ("human", "文档：{title}\nPDF 第 {page_number} 页：\n{text}"),
])


class FactExtractor:
    def __init__(self, settings: Settings):
        self.chat = ChatModel(settings)

    def extract(self, record: DocumentRecord, page_number: int, text: str) -> ExtractResponse:
        prompt = EXTRACTION_PROMPT.format_messages(
            title=record.title,
            page_number=page_number,
            text=text[:10000],
        )
        messages = [
            {"role": "system" if message.type == "system" else "user", "content": message.content}
            for message in prompt
        ]
        try:
            payload = json.loads(self.chat._complete(messages))
            facts = []
            normalized_page = "".join(text.split())
            for item in payload.get("facts", [])[:5]:
                fact = ExtractedFact.model_validate(item)
                if (
                    len("".join(fact.quote.split())) >= 18
                    and fact.quote.rstrip().endswith(("。", "！", "？", ".", "!", "?"))
                    and "".join(fact.quote.split()) in normalized_page
                ):
                    fact.fact_type = classify_fact(fact.quote, fact.fact_type)
                    facts.append(fact)
            mode = "extracted" if facts else "no_facts"
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            facts = []
            mode = "model_unavailable"
        return ExtractResponse(
            document_id=record.id,
            title=record.title,
            page_number=page_number,
            source_url=record.source_url,
            facts=facts,
            mode=mode,
        )


def classify_fact(quote: str, suggested: str) -> str:
    if "保养" in quote and re.search(r"\d+\s*(?:个月|km|公里)", quote):
        return "保养周期"
    if "警告灯" in quote and any(word in quote for word in ("表示", "说明", "故障", "熄灭")):
        return "故障信号"
    if any(word in quote for word in ("建议", "请勿", "应当", "立即")):
        return "建议操作"
    if any(word in quote for word in ("风险", "伤害", "不稳定", "失灵")):
        return "风险"
    return suggested

