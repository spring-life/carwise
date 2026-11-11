from pathlib import Path

from carwise.vector_store import VectorStore


def test_vector_store_filters_documents_and_replaces_without_duplicates(tmp_path: Path):
    store = VectorStore(tmp_path / "vectors.sqlite3")
    store.replace_document("manual-a", ["a1"], ["胎压故障说明"], [{"document_id": "manual-a"}], [[1.0, 0.0]])
    store.replace_document("manual-b", ["b1"], ["售后说明"], [{"document_id": "manual-b"}], [[0.0, 1.0]])

    assert store.count() == 2
    assert store.search([1.0, 0.0], ["manual-b"], 5)[0][0] == "售后说明"
    assert store.search([1.0, 0.0], [], 5) == []

    store.replace_document("manual-a", ["a2"], ["更新后的胎压说明"], [{"document_id": "manual-a"}], [[1.0, 0.0]])
    assert store.count() == 2
    assert store.search([1.0, 0.0], ["manual-a"], 5)[0][0] == "更新后的胎压说明"

