"""Policy search tool: semantic (FAISS) search over the ``policies`` table."""
import re

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from zaldi import config
from zaldi.ai.models import embedding_id, get_embeddings
from zaldi.db import content_repo

TOP_K = 5


def get_vectorstore() -> FAISS:
    """Load the FAISS index, or build it from the policies table (it is deleted whenever policies change)."""
    index_dir = str(config.POLICY_INDEX_DIR)
    marker = config.POLICY_INDEX_DIR / "embedding.id"
    if (config.POLICY_INDEX_DIR / "index.faiss").exists() and marker.exists() and marker.read_text() == embedding_id():
        return FAISS.load_local(index_dir, get_embeddings(), allow_dangerous_deserialization=True)
    documents = [Document(page_content=f"{p['title']}\n{p['content']}", metadata={"title": p["title"]})
                 for p in content_repo.list_rows("policies")]
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(documents)
    store = FAISS.from_documents(chunks, get_embeddings())
    store.save_local(index_dir)
    marker.write_text(embedding_id())  # an index is only valid for the embedding space that built it
    return store


def search_policies(query: str, k: int = TOP_K) -> list[str]:
    """Store-policy excerpts most relevant to ``query``: vector search over-fetched, then re-ranked by shared keywords."""
    hits = [doc.page_content for doc in get_vectorstore().similarity_search(query, k=k * 3)]
    terms = {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", query.lower())} - {"what", "your", "policy", "policie", "with", "about", "does", "have"}
    overlap = lambda text: sum(1 for t in terms if t in text.lower())  # noqa: E731
    return sorted(hits, key=lambda h: -overlap(h))[:k]  # sorted() is stable: ties keep vector order
