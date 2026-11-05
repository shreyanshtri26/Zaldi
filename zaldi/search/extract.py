"""Entity extraction: turn a free-text shopping message into structured catalogue filters.

Rule-based on purpose: it is instant, free, works offline and is easy to test. Attribute vocabularies (categories,
colours, brands, materials) are read from the catalogue itself, so new products are understood without code changes.
"Vibes" that no filter captures ("something festive and royal") are left to the vector half of hybrid search.
"""
import re
from dataclasses import asdict, dataclass, replace

from zaldi.db import connect

# Words customers use that differ from the catalogue's vocabulary.
CATEGORY_SYNONYMS = {
    "sari": "Saree", "lehnga": "Lehenga", "ghagra": "Lehenga", "shoes": "Footwear", "sandals": "Footwear",
    "juttis": "Footwear", "jutti": "Footwear", "mojari": "Footwear", "jewelry": "Jewellery", "jewellery": "Jewellery",
    "necklace": "Jewellery", "earrings": "Jewellery", "pants": "Bottomwear", "trousers": "Bottomwear",
    "palazzo": "Bottomwear", "churidar": "Bottomwear", "shirts": "Shirt", "blazer": "Jacket", "coat": "Jacket",
    "dupattas": "Dupatta", "stole": "Dupatta", "anarkali": "Kurta Set",
}
COLOR_SYNONYMS = {"lal": "red", "neela": "blue", "safed": "white", "kala": "black", "hara": "green",
                  "peela": "yellow", "gulabi": "pink", "kesariya": "orange", "sunehri": "gold"}
GENDER_WORDS = {
    "men": ["Men", "Unisex"], "mens": ["Men", "Unisex"], "man": ["Men", "Unisex"], "male": ["Men", "Unisex"],
    "gents": ["Men", "Unisex"], "groom": ["Men", "Unisex"], "him": ["Men", "Unisex"], "husband": ["Men", "Unisex"],
    "women": ["Women", "Unisex"], "womens": ["Women", "Unisex"], "woman": ["Women", "Unisex"],
    "ladies": ["Women", "Unisex"], "female": ["Women", "Unisex"], "bride": ["Women", "Unisex"],
    "wife": ["Women", "Unisex"], "boys": ["Boys"], "boy": ["Boys"], "girls": ["Girls"], "girl": ["Girls"],
    "kids": ["Boys", "Girls", "Unisex"], "kid": ["Boys", "Girls", "Unisex"], "children": ["Boys", "Girls", "Unisex"],
}
GENERIC_WORDS = {"blend", "art", "pure", "faux", "multicolor", "off", "royal", "pastel", "peacock", "rust", "sky"}  # never a filter on their own
SIZE_RE = re.compile(r"\b(?:size\s*(xxxl|xxl|xl|xs|s|m|l|\d{1,2})|(xxxl|xxl|xl|xs)\b)", re.I)
KIDS_SIZE_RE = re.compile(r"\b(\d{1,2}\s*-\s*\d{1,2})\s*(?:y|yrs?|years?)\b", re.I)

_AMOUNT = r"(?:rs\.?|₹|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?)?\b"
MAX_RE = re.compile(r"(?:under|below|less than|within|upto|up to|max(?:imum)?|not more than|at most|budget(?: of| is)?|<=?)\s*" + _AMOUNT, re.I)
MIN_RE = re.compile(r"(?:above|over|more than|at least|min(?:imum)?|starting (?:from|at)|>=?)\s*" + _AMOUNT, re.I)
RANGE_RE = re.compile(r"between\s*" + _AMOUNT + r"\s*(?:and|to|-)\s*" + _AMOUNT, re.I)
HI_MAX_RE = re.compile(_AMOUNT + r"\s*(?:se kam|tak|ke andar|ke niche|ke ander)", re.I)
HI_MIN_RE = re.compile(_AMOUNT + r"\s*(?:se upar|se zyada|se jyada|ke upar)", re.I)


