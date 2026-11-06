"""Server-wide settings the server admin controls from the portal: the admin password, the database address, copying data, restarting.
The network, the copy process and the restart are all faked, so no test can reach a real database or stop the test run."""
import json
import subprocess

import psycopg
import pytest

from tests.helpers import ADMIN_HEADERS, ADMIN_TOKEN
from zaldi import bootstrap, config, stores
from zaldi.api import server_admin
from zaldi.connectors import netguard
from zaldi.db import connect, init_db
from zaldi.errors import ValidationError
from zaldi.services import accounts, server_settings

NEW_PASSWORD = "a brand new admin password"
URL = "postgresql://neondb_owner:S3cretPassw0rd@ep-cool-sky-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def env(temp_db, monkeypatch):
    init_db()
    server_settings._verified.clear()
    monkeypatch.setattr(config, "DATA_DIR", temp_db / "data")
    monkeypatch.setenv("ALLOW_PRIVATE_STORE_URLS", "1")  # the fake database host does not resolve
    monkeypatch.delenv("DATABASE_URL", raising=False)


def as_password(password):
    return {"X-Admin-Token": password}


# --- the admin password -------------------------------------------------------------------------------------------------------------------
def test_the_status_shows_where_the_password_comes_from_and_nothing_secret(client):
    out = client.get("/api/admin/server", headers=ADMIN_HEADERS).get_json()
    assert out["admin_password"] == {"source": "environment", "environment_token_set": True, "min_length": 12}
    assert out["database"]["backend"] == "sqlite" and out["database"]["source"] == "default"
    assert ADMIN_TOKEN not in json.dumps(out)


def test_the_server_admin_can_set_a_password_in_the_portal_and_the_environment_token_stays_as_recovery(client):
    done = client.put("/api/admin/server/password", json={"current": ADMIN_TOKEN, "new": NEW_PASSWORD}, headers=ADMIN_HEADERS)
    assert done.status_code == 200 and done.get_json()["admin_password"]["source"] == "portal"
    assert NEW_PASSWORD not in done.get_data(as_text=True)
    assert client.get("/api/admin/server", headers=as_password(NEW_PASSWORD)).status_code == 200  # the new password signs in
    assert client.get("/api/admin/server", headers=ADMIN_HEADERS).status_code == 200  # the environment token still works
    assert client.get("/api/admin/server", headers=as_password("not the password")).status_code == 401
    with connect() as conn:  # stored as a salted hash, never the password
        stored = conn.execute("SELECT value FROM settings WHERE key = ?", (server_settings.PASSWORD_SETTING,)).fetchone()["value"]
    assert NEW_PASSWORD not in stored and stored.startswith(("scrypt:", "pbkdf2:"))


@pytest.mark.parametrize("current, new, why", [
    ("wrong", NEW_PASSWORD, "wrong"), (ADMIN_TOKEN, "short", "at least"), (ADMIN_TOKEN, ADMIN_TOKEN, "different"), (ADMIN_TOKEN, "", "at least"),
])
def test_a_password_change_needs_the_current_one_and_a_good_new_one(client, current, new, why):
    response = client.put("/api/admin/server/password", json={"current": current, "new": new}, headers=ADMIN_HEADERS)
    assert response.status_code == 400 and why in response.get_json()["error"].lower()
    assert client.get("/api/admin/server", headers=ADMIN_HEADERS).get_json()["admin_password"]["source"] == "environment"


def test_the_portal_password_can_be_removed_but_only_if_the_environment_token_exists(client, monkeypatch):
    client.put("/api/admin/server/password", json={"current": ADMIN_TOKEN, "new": NEW_PASSWORD}, headers=ADMIN_HEADERS)
    assert client.delete("/api/admin/server/password", json={"current": "nope"}, headers=ADMIN_HEADERS).status_code == 400
    monkeypatch.setattr(config, "ADMIN_TOKEN", None)  # a server with no environment token: removing the password would lock everyone out
    assert client.delete("/api/admin/server/password", json={"current": NEW_PASSWORD}, headers=as_password(NEW_PASSWORD)).status_code == 400
    monkeypatch.setattr(config, "ADMIN_TOKEN", ADMIN_TOKEN)
    gone = client.delete("/api/admin/server/password", json={"current": NEW_PASSWORD}, headers=ADMIN_HEADERS).get_json()
    assert gone["admin_password"]["source"] == "environment"
    assert client.get("/api/admin/server", headers=as_password(NEW_PASSWORD)).status_code == 401


