"""Retrieval quality of the product search, scored per method so each part of the hybrid is shown to earn its place.

Queries are generated from the catalogue itself and labelled by rule (a product is relevant when it really has the attributes
the query names), in three flavours: plain attributes ("red cotton kurta"), Hinglish and spelling variants ("lal sari"),
and budgets ("sherwani under 8000"). Labels are rule-made, not human-made: they test ranking consistency, not taste.
"""
import re
from dataclasses import replace
from math import log2

from zaldi.db import connect
from zaldi.search import hybrid
from zaldi.search.extract import Filters, extract_filters
from zaldi.search.index import vector_search

K = 6
HINGLISH = {"Saree": "sari", "Lehenga": "lehnga", "Footwear": "shoes", "Jewellery": "jewelry", "Bottomwear": "pants"}
COLORS_HI = {"red": "lal", "blue": "neela", "white": "safed", "black": "kala", "green": "hara", "yellow": "peela", "pink": "gulabi"}


def _products() -> list[dict]:
    with connect(readonly=True) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM products WHERE stock_quantity > 0 ORDER BY id")]


def golden_set(products: list[dict] | None = None) -> list[dict]:
    """``[{"query", "kind", "relevant": {product ids}}]`` built from the catalogue; deterministic."""
    products = products or _products()
    cases: list[dict] = []

    def add(query, kind, test):
        rel = {p["id"] for p in products if test(p)}
        if rel and len(rel) < len(products):
            cases.append({"query": query, "kind": kind, "relevant": rel})

    cats = sorted({p["category"] for p in products})
    for cat in cats:
        add(cat.lower(), "attribute", lambda p, c=cat: p["category"] == c)
        if cat in HINGLISH:
            add(HINGLISH[cat], "variant", lambda p, c=cat: p["category"] == c)
    for p in products:
        first_color = p["color"].split()[-1].lower()  # "Navy Blue" -> blue
        add(f"{first_color} {p['category'].lower()}", "attribute", lambda q, c=p["category"], col=first_color: q["category"] == c and col in q["color"].lower())
        mat = p["material"].split()[0].lower()
        add(f"{mat} {p['category'].lower()}", "attribute", lambda q, c=p["category"], m=mat: q["category"] == c and m in q["material"].lower())
        add(f"{p['brand'].lower()}", "attribute", lambda q, b=p["brand"]: q["brand"] == b)
        ceiling = (int(p["price"]) // 500 + 1) * 500
        add(f"{p['category'].lower()} under {ceiling}", "budget", lambda q, c=p["category"], m=ceiling: q["category"] == c and q["price"] <= m)
        if first_color in COLORS_HI and p["category"] in HINGLISH:
            add(f"{COLORS_HI[first_color]} {HINGLISH[p['category']]}", "variant", lambda q, c=p["category"], col=first_color: q["category"] == c and col in q["color"].lower())
    seen, unique = set(), []
    for c in cases:
        if c["query"] not in seen:
            seen.add(c["query"])
            unique.append(c)
    return unique


# --- the four methods: each maps a query to a ranked list of product ids -------------------------------------------

def lexical_only(query: str) -> list[int]:
    rows = hybrid._candidates(Filters(in_stock=False))
    terms = [t for t in re.findall(r"\w+", query.lower()) if t not in hybrid.STOPWORDS and not t.isdigit()]
    scored = [(hybrid._lexical_score(r, terms), r["id"]) for r in rows]
    return [pid for score, pid in sorted(scored, key=lambda x: (-x[0], x[1])) if score > 0]


def vector_only(query: str) -> list[int]:
    return vector_search(query)


def hybrid_rrf(query: str) -> list[int]:
    rows, _ = hybrid.search(query, Filters(in_stock=False), limit=50)
    return [r["id"] for r in rows]


def full_pipeline(query: str) -> list[int]:
    """What a shopper really gets: extracted filters (budget, colour...) plus hybrid ranking."""
    rows, _ = hybrid.search(query, replace(extract_filters(query), in_stock=True), limit=50)
    return [r["id"] for r in rows]


METHODS = {"keyword only": lexical_only, "meaning only": vector_only, "hybrid (RRF)": hybrid_rrf, "full pipeline": full_pipeline}


def score(ranked: list[int], relevant: set[int], k: int = K) -> dict:
    top = ranked[:k]
    hits = [1 if pid in relevant else 0 for pid in top]
    dcg = sum(h / log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / log2(i + 2) for i in range(min(len(relevant), k)))
    first = next((i for i, h in enumerate(hits) if h), None)
    return {"hit": 1.0 if any(hits) else 0.0, "mrr": 1 / (first + 1) if first is not None else 0.0,
            "ndcg": dcg / ideal if ideal else 0.0, "recall": sum(hits) / min(len(relevant), k)}


def evaluate(cases: list[dict] | None = None) -> dict:
    """``{method: {"overall": {metric: value}, "by_kind": {kind: {...}}}, "queries": n}`` (all averages over queries)."""
    cases = cases or golden_set()
    out: dict = {"queries": len(cases), "k": K, "methods": {}}
    for name, method in METHODS.items():
        rows = [(c["kind"], score(method(c["query"]), c["relevant"])) for c in cases]

        def mean(items):
            return {m: round(sum(r[m] for r in items) / len(items), 3) for m in ("hit", "mrr", "ndcg", "recall")} if items else {}

        out["methods"][name] = {"overall": mean([r for _, r in rows]),
                                "by_kind": {kind: mean([r for k2, r in rows if k2 == kind]) for kind in sorted({k for k, _ in rows})}}
    return out