@dataclass(frozen=True)
class Filters:
    category: str | None = None
    colors: tuple[str, ...] = ()  # lower-case fragments, matched with LIKE
    materials: tuple[str, ...] = ()
    genders: tuple[str, ...] = ()
    brand: str | None = None
    exclude_brands: tuple[str, ...] = ()
    size: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    in_stock: bool = True

    def is_empty(self) -> bool:
        return not any((self.category, self.colors, self.materials, self.genders, self.brand, self.size,
                        self.min_price, self.max_price))

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, (), False)}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9₹]+", " ", text.lower())).strip()


def _amount(number: str, unit: str | None) -> int:
    value = float(number.replace(",", ""))
    unit = (unit or "").lower()
    if unit in ("k", "thousand"):
        value *= 1000
    elif unit.startswith(("lakh", "lac")):
        value *= 100000
    return int(value)


def _vocab(column: str) -> list[str]:
    with connect(readonly=True) as conn:
        return [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM products WHERE {column} IS NOT NULL")]


def _phrase_matches(text: str, phrases: dict[str, str]) -> list[str]:
    """Values whose phrase occurs in ``text`` (plural 's' allowed). Longest phrases claim their words first."""
    found = []
    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = rf"\b{re.escape(phrase)}s?\b"
        if re.search(pattern, text):
            found.append(phrases[phrase])
            text = re.sub(pattern, " ", text)
    return found


def _prices(text: str) -> tuple[int | None, int | None]:
    lo = hi = None
    if m := RANGE_RE.search(text):
        a, b = _amount(m[1], m[2]), _amount(m[3], m[4])
        lo, hi = min(a, b), max(a, b)
        text = RANGE_RE.sub(" ", text)
    if hi is None and (m := MAX_RE.search(text) or HI_MAX_RE.search(text)):
        hi = _amount(m[1], m[2])
    if lo is None and (m := MIN_RE.search(text) or HI_MIN_RE.search(text)):
        lo = _amount(m[1], m[2])
    return lo, hi


def extract_filters(query: str) -> Filters:
    text = _norm(query)

    categories = {_norm(c): c for c in _vocab("category")} | {k: v for k, v in CATEGORY_SYNONYMS.items()}
    category = next(iter(_phrase_matches(text, categories)), None)

    brands = {_norm(b): b for b in _vocab("brand")}
    brand = next(iter(_phrase_matches(text, brands)), None)

    color_words = {w for c in _vocab("color") for w in _norm(c).split()} - GENERIC_WORDS
    color_phrases = {_norm(c): _norm(c) for c in _vocab("color") if " " in c}
    words = [COLOR_SYNONYMS.get(w, w) for w in text.split()]
    color_text = " ".join(words)
    colors = _phrase_matches(color_text, color_phrases)
    for phrase in colors:
        color_text = color_text.replace(phrase, " ")
    colors += [w for w in color_text.split() if w in color_words]

    material_words = {w for m in _vocab("material") for w in _norm(m).split()} - GENERIC_WORDS - color_words
    materials = [w for w in text.split() if w in material_words]

    genders: list[str] = []
    for word in text.split():
        for g in GENDER_WORDS.get(word, []):
            if g not in genders:
                genders.append(g)

    size = None
    if m := KIDS_SIZE_RE.search(query):
        size = re.sub(r"\s", "", m[1]) + " Y"
    elif m := SIZE_RE.search(query):
        size = (m[1] or m[2]).upper()
    elif "free size" in text:
        size = "Free Size"

    lo, hi = _prices(query)
    return Filters(category=category, colors=tuple(dict.fromkeys(colors)), materials=tuple(dict.fromkeys(materials)),
                   genders=tuple(genders), brand=brand, size=size, min_price=lo, max_price=hi)


def merge_defaults(explicit: Filters, defaults: Filters) -> Filters:
    """What the customer said now wins; saved preferences only fill the gaps."""
    pick = {}
    for f in ("category", "brand", "size", "min_price", "max_price"):
        pick[f] = getattr(explicit, f) if getattr(explicit, f) is not None else getattr(defaults, f)
    for f in ("colors", "materials", "genders"):
        pick[f] = getattr(explicit, f) or getattr(defaults, f)
    pick["exclude_brands"] = tuple(b for b in defaults.exclude_brands if b.lower() != (explicit.brand or "").lower())
    return replace(explicit, **pick)