def test_a_server_with_only_a_portal_password_works_and_still_refuses_wrong_tokens(client, monkeypatch):
    client.put("/api/admin/server/password", json={"current": ADMIN_TOKEN, "new": NEW_PASSWORD}, headers=ADMIN_HEADERS)
    monkeypatch.setattr(config, "ADMIN_TOKEN", None)
    assert client.get("/api/admin/stats", headers=as_password(NEW_PASSWORD)).status_code == 200
    assert client.get("/api/admin/stats", headers=as_password("guess")).status_code == 401  # not the 503 "not configured": a password exists
    assert client.get("/api/admin/stats").status_code == 401


def test_store_owners_cannot_reach_the_server_settings(client):
    client.post("/api/admin/stores", json={"slug": "cafe", "name": "Cafe"}, headers=ADMIN_HEADERS)
    accounts.create_account("o@cafe.test", PASSWORD, "cafe")
    owner = {"X-Admin-Token": accounts.issue_token(accounts.authenticate("o@cafe.test", PASSWORD)), "X-Store": "cafe"}
    for method, path in (("get", "/api/admin/server"), ("put", "/api/admin/server/password"), ("post", "/api/admin/server/database/test"),
                         ("put", "/api/admin/server/database"), ("post", "/api/admin/server/database/copy"), ("post", "/api/admin/server/restart")):
        assert getattr(client, method)(path, json={}, headers=owner).status_code == 403, path


# --- store owners change their own password -----------------------------------------------------------------------------------------------
def test_an_owner_changes_their_own_password(client):
    client.post("/api/admin/stores", json={"slug": "cafe", "name": "Cafe"}, headers=ADMIN_HEADERS)
    accounts.create_account("o@cafe.test", PASSWORD, "cafe")
    owner = {"X-Admin-Token": accounts.issue_token(accounts.authenticate("o@cafe.test", PASSWORD)), "X-Store": "cafe"}
    change = lambda current, new: client.put("/api/admin/account/password", json={"current": current, "new": new}, headers=owner)  # noqa: E731
    assert change("wrong password!", NEW_PASSWORD).status_code == 400
    assert change(PASSWORD, "short").status_code == 400 and change(PASSWORD, PASSWORD).status_code == 400
    assert change(PASSWORD, NEW_PASSWORD).status_code == 200
    with pytest.raises(ValidationError):
        accounts.authenticate("o@cafe.test", PASSWORD)
    assert accounts.authenticate("o@cafe.test", NEW_PASSWORD)["store"] == "cafe"
    assert client.put("/api/admin/account/password", json={"current": ADMIN_TOKEN, "new": NEW_PASSWORD}, headers=ADMIN_HEADERS).status_code == 400  # the server admin has no account


# --- the database -------------------------------------------------------------------------------------------------------------------------
class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConn:
    """Answers the few queries ``test_database`` asks."""

    def __init__(self, vector=True, products=False):
        self.vector, self.products = vector, products

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        if "server_version" in sql:
            return FakeCursor(("18.0",))
        if "pg_available_extensions" in sql:
            return FakeCursor((1,) if self.vector else None)
        if "to_regclass" in sql:
            return FakeCursor(("products",) if self.products else (None,))
        return FakeCursor((1,) if self.products else None)  # SELECT 1 FROM products LIMIT 1


def connect_as(monkeypatch, **kw):
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: FakeConn(**kw))


@pytest.mark.parametrize("bad", ["", "   ", "mysql://u:p@host/db", "http://host/db", "postgresql://", "not a url", "postgresql://u:p@host/db" + "x" * 700])
def test_only_a_postgres_address_is_accepted(client, bad):
    assert client.post("/api/admin/server/database/test", json={"url": bad}, headers=ADMIN_HEADERS).status_code == 400


def test_a_good_address_is_reported_without_ever_repeating_it(client, monkeypatch):
    connect_as(monkeypatch)
    response = client.post("/api/admin/server/database/test", json={"url": URL}, headers=ADMIN_HEADERS)
    out = response.get_json()
    assert out["ok"] and out["state"] == "ok" and out["has_data"] is False and out["host"].endswith("neon.tech") and out["database"] == "neondb"
    assert "S3cretPassw0rd" not in response.get_data(as_text=True) and "neondb_owner" not in response.get_data(as_text=True)


def test_a_database_that_already_has_zaldi_data_is_flagged(client, monkeypatch):
    connect_as(monkeypatch, products=True)
    assert client.post("/api/admin/server/database/test", json={"url": URL}, headers=ADMIN_HEADERS).get_json()["has_data"] is True


