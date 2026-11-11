import json

from .config import Settings
from .knowledge import KnowledgeBase


def evaluate() -> dict:
    settings = Settings()
    questions = json.loads((settings.project_root / "evaluation" / "questions.json").read_text(encoding="utf-8"))
    kb = KnowledgeBase(settings)
    results = []
    for question in questions:
        citations = kb.search(question["question"], [question["vehicle_id"]], limit=3)
        pages = [int(c.location.split()[1]) for c in citations if c.location and c.location.startswith("第 ")]
        expected = question["expected_pages"]
        expected_document_id = question.get("expected_document_id")
        if expected:
            matched = bool(set(pages) & set(expected))
        elif expected_document_id:
            matched = any(c.document_id == expected_document_id for c in citations)
        else:
            matched = not citations
        results.append({
            "id": question["id"],
            "question": question["question"],
            "expected_pages": expected,
            "expected_document_id": expected_document_id,
            "retrieved_pages": pages,
            "retrieved_documents": [citation.document_id for citation in citations],
            "pass": matched,
        })
    page_questions = [item for item in results if item["expected_pages"]]
    document_questions = [item for item in results if item["expected_document_id"]]
    unanswerable = [item for item in results if not item["expected_pages"] and not item["expected_document_id"]]
    return {
        "total": len(results),
        "top3_page_hit_rate": sum(item["pass"] for item in page_questions) / len(page_questions),
        "top3_document_hit_rate": sum(item["pass"] for item in document_questions) / len(document_questions),
        "unanswerable_rejection_rate": sum(item["pass"] for item in unanswerable) / len(unanswerable),
        "results": results,
    }


def main() -> None:
    report = evaluate()
    output = Settings().project_root / "evaluation" / "retrieval-results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Top-3 page hit: {report['top3_page_hit_rate']:.1%}")
    print(f"Top-3 document hit: {report['top3_document_hit_rate']:.1%}")
    print(f"Unanswerable rejection: {report['unanswerable_rejection_rate']:.1%}")
    print("Failures:", ", ".join(item["id"] for item in report["results"] if not item["pass"]) or "none")


if __name__ == "__main__":
    main()

