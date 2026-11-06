"""Store owner accounts: sign-in, scope to one store, read-only viewers, server-admin-only actions and opt-in sign-up."""
import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi import config, stores
from zaldi.db import init_db
from zaldi.errors import ValidationError
from zaldi.services import accounts

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()


def owner_token(client, slug="cafe", email="owner@cafe.test", role="owner"):
    if not stores.exists(slug):
        client.post("/api/admin/stores", json={"slug": slug, "name": slug.title()}, headers=ADMIN_HEADERS)
    client.post(f"/api/admin/stores/{slug}/accounts", json={"email": email, "password": PASSWORD, "role": role}, headers=ADMIN_HEADERS)
    login = client.post("/api/admin/account-login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return login.get_json()["token"]


def test_an_owner_signs_in_and_manages_only_their_own_store(client):
    token = owner_token(client)
    own = {"X-Admin-Token": token, "X-Store": "cafe"}
    assert client.post("/api/admin/login", headers=own).status_code == 200
    assert client.get("/api/admin/stats", headers=own).status_code == 200
    # the same token on another store, or on the default store, is refused
    assert client.get("/api/admin/stats", headers={"X-Admin-Token": token}).status_code == 403
    stores.create_store("other", "Other")
    assert client.get("/api/admin/stats", headers={"X-Admin-Token": token, "X-Store": "other"}).status_code == 403


def test_wrong_credentials_get_one_vague_answer_and_passwords_are_not_stored_in_clear():
    stores.create_store("cafe", "Cafe")
    accounts.create_account("a@cafe.test", PASSWORD, "cafe")
    for email, password in (("a@cafe.test", "wrong password!"), ("nobody@cafe.test", PASSWORD)):
        with pytest.raises(ValidationError, match="wrong email or password"):
            accounts.authenticate(email, password)
    from zaldi.db import connect

    with connect() as conn:
        assert PASSWORD not in conn.execute("SELECT password_hash FROM admin_users").fetchone()[0]


def test_a_viewer_can_read_but_not_change(client):
    token = owner_token(client, email="viewer@cafe.test", role="viewer")
    headers = {"X-Admin-Token": token, "X-Store": "cafe"}
    assert client.get("/api/admin/stats", headers=headers).status_code == 200
    assert client.put("/api/admin/settings", json={"brand_name": "x"}, headers=headers).status_code == 403


def test_owners_cannot_create_stores_or_accounts(client):
    token = owner_token(client)
    headers = {"X-Admin-Token": token, "X-Store": "cafe"}
    assert client.post("/api/admin/stores", json={"slug": "mine", "name": "Mine"}, headers=headers).status_code == 403
    assert client.get("/api/admin/stores", headers=headers).status_code == 403
    assert client.post("/api/admin/stores/cafe/accounts", json={"email": "x@y.test", "password": PASSWORD}, headers=headers).status_code == 403


def test_tokens_are_tamper_proof_and_die_with_the_account(client):
    token = owner_token(client)
    own = {"X-Store": "cafe"}
    assert client.get("/api/admin/stats", headers={**own, "X-Admin-Token": token + "x"}).status_code == 401
    from zaldi.db import connect

    with connect() as conn:
        conn.execute("DELETE FROM admin_users")
    assert client.get("/api/admin/stats", headers={**own, "X-Admin-Token": token}).status_code == 401


def test_account_rules_are_enforced():
    stores.create_store("cafe", "Cafe")
    for bad in (("not-an-email", PASSWORD), ("a@b.test", "short")):
        with pytest.raises(ValidationError):
            accounts.create_account(*bad, "cafe")
    accounts.create_account("dup@cafe.test", PASSWORD, "cafe")
    with pytest.raises(ValidationError, match="already exists"):
        accounts.create_account("DUP@cafe.test", PASSWORD, "cafe")
    with pytest.raises(ValidationError, match="unknown store"):
        accounts.create_account("x@cafe.test", PASSWORD, "missing")


def test_sign_up_is_closed_by_default_and_when_open_makes_a_store_and_its_owner(client, monkeypatch):
    body = {"email": "new@shop.test", "password": PASSWORD, "store": "newshop", "name": "New Shop"}
    assert client.post("/api/signup", json=body).status_code == 400 and not stores.exists("newshop")
    monkeypatch.setattr(config, "ALLOW_SIGNUP", True)
    done = client.post("/api/signup", json=body)
    assert done.status_code == 201 and stores.exists("newshop")
    token = done.get_json()["token"]
    assert client.get("/api/admin/stats", headers={"X-Admin-Token": token, "X-Store": "newshop"}).status_code == 200
    again = client.post("/api/signup", json={**body, "store": "second", "email": "new@shop.test"})
    assert again.status_code == 400 and not stores.exists("second")  # the email is taken: no orphan store is left behind
