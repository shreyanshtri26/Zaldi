"""Semantic router: sends a customer message to discovery, cart, checkout or chitchat."""
import hashlib
import json
import re
from enum import Enum

import numpy as np

from zaldi import config
from zaldi.ai.models import embedding_id, get_embeddings
from zaldi.ai.route_samples import CART_SAMPLES, CHECKOUT_SAMPLES, CHITCHAT_SAMPLES, PRODUCT_SAMPLES


# A cart or checkout route is only believable if the message contains a matching cue word: embeddings alone must
# never decide that a sentence is an instruction to change the cart or place an order.
CART_CUE = re.compile(r"\b(cart|bag|basket|add|remove|delete|buy|quantity|qty|coupon|promo|code|hata\w*|daal|karo)\b", re.I)
CHECKOUT_CUE = re.compile(r"check\s?out|order|pay|purchase|buy|karo", re.I)


class Route(str, Enum):
    PRODUCTS = "products"  # discovery: find products, answer policy questions
    CART = "cart"
    CHECKOUT = "checkout"
    CHITCHAT = "chitchat"


def _cosine_similarity(a, b) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


class SemanticRouter:
    """Picks the route whose example utterances are closest (cosine similarity) to the message."""

    def __init__(self) -> None:
        self._embeddings = get_embeddings()
        self._vectors = {
            Route.PRODUCTS: self._embed_cached(PRODUCT_SAMPLES),
            Route.CART: self._embed_cached(CART_SAMPLES),
            Route.CHECKOUT: self._embed_cached(CHECKOUT_SAMPLES),
            Route.CHITCHAT: self._embed_cached(CHITCHAT_SAMPLES),
        }

    def _embed_cached(self, texts: list[str]) -> list[list[float]]:
        """Samples never change, so embed once per (model, texts) and keep it on disk.

        Saves ~90 API calls per restart (the Gemini free tier allows 100 per minute).
        """
        key = hashlib.sha256((embedding_id() + "\n" + config.EMBEDDING_MODEL + "\n".join(texts)).encode()).hexdigest()[:16]
        path = config.ROUTER_CACHE_DIR / f"{key}.json"
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            vectors = self._embeddings.embed_documents(texts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(vectors))
            return vectors

    def guide(self, query: str) -> Route:
        query_vector = self._embeddings.embed_query(query)
        scores = {route: max(_cosine_similarity(query_vector, v) for v in vectors)
                  for route, vectors in self._vectors.items()}
        if not CART_CUE.search(query):
            scores.pop(Route.CART)
        if not CHECKOUT_CUE.search(query):
            scores.pop(Route.CHECKOUT)
        return max(scores, key=scores.get)
