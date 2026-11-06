"""Policy search tool: semantic (FAISS) search over the ``policies`` table, fused with keyword matching.

Every chunk carries its section title, so an answer can say where it came from and a later chunk never loses its context
("Refunds for prepaid orders..." is still labelled REFUNDS). Ranking combines the vector order with keyword overlap
(reciprocal rank fusion, the same idea the product search uses).
"""
import re

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from zaldi import stores
from zaldi.ai.models import embedding_id, get_embeddings
from zaldi.db import content_repo

TOP_K = 5
RRF_K = 60
FETCH_FACTOR = 4  # over-fetch from the vector index, then keep the best k after fusion
GENERIC = {"what", "your", "policy", "policie", "with", "about", "does", "have", "this", "that", "from", "will", "when"}


def get_vectorstore() -> FAISS:
    """Load the FAISS index, or build it from the policies table (it is deleted whenever policies change)."""
    folder = stores.policy_index_dir()
    index_dir = str(folder)
    marker = folder / "embedding.id"
    if (folder / "index.faiss").exists() and marker.exists() and marker.read_text() == embedding_id():
        return FAISS.load_local(index_dir, get_embeddings(), allow_dangerous_deserialization=True)
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = [Document(page_content=f"{p['title']}\n{part}", metadata={"title": p["title"]})
              for p in content_repo.list_rows("policies") for part in splitter.split_text(p["content"])]
    store = FAISS.from_documents(chunks, get_embeddings())
    store.save_local(index_dir)
    marker.write_text(embedding_id())  # an index is only valid for the embedding space that built it
    return store


def _terms(query: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{3,}", query.lower())} - GENERIC


def search_policy_chunks(query: str, k: int = TOP_K) -> list[dict]:
    """The ``k`` best chunks as ``{"title", "text"}``, best first."""
    hits = get_vectorstore().similarity_search(query, k=k * FETCH_FACTOR)
    terms = _terms(query)
    overlap = [sum(1 for t in terms if t in h.page_content.lower()) for h in hits]
    keyword_order = sorted(range(len(hits)), key=lambda i: -overlap[i])
    keyword_rank = {i: r for r, i in enumerate(keyword_order) if overlap[i] > 0}
    fused = {i: 1 / (RRF_K + i) + (1 / (RRF_K + keyword_rank[i]) if i in keyword_rank else 0) for i in range(len(hits))}
    seen, out = set(), []
    for i in sorted(fused, key=lambda i: -fused[i]):
        text = hits[i].page_content
        if text not in seen:
            seen.add(text)
            out.append({"title": hits[i].metadata.get("title", ""), "text": text})
    return out[:k]


def search_policies(query: str, k: int = TOP_K) -> list[str]:
    """Store-policy excerpts most relevant to ``query``; each starts with its section title (the citation)."""
    return [c["text"] for c in search_policy_chunks(query, k)]
