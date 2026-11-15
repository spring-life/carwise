import json
import re

import httpx
from langchain_core.prompts import ChatPromptTemplate

from .config import Settings
from .models import AskResponse, Citation


NO_EVIDENCE = "现有资料不足以确认这个问题。请缩小车型范围或补充可信来源。"
NO_VERIFIED_QUOTE = "检索到了候选资料，但模型摘录未通过原文核对。请核对原始资料或换一种问法。"
UNCONFIRMED_RETRIEVAL = "检索到候选原文，但模型未确认它能回答问题。请核对下方来源。"

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是购车资料研究助手。阅读候选资料，只找与问题直接相关的原文句子，不要解释、改写或补充。
返回 JSON 对象：quotes 是最多三个对象的数组，每个对象包含 id（来源编号）和 quote（从该来源逐字复制的连续原文）。
如果资料无法回答，返回 {{\"quotes\": []}}。不得编造价格、油耗、故障率、售后体验或维修建议。"""),
    ("human", "问题：{question}\n候选资料：\n{context}"),
])


def verified_quote(quote: str | None, excerpt: str) -> str | None:
    if not isinstance(quote, str):
        return None
    source_positions = [index for index, char in enumerate(excerpt) if not char.isspace()]
    source = "".join(excerpt[index] for index in source_positions)
    best: tuple[int, int, bool] | None = None
    # PDF tables often make the model omit a row or reflow a later line.
    # Match only an anchored, contiguous span and render its source bytes.
    lines = quote.splitlines(keepends=True)
    for candidate in [quote, *("".join(lines[index:]) for index in range(1, len(lines)) if lines[index].strip())]:
        wanted = "".join(candidate.split())
        if len(wanted) < 18:
            continue
        start = source.find(wanted)
        length = len(wanted)
        if start < 0 and len(wanted) >= 30:
            start = source.find(wanted[:30])
            if start >= 0:
                length = 30
                while start + length < len(source) and length < len(wanted) and source[start + length] == wanted[length]:
                    length += 1
        if start >= 0 and (best is None or length > best[1]):
            best = (start, length, length < len(wanted))
    if best is None:
        return None
    start, length, partial = best
    matched = excerpt[source_positions[start]:source_positions[start + length - 1] + 1]
    if partial and "\n" in matched:
        lines = matched.splitlines(keepends=True)
        for index in range(len(lines) - 1, -1, -1):
            candidate = "".join(lines[:index + 1])
            if re.search(r"\d", lines[index]) and len("".join(candidate.split())) >= 18:
                return candidate.strip()
    return matched.strip()


class ChatModel:
    def __init__(self, settings: Settings):
        self.settings = settings

    def answer(self, question: str, citations: list[Citation]) -> AskResponse:
        if not citations:
            return AskResponse(answer=NO_EVIDENCE, citations=[], mode="no_evidence")
        context = "\n\n".join(
            f"[{citation.id}] {citation.title}｜{citation.source_type}｜{citation.published_on or '日期未知'}｜{citation.location or '正文'}\n{citation.excerpt}"
            for citation in citations
        )
        prompt = ANSWER_PROMPT.format_messages(question=question, context=context)
        messages = [{"role": message.type if message.type != "human" else "user", "content": message.content} for message in prompt]
        try:
            content = self._complete(messages)
            payload = json.loads(content)
            by_id = {citation.id: citation for citation in citations}
            chosen: list[tuple[Citation, str]] = []
            items = payload.get("quotes", []) if isinstance(payload, dict) else []
            if items == []:
                return AskResponse(answer=UNCONFIRMED_RETRIEVAL, citations=citations, mode="retrieval_only")
            for item in (items[:3] if isinstance(items, list) else []):
                if isinstance(item, dict):
                    citation = by_id.get(item.get("id"))
                    proposed = item.get("quote")
                elif isinstance(item, str):
                    marker = re.match(r"^\s*[\[{](S\d+)[\]}]\s*", item)
                    citation = by_id.get(marker.group(1)) if marker else citations[0] if len(citations) == 1 else None
                    proposed = item[marker.end():] if marker else item
                else:
                    continue
                if citation:
                    quote = verified_quote(proposed, citation.excerpt)
                    if quote:
                        chosen.append((citation, quote))
            if not chosen:
                return AskResponse(answer=NO_VERIFIED_QUOTE, citations=[], mode="no_evidence")
            answer = "根据已收录资料，相关原文如下：\n\n" + "\n\n".join(
                f"[{citation.id}] {quote}" for citation, quote in chosen
            )
            notes = list(dict.fromkeys(citation.applicability_note for citation, _ in chosen if citation.applicability_note))
            if notes:
                answer = "资料适用性提示：" + "；".join(notes) + "\n\n" + answer
            return AskResponse(answer=answer, citations=[citation for citation, _ in chosen], mode="evidence_selected")
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return AskResponse(
                answer="生成模型暂不可用。以下是检索到的相关原文，请核对来源后判断。",
                citations=citations,
                mode="retrieval_only",
            )

    def _complete(self, messages: list[dict[str, str]]) -> str:
        if self.settings.llm_provider == "ollama":
            response = httpx.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.settings.ollama_chat_model,
                    "messages": messages,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "seed": 42},
                },
                timeout=180,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        if self.settings.llm_provider == "deepseek":
            if not self.settings.deepseek_api_key:
                raise RuntimeError("CARWISE_DEEPSEEK_API_KEY is missing")
            response = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                json={
                    "model": self.settings.deepseek_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "stream": False,
                },
                timeout=180,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        raise ValueError(f"Unknown LLM provider: {self.settings.llm_provider}")

