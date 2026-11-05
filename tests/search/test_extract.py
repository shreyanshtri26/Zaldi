import pytest

from zaldi.db import init_db
from zaldi.search.extract import Filters, extract_filters, merge_defaults


@pytest.fixture(autouse=True)
def db(temp_db):
    init_db()


@pytest.mark.parametrize("text, lo, hi", [
    ("kurta under 2000", None, 2000),
    ("sarees below ₹1,500", None, 1500),
    ("show me lehenga less than 20k", None, 20000),
    ("budget of Rs. 3000", None, 3000),
    ("between 1000 and 3000", 1000, 3000),
    ("above 5000 silk saree", 5000, None),
    ("at least 1.5k", 1500, None),
    ("2000 se kam kurti", None, 2000),
    ("1 lakh tak", None, 100000),
    ("a nice kurta", None, None),
    ("size 40 jacket", None, None),  # a size is not a price
])
def test_price(text, lo, hi):
    f = extract_filters(text)
    assert (f.min_price, f.max_price) == (lo, hi)


def test_full_sentence():
    f = extract_filters("I need a red cotton kurta for men in size XL under 2500")
    assert f.category == "Kurta" and f.colors == ("red",) and "cotton" in f.materials
    assert f.genders == ("Men", "Unisex") and f.size == "XL" and f.max_price == 2500


def test_women_is_not_men():
    assert extract_filters("kurti for women").genders == ("Women", "Unisex")


def test_longest_category_wins_and_plural():
    assert extract_filters("kurta sets").category == "Kurta Set"
    assert extract_filters("show sarees").category == "Saree"
    assert extract_filters("sari").category == "Saree"


def test_color_phrase_and_hindi():
    assert extract_filters("navy blue jacket").colors == ("navy blue",)
    assert extract_filters("lal saree").colors == ("red",)
    assert extract_filters("something royal and festive").colors == ()  # a vibe, not a colour


def test_brand_and_kids_size():
    assert extract_filters("anything from Biba Style").brand == "Biba Style"
    assert extract_filters("kidswear 4-5 years").size == "4-5 Y"


def test_empty_and_noise():
    assert extract_filters("").is_empty() and extract_filters("hello there").is_empty()


def test_explicit_beats_saved_preferences():
    prefs = Filters(max_price=1000, brand="Biba Style", genders=("Women", "Unisex"))
    merged = merge_defaults(Filters(max_price=3000, category="Kurta"), prefs)
    assert merged.max_price == 3000 and merged.brand == "Biba Style" and merged.genders == ("Women", "Unisex")
