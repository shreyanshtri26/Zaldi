"""Vector search stored in Postgres (pgvector), used instead of the FAISS files when ``DATABASE_URL`` is set.

Each store keeps its vectors in its own schema, so one store's embeddings can never leak into another's results. A ``kind`` ("products",
"policies") separates the indexes; each has a fingerprint, so an index rebuilds itself when the data or the embedding model changes.
The object it returns has the one method the app uses, ``similarity_search``, with the same result shape as FAISS.
"""
import json

from langchain_core.documents import Document

from zaldi.db import connect


def _literal(vector) -> str:
    return "[" + ",".join(f"{float(x):.7g}" for x in vector) + "]"


def fingerprint(kind: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT fingerprint FROM vector_meta WHERE kind = ?", (kind,)).fetchone()
    return row["fingerprint"] if row else None


def invalidate(kind: str) -> None:
    """Forget an index (its data changed): the next search rebuilds it."""
    with connect() as conn:
        conn.execute("DELETE FROM vectors WHERE kind = ?", (kind,))
        conn.execute("DELETE FROM vector_meta WHERE kind = ?", (kind,))


class PgVectorStore:
    def __init__(self, kind: str, embeddings):
        self.kind, self.embeddings = kind, embeddings

    @classmethod
    def build(cls, kind: str, docs: list[Document], embeddings, fp: str) -> "PgVectorStore":
        vectors = embeddings.embed_documents([d.page_content for d in docs])
        with connect() as conn:
            conn.execute("DELETE FROM vectors WHERE kind = ?", (kind,))
            for doc, vec in zip(docs, vectors):
                conn.execute("INSERT INTO vectors (kind, content, meta, embedding) VALUES (?, ?, ?, ?::vector)",
                             (kind, doc.page_content, json.dumps(doc.metadata), _literal(vec)))
            conn.execute("DELETE FROM vector_meta WHERE kind = ?", (kind,))
            conn.execute("INSERT INTO vector_meta (kind, fingerprint) VALUES (?, ?)", (kind, fp))
        return cls(kind, embeddings)

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        literal = _literal(self.embeddings.embed_query(query))
        with connect() as conn:
            rows = conn.execute("SELECT content, meta FROM vectors WHERE kind = ? ORDER BY embedding <=> ?::vector LIMIT ?",
                                (self.kind, literal, int(k))).fetchall()
        return [Document(page_content=r["content"], metadata=json.loads(r["meta"])) for r in rows]
