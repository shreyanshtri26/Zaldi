"""The assistant asks for what it needs: a vague request gets tappable choices, the agent can ask mid-run, and checkout says
exactly which details the secure form wants."""
import pytest
from langchain_core.messages import AIMessage

from tests.test_agent_loop import Scripted, call
from zaldi.agent.loop import run_agent
from zaldi.connectors.local import LocalStore
from zaldi.db import init_db
from zaldi.services import cart, chat_service

S = "sess-ask-1"


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()
    chat_service.get_router.cache_clear()


def test_a_vague_request_gets_a_question_with_category_quick_replies():
    r = chat_service.handle_query("suggest something nice for me", S)
    assert r["products"] == [] and "What are you shopping for" in r["response"]
    assert 1 <= len(r["quick_replies"]) <= 4 and all(isinstance(c, str) for c in r["quick_replies"])


def test_a_specific_request_is_not_interrupted_with_questions():
    r = chat_service.handle_query("suggest a saree under 3000", S)
    assert r["products"] and "What are you shopping for" not in r["response"]   # it answers; any chips are follow-ups, not a question
    assert all(q.startswith("Cheapest") for q in r.get("quick_replies", []))


def test_the_agent_can_ask_with_tappable_answers_and_stops_there():
    llm = Scripted(responses=[call("ask_shopper", {"question": "Which size do you wear?", "options": ["S", "M", "L", "XL", "XXL"]}),
                              AIMessage(content="must not be asked for")], seen=[])
    r = run_agent("compare kurtas and pick one for me", S, LocalStore(), llm)
    assert r["response"] == "Which size do you wear?" and r["quick_replies"] == ["S", "M", "L", "XL"]  # capped at four
    assert len(llm.seen) == 1 and r["steps"][0]["tool"] == "ask_shopper"  # no second model call


def test_checkout_lists_exactly_what_the_secure_form_needs():
    pid = LocalStore().search_products(S, "kurta under 1500")["products"][0]["id"]
    cart.add_item(S, pid)
    r = chat_service.handle_query("i want to checkout", S)
    assert r["action"] == "collect_address"
    for needed in ("full name", "mobile number", "address", "city", "state", "PIN code", "standard or express"):
        assert needed in r["response"]
    assert "secure delivery form" in r["response"]


def test_the_agent_path_also_tells_the_shopper_what_to_fill_in(monkeypatch):
    pid = LocalStore().search_products(S, "kurta under 1500")["products"][0]["id"]
    cart.add_item(S, pid)
    llm = Scripted(responses=[call("start_checkout"), AIMessage(content="All set, please continue.")], seen=[])
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    r = chat_service.handle_query("compare and then order it", S)
    assert r["type"] == "agent" and "full name" in r["response"] and "PIN code" in r["response"]
