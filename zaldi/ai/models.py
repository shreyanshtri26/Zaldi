"""Factories for the chat model and the embedding model (created lazily, so the CMS runs without API keys)."""
import hashlib
import re
from functools import lru_cache

import numpy as np
from langchain_core.embeddings import Embeddings

from zaldi import config


def get_llm():
    if config.LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(temperature=0, model=config.LLM_MODEL, api_key=config.GROQ_API_KEY)
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(temperature=0, model=config.LLM_MODEL, google_api_key=config.GOOGLE_API_KEY)


class HashingEmbeddings(Embeddings):
    """Offline bag-of-words embeddings (hashed unigrams + bigrams). No API, deterministic; matches words, not meaning."""

    DIM = 512

    def _vector(self, text: str) -> list[float]:
        words = re.findall(r"\w+", text.lower())
        vec = np.zeros(self.DIM, dtype=np.float32)
        for token in words + [f"{a}_{b}" for a, b in zip(words, words[1:])]:
            h = int.from_bytes(hashlib.md5(token.encode()).digest()[:8], "big")
            vec[h % self.DIM] += 1.0 if (h >> 63) else -1.0
        norm = np.linalg.norm(vec)
        return (vec / norm if norm else vec).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def embedding_id() -> str:
    """Names the active embedding space; cached vectors and indexes are only valid for the id they were built with."""
    return "local" if config.EMBEDDING_PROVIDER == "local" else f"{config.EMBEDDING_PROVIDER}:{config.EMBEDDING_MODEL}"


@lru_cache(maxsize=4)
def _embeddings_for(provider: str, model: str, api_key: str | None):
    if provider == "local":
        return HashingEmbeddings()
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=model, google_api_key=api_key)


def get_embeddings():
    return _embeddings_for(config.EMBEDDING_PROVIDER, config.EMBEDDING_MODEL, config.GOOGLE_API_KEY)
