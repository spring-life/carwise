"""Check answers against the question set in evaluation/."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from time import perf_counter

from fastapi.testclient import TestClient

from carwise.config import Settings
from carwise.main import app


def normalized(value: str) -> str:
    return "".join(value.split()).lower()


def assess(case: dict, response: dict) -> list[str]:
    failures = []
    if response.get("mode") != case["mode"]:
        failures.append(f"mode: expected {case['mode']}, got {response.get('mode')}")
    answer = normalized(response.get("answer", ""))
    for phrase in case.get("must_contain", []):
        if normalized(phrase) not in answer:
            failures.append(f"missing fact: {phrase}")
    citations = response.get("citations", [])
    if expected_document := case.get("document_id"):
        if expected_document not in {item.get("document_id") for item in citations}:
            failures.append(f"missing source: {expected_document}")
        if any(item.get("source_type") != "official" or "byd.com" not in item.get("url", "") for item in citations):
            failures.append("nonofficial source")
    elif case["mode"] in {"no_evidence", "clarification"} and citations:
        failures.append("unexpected citation")
    if case.get("must_warn_applicability") and "适用性提示" not in response.get("answer", ""):
        failures.append("missing applicability warning")
    if case["mode"] == "evidence_selected":
        quotes = re.findall(r"\[(S\d+)\]\s*(.*?)(?=\n\n\[S\d+\]|\Z)", response.get("answer", ""), re.DOTALL)
        by_id = {item["id"]: item for item in citations}
        if not quotes or any(
            source_id not in by_id or len(normalized(quote)) < 18
            or normalized(quote) not in normalized(by_id[source_id].get("excerpt", ""))
            for source_id, quote in quotes
        ):
            failures.append("answer lacks a verifiable source span")
    return failures


def evaluate(cases: list[dict]) -> dict:
    rows = []
    with TestClient(app) as client:
        for case in cases:
            start = perf_counter()
            response = client.post("/api/ask", json={
                "question": case["question"], "vehicle_ids": case["vehicle_ids"],
            })
            elapsed_ms = round((perf_counter() - start) * 1000, 1)
            result = response.json()
            failures = assess(case, result) if response.status_code == 200 else [f"HTTP {response.status_code}"]
            rows.append({
                "id": case["id"], "group": case["group"], "question": case["question"],
                "vehicle_ids": case["vehicle_ids"], "expected_mode": case["mode"],
                "mode": result.get("mode"), "answer": result.get("answer"),
                "citations": [{"document_id": item["document_id"], "location": item.get("location"), "url": item["url"]} for item in result.get("citations", [])],
                "elapsed_ms": elapsed_ms, "passed": not failures, "failures": failures,
            })
            print(f"{case['id']}: {'PASS' if not failures else 'FAIL'} {', '.join(failures)}", flush=True)
    groups = sorted({case["group"] for case in cases})
    return {
        "protocol": "Answer quality regression set. Questions and expected facts are fixed before the first run. Checks are exact factual proxies; manual review remains necessary.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "question_count": len(cases),
        "summary": {group: {"passed": sum(row["passed"] for row in rows if row["group"] == group), "total": sum(row["group"] == group for row in rows)} for group in groups},
        "passed": sum(row["passed"] for row in rows),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Settings().project_root / "evaluation" / "answer-quality-results.json")
    args = parser.parse_args()
    questions_path = Settings().project_root / "evaluation" / "answer-quality-questions.json"
    cases = json.loads(questions_path.read_text(encoding="utf-8"))
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Question IDs must be unique")
    report = evaluate(cases)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "total": report["question_count"], "groups": report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
