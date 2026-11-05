import pytest

from zaldi.db import content_repo, init_db
from zaldi.search.extract import Filters, extract_filters, merge_defaults
from zaldi.search.hybrid import search
from zaldi.services import preferences


@pytest.fixture(autouse=True)
def db(temp_db):
    init_db()


def find(text, extra=None, limit=6):
    f = extract_filters(text)
    return search(text, merge_defaults(f, extra) if extra else f, limit)


def test_budget_is_a_hard_limit():
    rows, _ = find("kurta under 1500")
    assert rows and all(r["price"] <= 1500 and r["category"] == "Kurta" for r in rows)


def test_out_of_stock_hidden():
    p = content_repo.list_rows("products")[0]
    content_repo.update_row("products", p["id"], {"stock_quantity": 0})
    rows, _ = search(p["product_name"], Filters(category=p["category"]), limit=50)
    assert p["id"] not in [r["id"] for r in rows]


def test_exact_brand_via_lexical_and_filter():
    rows, _ = find("anything from Biba Style")
    assert rows and all(r["brand"] == "Biba Style" for r in rows)


def test_size_filter_matches_whole_size_token():
    rows, _ = find("shirt in size XL")
    assert all("XL" in [s.strip() for s in r["size"].split(",")] for r in rows)
    assert not any(r["size"] == "S, M, L" for r in rows)  # 'L' must not match 'XL' and vice versa


def test_vibe_query_uses_lexical_and_vector_ranking():
    rows, _ = find("banarasi silk saree with zari border")
    assert "Banarasi" in rows[0]["product_name"]


def test_filters_relax_when_nothing_matches_and_say_so():
    rows, dropped = search("saree", Filters(category="Saree", colors=("no-such-colour",)))
    assert rows and dropped == ["colors"]
    assert all(r["category"] == "Saree" for r in rows)  # category is never relaxed


def test_budget_never_relaxed():
    rows, dropped = find("saree under 100")
    assert rows == []


def test_gibberish_does_not_crash():
    assert isinstance(find("zzzz qqqq")[0], list)


def test_limit_respected():
    assert len(find("kurta", limit=2)[0]) <= 2


def test_preferences_are_injected_and_overridden():
    preferences.save_preferences("s1", {"max_price": 2000, "exclude_brands": "Biba Style", "gender": "Women"})
    prefs = preferences.preference_filters("s1")
    rows, _ = find("show me kurtas", prefs)
    assert rows and all(r["price"] <= 2000 and r["brand"] != "Biba Style" for r in rows)
    assert all(r["gender"] in ("Women", "Unisex") for r in rows)
    rows, _ = find("saree under 20000", prefs)  # explicit budget beats the saved one
    assert any(r["price"] > 2000 for r in rows)


def test_preference_validation_and_clear():
    with pytest.raises(Exception):
        preferences.save_preferences("s1", {"max_price": "lots"})
    with pytest.raises(Exception):
        preferences.save_preferences("s1", {"gender": "Alien"})
    preferences.save_preferences("s1", {"max_price": 500})
    assert preferences.save_preferences("s1", {})["max_price"] is None
