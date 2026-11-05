import pytest

from zaldi.api.chat import BUSY, FAILED
from zaldi.services import chat_service

SID = {"X-Session-Id": "22222222-2222-4222-8222-222222222222"}


@pytest.mark.parametrize("error, status, message", [
    ("429 RESOURCE_EXHAUSTED. You exceeded your current quota", 503, BUSY),
    ("connection reset by peer", 502, FAILED),
])
def test_model_errors_become_a_plain_try_again_message(client, monkeypatch, error, status, message):
    def boom(*_args, **_kwargs):
        raise RuntimeError(error)

    monkeypatch.setattr(chat_service, "handle_query", boom)
    response = client.post("/api/chat", json={"message": "hello"}, headers=SID)
    assert response.status_code == status
    body = response.get_json()
    assert body["error"] == message
    assert "RESOURCE_EXHAUSTED" not in body["error"] and "reset by peer" not in body["error"]  # provider detail never reaches the customer
