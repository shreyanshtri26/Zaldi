"""The agent's tool steps are saved with the chat log and returned to the admin."""
import pytest
from langchain_core.messages import AIMessage

from tests.test_agent_loop import Scripted, call
from zaldi.db import chat_log_repo, init_db
from zaldi.services import chat_service

S = "sess-trace-1"


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()
    chat_service.get_router.cache_clear()


def test_agent_steps_are_saved_and_read_back(monkeypatch):
    llm = Scripted(responses=[call("search_products", {"query": "kurta"}), AIMessage(content="Here are kurtas.")], seen=[])
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    chat_service.handle_query("compare kurtas and show the cheaper one", S)
    row = chat_log_repo.recent_logs(1)[0]
    assert row["route"] == "agent"
    assert [s["tool"] for s in row["steps"]] == ["search_products"] and row["steps"][0]["ok"] is True


def test_fixed_pipeline_chats_have_no_steps():
    chat_service.handle_query("show me kurta under 1500", S)
    assert chat_log_repo.recent_logs(1)[0]["steps"] is None
