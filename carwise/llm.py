import json

import httpx
from langchain_core.prompts import ChatPromptTemplate

from .config import Settings
from .models import AskResponse, Citation


NO_EVIDENCE = "现有资料不足以确认这个问题。请缩小车型范围或补充可信来源。"

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是购车资料研究助手。阅读候选资料，只找与问题直接相关的原文句子，不要解释、改写或补充。
返回 JSON 对象：quotes 是最多三个对象的数组，每个对象包含 id（来源编号）和 quote（从该来源逐字复制的连续原文）。
如果资料无法回答，返回 {{\"quotes\": []}}。不得编造价格、油耗、故障率、售后体验或维修建议。"""),
    ("human", "问题：{question}\n候选资料：\n{context}"),
])


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
            for item in payload.get("quotes", [])[:3]:
                citation = by_id.get(item.get("id"))
                quote = item.get("quote")
                if (
                    citation and isinstance(quote, str)
                    and len("".join(quote.split())) >= 18
                    and "".join(quote.split()) in "".join(citation.excerpt.split())
                ):
                    chosen.append((citation, quote.strip()))
            if not chosen:
                return AskResponse(answer=NO_EVIDENCE, citations=[], mode="no_evidence")
            answer = "根据已收录资料，相关原文如下：\n\n" + "\n\n".join(
                f"[{citation.id}] {quote}" for citation, quote in chosen
            )
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

