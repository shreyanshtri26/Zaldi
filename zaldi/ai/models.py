"""Factories for the chat model and the embedding model (created lazily, so the CMS runs without API keys)."""
import hashlib
import re
from functools import lru_cache

import numpy as np
from langchain_core.embeddings import Embeddings

from zaldi import config


def _google_key() -> str | None:
    from zaldi.services import ai_key

    return ai_key.key_for("google")


def get_llm(provider: str | None = None, model: str | None = None):
    """The chat model. With no arguments: the provider, model and key this store chose in the dashboard, else the server's. A provider
    or model named explicitly (the cheap-model and fallback settings do) is used as given, with that provider's key."""
    from zaldi.services import ai_key

    provider = provider or ai_key.effective_provider()
    model = model or ai_key.chosen_model(provider) or ai_key.default_model(provider)
    key = ai_key.key_for(provider)
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(temperature=0, model=model, api_key=key, max_retries=1, timeout=15)
    from langchain_google_genai import ChatGoogleGenerativeAI

    # One retry and a short timeout: if the model is rate limited, the plain-text fallback answers in seconds, not ~40s.
    return ChatGoogleGenerativeAI(temperature=0, model=model, google_api_key=key, max_retries=1, timeout=15)


def get_fallback_llm():
    """The optional second model (``LLM_FALLBACK_PROVIDER``/``LLM_FALLBACK_MODEL``), or ``None`` when not configured."""
    from zaldi.services import ai_key

    provider, model = config.LLM_FALLBACK_PROVIDER, config.LLM_FALLBACK_MODEL
    if not provider or not model or (provider, model) == (config.LLM_PROVIDER, config.LLM_MODEL):
        return None
    if not ai_key.key_for("groq" if provider == "groq" else "google"):
        return None
    return get_llm(provider, model)


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


def embedding_provider() -> str:
    """``local`` or ``google``. A store with its own Gemini key gets real embeddings even if the server has none (unless the server
    pins ``EMBEDDING_PROVIDER`` explicitly)."""
    import os

    from zaldi.services import ai_key

    if config.EMBEDDING_PROVIDER == "local" and not os.getenv("EMBEDDING_PROVIDER") and ai_key.own_key():
        return "google"
    return config.EMBEDDING_PROVIDER


def embedding_id() -> str:
    """Names the active embedding space; cached vectors and indexes are only valid for the id they were built with."""
    provider = embedding_provider()
    return "local" if provider == "local" else f"{provider}:{config.EMBEDDING_MODEL}"


@lru_cache(maxsize=4)
def _embeddings_for(provider: str, model: str, api_key: str | None):
    if provider == "local":
        return HashingEmbeddings()
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=model, google_api_key=api_key)


def get_embeddings():
    return _embeddings_for(embedding_provider(), config.EMBEDDING_MODEL, _google_key())
