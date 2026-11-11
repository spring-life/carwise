"""Small, inspectable vector store backed by SQLite and exact cosine search."""

import json
import sqlite3
from pathlib import Path

import numpy as np


class VectorStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    dimensions INTEGER NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def count_document(self, document_id: str) -> int:
        with self._connect() as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchone()[0])

    def replace_document(
        self,
        document_id: str,
        ids: list[str],
        chunks: list[str],
        metadatas: list[dict[str, str]],
        vectors: list[list[float]],
    ) -> None:
        if not (len(ids) == len(chunks) == len(metadatas) == len(vectors)):
            raise ValueError("Chunk arrays must have the same length")
        rows = []
        for chunk_id, body, metadata, vector in zip(ids, chunks, metadatas, vectors):
            array = np.asarray(vector, dtype=np.float32)
            if array.ndim != 1 or not array.size:
                raise ValueError("Embedding must be a nonempty one-dimensional vector")
            rows.append((
                chunk_id, document_id, body,
                json.dumps(metadata, ensure_ascii=False),
                array.tobytes(), int(array.size),
            ))
        with self._connect() as connection:
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            connection.executemany(
                "INSERT INTO chunks (id, document_id, body, metadata, embedding, dimensions) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )

    def search(
        self,
        vector: list[float],
        document_ids: list[str] | None,
        limit: int,
    ) -> list[tuple[str, dict[str, str], float]]:
        query = np.asarray(vector, dtype=np.float32)
        if query.ndim != 1 or not query.size:
            raise ValueError("Query embedding is empty")
        with self._connect() as connection:
            if document_ids is None:
                rows = connection.execute("SELECT body, metadata, embedding, dimensions FROM chunks").fetchall()
            elif not document_ids:
                return []
            else:
                placeholders = ",".join("?" for _ in document_ids)
                rows = connection.execute(
                    f"SELECT body, metadata, embedding, dimensions FROM chunks WHERE document_id IN ({placeholders})",
                    document_ids,
                ).fetchall()
        if not rows:
            return []
        bodies: list[str] = []
        metadata: list[dict[str, str]] = []
        vectors: list[np.ndarray] = []
        for body, meta, blob, dimensions in rows:
            if dimensions != query.size:
                raise ValueError("Stored embedding dimensions differ from the current model; reingest documents")
            bodies.append(body)
            metadata.append(json.loads(meta))
            vectors.append(np.frombuffer(blob, dtype=np.float32))
        matrix = np.stack(vectors)
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        scores = np.divide(matrix @ query, norms, out=np.zeros(len(rows), dtype=np.float32), where=norms > 0)
        indexes = np.argsort(scores)[::-1][:limit]
        return [(bodies[i], metadata[i], float(scores[i])) for i in indexes]