@pytest.mark.parametrize("failure, state", [
    ("FATAL: password authentication failed for user", "auth"), ("could not translate host name to address", "unreachable"),
    ("connection timeout expired", "unreachable"), ("SSL SYSCALL error: EOF", "error"),
])
def test_connection_failures_are_explained_in_plain_words(client, monkeypatch, failure, state):
    def boom(*a, **k):
        raise psycopg.OperationalError(f"{failure} for {URL}")

    monkeypatch.setattr(psycopg, "connect", boom)
    response = client.post("/api/admin/server/database/test", json={"url": URL}, headers=ADMIN_HEADERS)
    out = response.get_json()
    assert out["ok"] is False and out["state"] == state and out["message"]
    assert "S3cretPassw0rd" not in response.get_data(as_text=True)


def test_a_database_without_pgvector_is_refused_with_the_reason(client, monkeypatch):
    connect_as(monkeypatch, vector=False)
    out = client.post("/api/admin/server/database/test", json={"url": URL}, headers=ADMIN_HEADERS).get_json()
    assert out["ok"] is False and out["state"] == "no_vector" and "pgvector" in out["message"]


def test_addresses_that_point_at_the_servers_own_network_are_blocked(client, monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_STORE_URLS")
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: pytest.fail("must not even try to connect"))
    for host in ("127.0.0.1", "localhost", "10.0.0.5", "169.254.169.254"):
        out = client.post("/api/admin/server/database/test", json={"url": f"postgresql://u:p@{host}/db"}, headers=ADMIN_HEADERS).get_json()
        assert out["ok"] is False and out["state"] == "blocked", host
    assert netguard.check_public_url  # the same guard the store connectors use


def test_saving_an_address_stores_it_encrypted_and_asks_for_a_restart(client, monkeypatch, temp_db):
    connect_as(monkeypatch)
    saved = client.put("/api/admin/server/database", json={"url": URL}, headers=ADMIN_HEADERS).get_json()["database"]
    assert saved["saved_in_portal"] and saved["restart_needed"] is True and saved["backend"] == "sqlite"  # still running on SQLite until the restart
    assert saved["saved"]["host"].endswith("neon.tech") and "S3cretPassw0rd" not in json.dumps(saved)
    raw = (temp_db / "data" / bootstrap.FILE).read_text(encoding="utf-8")
    assert "S3cretPassw0rd" not in raw and "neon.tech" not in raw  # encrypted on disk
    assert bootstrap.load(config.DATA_DIR, config.SECRET_KEY) == URL
    assert bootstrap.load(config.DATA_DIR, "a-different-secret") == ""  # useless without the server's secret
    gone = client.delete("/api/admin/server/database", headers=ADMIN_HEADERS).get_json()["database"]
    assert gone["saved_in_portal"] is False and gone["restart_needed"] is False and not (temp_db / "data" / bootstrap.FILE).exists()


def test_an_address_that_does_not_connect_is_never_saved(client, monkeypatch, temp_db):
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: (_ for _ in ()).throw(psycopg.OperationalError("password authentication failed")))
    assert client.put("/api/admin/server/database", json={"url": URL}, headers=ADMIN_HEADERS).status_code == 400
    assert not (temp_db / "data" / bootstrap.FILE).exists()


def test_an_environment_address_wins_over_the_saved_one_and_the_status_says_so(client, monkeypatch):
    connect_as(monkeypatch)
    client.put("/api/admin/server/database", json={"url": URL}, headers=ADMIN_HEADERS)
    monkeypatch.setenv("DATABASE_URL", "postgresql://other@host/db")
    monkeypatch.setattr(config, "DATABASE_URL", "")  # (the test suite itself runs on SQLite)
    db = client.get("/api/admin/server", headers=ADMIN_HEADERS).get_json()["database"]
    assert db["source"] == "environment" and db["environment_overrides"] is True and db["restart_needed"] is False


# --- copying the data ---------------------------------------------------------------------------------------------------------------------
class Copy:
    """A fake child process for ``python -m zaldi migrate``."""

    def __init__(self, code=0, out="default: products 32, policies 6\nDone.", err=""):
        self.code, self.out, self.err, self.calls = code, out, err, []

    def __call__(self, command, **kw):
        self.calls.append((command, kw))
        return subprocess.CompletedProcess(command, self.code, self.out.replace("{url}", kw["env"]["DATABASE_URL"]), self.err)


