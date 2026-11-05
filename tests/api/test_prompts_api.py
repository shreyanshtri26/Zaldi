import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi.ai.prompts import DEFAULT_PROMPTS, get_prompt


def test_prompts_start_as_defaults(client):
    prompts = client.get("/api/admin/prompts", headers=ADMIN_HEADERS).get_json()
    assert {p["name"] for p in prompts} == set(DEFAULT_PROMPTS)
    assert all(not p["is_custom"] and p["content"] == p["default"] for p in prompts)


def test_override_is_used_by_the_assistant_and_can_be_reset(client):
    text = "You are a polite Zaldi assistant. Always greet with Namaste."
    updated = client.put("/api/admin/prompts/agent_system", json={"content": text}, headers=ADMIN_HEADERS)
    assert updated.get_json()["is_custom"] is True
    assert get_prompt("agent_system") == text  # what the agent reads on the next request

    reset = client.delete("/api/admin/prompts/agent_system", headers=ADMIN_HEADERS)
    assert reset.get_json()["is_custom"] is False
    assert get_prompt("agent_system") == DEFAULT_PROMPTS["agent_system"]


def test_saving_the_default_text_clears_the_override(client):
    client.put("/api/admin/prompts/agent_system", json={"content": "custom"}, headers=ADMIN_HEADERS)
    again = client.put("/api/admin/prompts/agent_system", json={"content": DEFAULT_PROMPTS["agent_system"]},
                       headers=ADMIN_HEADERS)
    assert again.get_json()["is_custom"] is False


@pytest.mark.parametrize("name, content", [
    ("agent_system", "   "),                       # empty
    ("agent_system", "x" * 5000),                  # too long
    ("chitchat", "Reply nicely."),                 # missing {input}
    ("chitchat", "Hi {input} and {other}"),        # stray variable
    ("nope", "anything"),                          # unknown prompt
])
def test_invalid_prompts_are_rejected(client, name, content):
    response = client.put(f"/api/admin/prompts/{name}", json={"content": content}, headers=ADMIN_HEADERS)
    assert response.status_code == 400


def test_braces_in_the_agent_prompt_do_not_break_the_template():
    from zaldi.ai.prompts import escape_braces
    assert escape_braces("Use {curly} braces") == "Use {{curly}} braces"


def test_prompt_endpoints_need_the_admin_token(client):
    assert client.get("/api/admin/prompts").status_code == 401
    assert client.put("/api/admin/prompts/agent_system", json={"content": "x"}).status_code == 401
