"""Retrieval quality: for real shopper questions, the right policy section must be in the top results.
Runs offline with the hashing embedder, so it measures the whole retrieval path (chunking, fusion), not a model."""
import pytest

from zaldi.ai.tools.policy_search import search_policy_chunks, search_policies
from zaldi.db import init_db

CASES = [
    ("how many days do I have to return a kurta", "RETURNS & EXCHANGES"),
    ("is cash on delivery available", "PAYMENT OPTIONS"),
    ("when will I get my refund", "REFUNDS"),
    ("can I change my delivery address after ordering", "ORDER CANCELLATION & ADDRESS CHANGE"),
    ("how do I wash a chikankari kurta", "CARE INSTRUCTIONS"),
    ("which size should I pick if I am between two sizes", "SIZE & FIT GUIDE"),
    ("do you give a GST invoice", "GST & INVOICES"),
    ("any discount for my first order", "OFFERS & LOYALTY"),
    ("is the silk genuine and certified", "WARRANTY & AUTHENTICITY"),
    ("customer care phone number and support hours", "CUSTOMER SUPPORT"),
    ("do you sell my personal data", "PRIVACY"),
    ("how long does delivery take to Mumbai", "SHIPPING & DELIVERY"),
    ("is shipping free above a certain amount", "SHIPPING & DELIVERY"),
    ("can I cancel my order before it ships", "ORDER CANCELLATION & ADDRESS CHANGE"),
]


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()


@pytest.mark.parametrize("question, title", CASES)
def test_the_right_policy_is_in_the_top_three(question, title):
    assert title in [c["title"] for c in search_policy_chunks(question, k=3)]


def test_the_top_hit_is_right_for_most_questions():
    top = sum(1 for q, title in CASES if search_policy_chunks(q, k=1)[0]["title"] == title)
    assert top / len(CASES) >= 0.7  # guards against a retrieval regression


def test_every_excerpt_carries_its_section_title():
    for text in search_policies("how do I wash silk sarees", k=4):
        assert text.split("\n", 1)[0].isupper()  # the citation line, e.g. "CARE INSTRUCTIONS"
