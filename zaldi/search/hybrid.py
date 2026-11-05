"""Hybrid product search: hard SQL filters + vector similarity (style) + lexical match (exact words), fused with RRF."""
import re
from dataclasses import replace

from zaldi.db import connect
from zaldi.search.extract import Filters
from zaldi.search.index import vector_search

RRF_K = 60
STOPWORDS = set("a an the and or for of in on with to me my i is are do you have any show find want need looking look "
                "please some something under below above over than less more rs rupees budget size kya hai ka ke ki "
                "dikhao chahiye mujhe se aur".split())
# Filters dropped, in this order, when nothing matches all of them (budget and category are never relaxed).
RELAX_ORDER = ("materials", "colors", "size", "brand", "genders")


def _where(f: Filters) -> tuple[str, list]:
    clauses, args = [], []
    if f.in_stock:
        clauses.append("stock_quantity > 0")
    if f.min_price is not None:
        clauses.append("price >= ?")
        args.append(f.min_price)
    if f.max_price is not None:
        clauses.append("price <= ?")
        args.append(f.max_price)
    if f.category:
        clauses.append("category = ? COLLATE NOCASE")
        args.append(f.category)
    if f.brand:
        clauses.append("brand = ? COLLATE NOCASE")
        args.append(f.brand)
    if f.exclude_brands:
        clauses.append(f"(brand IS NULL OR brand COLLATE NOCASE NOT IN ({','.join('?' * len(f.exclude_brands))}))")
        args += f.exclude_brands
    if f.genders:
        clauses.append(f"gender IN ({','.join('?' * len(f.genders))})")
        args += f.genders
    if f.colors:
        clauses.append("(" + " OR ".join("LOWER(color) LIKE ?" for _ in f.colors) + ")")
        args += [f"%{c.lower()}%" for c in f.colors]
    for word in f.materials:
        clauses.append("(LOWER(material) LIKE ? OR LOWER(product_name) LIKE ?)")
        args += [f"%{word}%"] * 2
    if f.size:
        clauses.append("(',' || REPLACE(LOWER(size), ' ', '') || ',') LIKE ?")
        args.append(f"%,{f.size.lower().replace(' ', '')},%")
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", args


def _candidates(f: Filters) -> list[dict]:
    where, args = _where(f)
    with connect(readonly=True) as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM products{where} ORDER BY id", args)]


def _lexical_score(row: dict, terms: list[str]) -> float:
    weighted = (("product_name", 3), ("brand", 2), ("category", 2), ("color", 2), ("material", 1.5), ("description", 1))
    score = 0.0
    for field, weight in weighted:
        words = set(re.findall(r"\w+", (row.get(field) or "").lower()))
        score += weight * sum(1 for t in terms if t in words or (len(t) > 3 and t.rstrip("s") in words))
    return score


def search(query: str, filters: Filters, limit: int = 6) -> tuple[list[dict], list[str]]:
    """Best ``limit`` products for ``query`` under ``filters``, plus the names of any filters dropped to find matches."""
    dropped: list[str] = []
    rows = _candidates(filters)
    for name in RELAX_ORDER:
        if rows or not getattr(filters, name):
            continue
        filters = replace(filters, **{name: type(getattr(filters, name))()})
        dropped.append(name)
        rows = _candidates(filters)
    if not rows:
        return [], dropped

    by_id = {r["id"]: r for r in rows}
    vector_rank = {pid: i for i, pid in enumerate(p for p in vector_search(query) if p in by_id)}
    terms = [t for t in re.findall(r"\w+", query.lower()) if t not in STOPWORDS and not t.isdigit()]
    scores = {r["id"]: _lexical_score(r, terms) for r in rows}
    lexical_rank = {pid: i for i, pid in enumerate(sorted((p for p in scores if scores[p] > 0), key=lambda p: -scores[p]))}

    def fused(pid: int) -> float:
        return sum(1 / (RRF_K + rank[pid]) for rank in (vector_rank, lexical_rank) if pid in rank)

    ordered = sorted(by_id, key=lambda pid: (-fused(pid), by_id[pid]["price"], pid))
    return [by_id[pid] for pid in ordered[:limit]], dropped
