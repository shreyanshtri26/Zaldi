"""Vector store for the catalogue (FAISS). Only searchable text is embedded; price and stock are read live from SQL.

The index records a fingerprint of (embedding space, product texts), so it rebuilds itself after any product edit or
embedding-provider change: no invalidation hooks needed.
"""
import hashlib
import json

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from zaldi import config
from zaldi.ai.models import embedding_id, get_embeddings
from zaldi.db import content_repo

TEXT_FIELDS = ("product_name", "category", "material", "color", "brand", "gender", "description")


def product_documents() -> list[Document]:
    docs = []
    for row in content_repo.list_rows("products"):
        text = ". ".join(f"{f.replace('_', ' ')}: {row[f]}" for f in TEXT_FIELDS if row.get(f))
        docs.append(Document(page_content=text, metadata={"id": row["id"]}))
    return docs


def _fingerprint(docs: list[Document]) -> str:
    blob = embedding_id() + "\n" + "\n".join(f"{d.metadata['id']}|{d.page_content}" for d in docs)
    return hashlib.sha256(blob.encode()).hexdigest()


def build_index(docs: list[Document] | None = None) -> tuple[FAISS | None, int]:
    """Embed the catalogue and persist it. Returns (store, product count); store is None for an empty catalogue."""
    docs = product_documents() if docs is None else docs
    index_dir = config.PRODUCT_INDEX_DIR
    if not docs:
        return None, 0
    store = FAISS.from_documents(docs, get_embeddings())
    index_dir.mkdir(parents=True, exist_ok=True)
    store.save_local(str(index_dir))
    (index_dir / "fingerprint.json").write_text(json.dumps({"fingerprint": _fingerprint(docs)}))
    return store, len(docs)


def get_index() -> FAISS | None:
    docs = product_documents()
    if not docs:
        return None
    meta = config.PRODUCT_INDEX_DIR / "fingerprint.json"
    try:
        fresh = json.loads(meta.read_text())["fingerprint"] == _fingerprint(docs)
    except (OSError, ValueError, KeyError):
        fresh = False
    if fresh:
        return FAISS.load_local(str(config.PRODUCT_INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True)
    return build_index(docs)[0]


def vector_search(query: str, k: int = 50) -> list[int]:
    """Product ids ordered by semantic similarity to ``query`` (best first)."""
    store = get_index()
    if store is None:
        return []
    return [d.metadata["id"] for d in store.similarity_search(query, k=k)]