def test_copying_runs_in_a_separate_process_with_the_target_address_and_reports_what_moved(client, monkeypatch):
    connect_as(monkeypatch)
    fake = Copy(out="default: products 32, policies 6\nsomething about {url}\nDone.")
    monkeypatch.setattr(subprocess, "run", fake)
    response = client.post("/api/admin/server/database/copy", json={"url": URL}, headers=ADMIN_HEADERS)
    assert response.status_code == 200 and "default: products 32, policies 6" in response.get_json()["report"]
    command, kw = fake.calls[0]
    assert command[-2:] == ["zaldi", "migrate"] and kw["env"]["DATABASE_URL"] == URL and "--replace" not in command
    assert "S3cretPassw0rd" not in response.get_data(as_text=True)  # the address is scrubbed from what the child printed


def test_copying_into_a_database_that_has_data_needs_an_explicit_replace_with_a_typed_confirmation(client, monkeypatch):
    connect_as(monkeypatch, products=True)
    fake = Copy()
    monkeypatch.setattr(subprocess, "run", fake)
    refused = client.post("/api/admin/server/database/copy", json={"url": URL}, headers=ADMIN_HEADERS)
    assert refused.status_code == 400 and "already has" in refused.get_json()["error"] and not fake.calls
    assert client.post("/api/admin/server/database/copy", json={"url": URL, "replace": True}, headers=ADMIN_HEADERS).status_code == 400  # no typed confirmation
    assert client.post("/api/admin/server/database/copy", json={"url": URL, "replace": True, "confirm": "yes"}, headers=ADMIN_HEADERS).status_code == 400
    assert not fake.calls
    ok = client.post("/api/admin/server/database/copy", json={"url": URL, "replace": True, "confirm": "REPLACE"}, headers=ADMIN_HEADERS)
    assert ok.status_code == 200 and "--replace" in fake.calls[0][0]


def test_a_failed_or_stuck_copy_gives_a_clear_message_and_never_the_address(client, monkeypatch):
    connect_as(monkeypatch)
    monkeypatch.setattr(subprocess, "run", Copy(code=1, out="", err=f"Traceback (most recent call last):\nValueError: boom {URL}"))
    failed = client.post("/api/admin/server/database/copy", json={"url": URL}, headers=ADMIN_HEADERS)
    assert failed.status_code == 400 and "Nothing on this server was changed" in failed.get_json()["error"] and "S3cretPassw0rd" not in failed.get_data(as_text=True)

    def stuck(*a, **k):
        raise subprocess.TimeoutExpired("migrate", 900)

    monkeypatch.setattr(subprocess, "run", stuck)
    assert "too long" in client.post("/api/admin/server/database/copy", json={"url": URL}, headers=ADMIN_HEADERS).get_json()["error"]


# --- restart ------------------------------------------------------------------------------------------------------------------------------
class FakeTimer:
    started = []

    def __init__(self, delay, fn):
        self.delay, self.fn = delay, fn

    def start(self):
        FakeTimer.started.append(self)


def test_restart_needs_a_typed_confirmation_and_then_runs_after_the_response_is_sent(client, monkeypatch):
    FakeTimer.started.clear()
    monkeypatch.setattr(server_admin.threading, "Timer", FakeTimer)
    assert client.post("/api/admin/server/restart", json={}, headers=ADMIN_HEADERS).status_code == 400 and not FakeTimer.started
    done = client.post("/api/admin/server/restart", json={"confirm": "RESTART"}, headers=ADMIN_HEADERS)
    assert done.status_code == 202 and len(FakeTimer.started) == 1 and FakeTimer.started[0].delay >= 1


def test_under_gunicorn_the_master_is_asked_to_reload_every_worker_and_elsewhere_the_process_exits(client, monkeypatch):
    FakeTimer.started.clear()
    monkeypatch.setattr(server_admin.threading, "Timer", FakeTimer)
    sent, exited = [], []
    monkeypatch.setattr(server_admin.signal, "SIGHUP", 1, raising=False)  # Windows has no SIGHUP; the branch under test does not need a real one
    monkeypatch.setattr(server_admin.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr(server_admin.os, "_exit", lambda code: exited.append(code))
    client.post("/api/admin/server/restart", json={"confirm": "RESTART"}, headers=ADMIN_HEADERS, environ_overrides={"SERVER_SOFTWARE": "gunicorn/23.0"})
    FakeTimer.started[-1].fn()
    assert len(sent) == 1 and sent[0][1] == 1 and not exited
    sent.clear()
    client.post("/api/admin/server/restart", json={"confirm": "RESTART"}, headers=ADMIN_HEADERS, environ_overrides={"SERVER_SOFTWARE": "Werkzeug/3"})
    FakeTimer.started[-1].fn()
    assert exited == [3] and not sent
