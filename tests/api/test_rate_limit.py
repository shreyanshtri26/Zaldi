from tests.helpers import ADMIN_HEADERS
from zaldi import config

SID = {"X-Session-Id": "11111111-1111-4111-8111-111111111111"}


def test_chat_is_limited_per_visitor(client, monkeypatch):
    from zaldi.services import chat_service

    monkeypatch.setattr(chat_service, "handle_query", lambda *a, **k: {"response": "ok"})  # no LLM in a limiter test
    monkeypatch.setattr(config, "RATE_LIMIT_CHAT", 2)
    codes = [client.post("/api/chat", json={"message": "hi"}, headers=SID | {"CF-Connecting-IP": "1.1.1.1"}).status_code
             for _ in range(3)]
    assert codes[2] == 429 and 429 not in codes[:2]
    other = client.post("/api/chat", json={"message": "hi"}, headers=SID | {"CF-Connecting-IP": "2.2.2.2"})
    assert other.status_code == 200  # a different visitor is unaffected


def test_admin_login_attempts_are_limited(client, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_LOGIN", 2)
    h = {"CF-Connecting-IP": "3.3.3.3", "X-Admin-Token": "wrong"}
    assert [client.post("/api/admin/login", headers=h).status_code for _ in range(3)] == [401, 401, 429]
    assert client.post("/api/admin/login", headers=ADMIN_HEADERS | {"CF-Connecting-IP": "4.4.4.4"}).status_code == 200
