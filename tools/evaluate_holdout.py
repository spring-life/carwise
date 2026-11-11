"""Run the frozen holdout once against the existing local index."""

import json
from pathlib import Path

from carwise.config import Settings
from carwise.knowledge import KnowledgeBase


def main() -> None:
    root = Settings().project_root
    output = root / "evaluation" / "results-holdout.json"
    if output.exists():
        raise SystemExit(f"Holdout result already exists: {output}")
    questions = json.loads((root / "evaluation" / "questions-holdout.json").read_text(encoding="utf-8"))
    kb = KnowledgeBase(Settings())
    if kb.count() == 0:
        raise SystemExit("Local index is empty")
    results = []
    for item in questions:
        citations = kb.search(item["question"], [item["vehicle_id"]], limit=3)
        hits = [
            {"document_id": citation.document_id, "page": int(citation.location.split()[1]) if citation.location and citation.location.startswith("第 ") else None}
            for citation in citations
        ]
        expected_document = item.get("expected_document_id")
        expected_pages = item["expected_pages"]
        results.append({
            "id": item["id"],
            "expected_document_id": expected_document,
            "expected_pages": expected_pages,
            "retrieved": hits,
            "page_hit": any(hit["document_id"] == expected_document and hit["page"] in expected_pages for hit in hits) if expected_pages else None,
            "document_hit": any(hit["document_id"] == expected_document for hit in hits) if expected_pages else None,
            "rejected": not hits if not expected_pages else None,
        })
    factual = [row for row in results if row["expected_pages"]]
    absent = [row for row in results if not row["expected_pages"]]
    report = {
        "protocol": {
            "baseline_commit": "224a4d3",
            "random_seed": 20261111,
            "sampling": "Five manuals, four pages per manual; indexed page ranges, nonempty page text, excluding development question page numbers; questions drafted from source pages before retrieval.",
            "config": {"min_similarity": 0.58, "service_page_min_similarity": 0.54, "chunk_size": 350, "chunk_overlap": 60, "same_page_penalty": 0.05},
            "retrieval_limit": 3,
        },
        "counts": {
            "factual": len(factual),
            "unanswerable": len(absent),
            "page_hits": sum(row["page_hit"] for row in factual),
            "document_hits": sum(row["document_hit"] for row in factual),
            "unanswerable_rejections": sum(row["rejected"] for row in absent),
        },
        "results": results,
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
