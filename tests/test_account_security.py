"""Owner account security: two-step sign-in (TOTP), password reset, sessions that end when credentials change, lockout, and the accounts
screen's endpoints. The clock, email and network are faked."""
import smtplib
import sqlite3

import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi import config, stores
from zaldi.db import connect, init_db
from zaldi.errors import ValidationError
from zaldi.services import accounts, mailer, totp

PASSWORD = "correct horse battery"
NEW = "an entirely different phrase"
EMAIL = "owner@cafe.test"


class Clock:
    t = 1_700_000_010.0

    @classmethod
    def step(cls):
        return int(cls.t // 30)

    @classmethod
    def tick(cls, steps=1):
        cls.t += 30 * steps


@pytest.fixture(autouse=True)
def env(temp_db, monkeypatch):
    init_db()
    Clock.t = 1_700_000_010.0
    monkeypatch.setattr(totp, "_now", lambda: Clock.t)
    accounts._failures.clear()
    accounts._last_reset_mail.clear()
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "SMTP_FROM", "")


def shop(client, email=EMAIL, role="owner"):
    if not stores.exists("cafe"):
        client.post("/api/admin/stores", json={"slug": "cafe", "name": "Cafe"}, headers=ADMIN_HEADERS)
    return client.post("/api/admin/stores/cafe/accounts", json={"email": email, "password": PASSWORD, "role": role}, headers=ADMIN_HEADERS)


def sign_in(client, password=PASSWORD, email=EMAIL):
    return client.post("/api/admin/account-login", json={"email": email, "password": password})


def head(token):
    return {"X-Admin-Token": token, "X-Store": "cafe"}


def works(client, token):
    return client.get("/api/admin/stats", headers=head(token)).status_code == 200


def turn_on_two_step(client, token):
    """Set up two-step through the API and return (secret, recovery codes)."""
    setup = client.post("/api/admin/account/two-step/setup", json={"password": PASSWORD}, headers=head(token)).get_json()
    enabled = client.post("/api/admin/account/two-step/enable", json={"code": totp.code_at(setup["secret"], Clock.step())}, headers=head(token))
    assert enabled.status_code == 200
    return setup["secret"], enabled.get_json()["recovery_codes"]


# --- the one-time-password maths -------------------------------------------------------------------------------------------------------
def test_totp_matches_the_rfc_6238_test_vector_and_rejects_replays_and_wrong_codes():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # the RFC's ASCII secret 12345678901234567890
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.verify(secret, "287082", now=59) == 1
    assert totp.verify(secret, "287082", after_step=1, now=59) is None  # the same step cannot be used twice
    assert totp.verify(secret, "287082", now=59 + 30) == 1 and totp.verify(secret, "287082", now=59 + 60) is None  # one step of drift, not more
    for bad in ("", "12345", "1234567", "abcdef", "287083", None):
        assert totp.verify(secret, bad, now=59) is None
    assert totp.verify(secret, "28 70 82", now=59) == 1  # spaces from copying are fine
    uri = totp.uri("a@b.test", secret)
    assert uri.startswith("otpauth://totp/Zaldi%3Aa%40b.test?secret=") and "issuer=Zaldi" in uri


# --- two-step sign-in -------------------------------------------------------------------------------------------------------------------
def test_two_step_setup_needs_the_password_and_a_working_code_before_it_turns_on(client):
    shop(client)
    token = sign_in(client).get_json()["token"]
    assert client.post("/api/admin/account/two-step/setup", json={"password": "wrong password!"}, headers=head(token)).status_code == 400
    setup = client.post("/api/admin/account/two-step/setup", json={"password": PASSWORD}, headers=head(token)).get_json()
    assert client.get("/api/admin/account/two-step", headers=head(token)).get_json()["enabled"] is False  # not on until a code proves the app has it
    assert client.post("/api/admin/account/two-step/enable", json={"code": "000000"}, headers=head(token)).status_code == 400
    assert sign_in(client).get_json().get("token")  # still a normal sign-in
    ok = client.post("/api/admin/account/two-step/enable", json={"code": totp.code_at(setup["secret"], Clock.step())}, headers=head(token)).get_json()
    assert len(ok["recovery_codes"]) == 8 and len(set(ok["recovery_codes"])) == 8
    assert client.get("/api/admin/account/two-step", headers=head(token)).get_json() == {"enabled": True, "recovery_codes_left": 8}
    assert client.post("/api/admin/account/two-step/setup", json={"password": PASSWORD}, headers=head(token)).status_code == 400  # already on


def test_the_secret_and_recovery_codes_are_not_stored_in_clear(client):
    shop(client)
    secret, codes = turn_on_two_step(client, sign_in(client).get_json()["token"])
    with connect() as conn:
        row = dict(conn.execute("SELECT totp_secret, recovery_codes FROM admin_users WHERE email = ?", (EMAIL,)).fetchone())
    assert secret not in row["totp_secret"] and not any(c in row["recovery_codes"] for c in codes)


def test_with_two_step_on_the_password_alone_gets_a_challenge_and_not_a_token(client):
    shop(client)
    secret, _ = turn_on_two_step(client, sign_in(client).get_json()["token"])
    first = sign_in(client).get_json()
    assert first["needs_two_step"] is True and "token" not in first and first["challenge"]
    Clock.tick()
    good = client.post("/api/admin/account-login/two-step", json={"challenge": first["challenge"], "code": totp.code_at(secret, Clock.step())})
    assert good.status_code == 200 and works(client, good.get_json()["token"]) and good.get_json()["store"] == "cafe"
    wrong = client.post("/api/admin/account-login/two-step", json={"challenge": first["challenge"], "code": "000000"})
    assert wrong.status_code == 400 and "token" not in wrong.get_data(as_text=True)


def test_a_code_works_once_and_the_challenge_cannot_be_forged_or_outlive_its_window(client, monkeypatch):
    shop(client)
    secret, _ = turn_on_two_step(client, sign_in(client).get_json()["token"])
    challenge = sign_in(client).get_json()["challenge"]
    Clock.tick()
    code = totp.code_at(secret, Clock.step())
    send = lambda c, k: client.post("/api/admin/account-login/two-step", json={"challenge": c, "code": k})  # noqa: E731
    assert send(challenge, code).status_code == 200
    assert send(challenge, code).status_code == 400  # replay of the same code
    assert send("not-a-challenge", code).status_code == 400
    monkeypatch.setattr(accounts, "CHALLENGE_TTL", -1)
    Clock.tick()
    assert send(challenge, totp.code_at(secret, Clock.step())).status_code == 400  # too slow


def test_a_recovery_code_signs_in_once_and_then_is_gone(client):
    shop(client)
    _, codes = turn_on_two_step(client, sign_in(client).get_json()["token"])
    send = lambda c, k: client.post("/api/admin/account-login/two-step", json={"challenge": c, "code": k})  # noqa: E731
    assert send(sign_in(client).get_json()["challenge"], codes[0]).status_code == 200
    assert send(sign_in(client).get_json()["challenge"], codes[0]).status_code == 400
    assert send(sign_in(client).get_json()["challenge"], codes[1]).status_code == 200
    token = sign_in(client).get_json()
    assert token["needs_two_step"] and accounts.two_step_status(EMAIL)["recovery_codes_left"] == 6


def test_turning_two_step_off_needs_the_password_and_a_code_and_ends_other_sessions(client):
    shop(client)
    old = sign_in(client).get_json()["token"]
    secret, _ = turn_on_two_step(client, old)
    Clock.tick()
    me = head(old)
    assert client.post("/api/admin/account/two-step/disable", json={"password": "wrong password!", "code": totp.code_at(secret, Clock.step())}, headers=me).status_code == 400
    assert client.post("/api/admin/account/two-step/disable", json={"password": PASSWORD, "code": "000000"}, headers=me).status_code == 400
    off = client.post("/api/admin/account/two-step/disable", json={"password": PASSWORD, "code": totp.code_at(secret, Clock.step())}, headers=me)
    assert off.status_code == 200 and works(client, off.get_json()["token"]) and not works(client, old)
    assert sign_in(client).get_json().get("token") and client.get("/api/admin/account/two-step", headers=head(off.get_json()["token"])).get_json()["enabled"] is False


def test_the_server_admin_can_turn_two_step_off_for_a_lost_phone(client):
    shop(client)
    old = sign_in(client).get_json()["token"]
    turn_on_two_step(client, old)
    done = client.post(f"/api/admin/stores/cafe/accounts/{EMAIL}/two-step/disable", headers=ADMIN_HEADERS)
    assert done.status_code == 200 and not works(client, old) and sign_in(client).get_json().get("token")


def test_the_server_admin_has_no_account_so_the_account_endpoints_say_so(client):
    for path in ("/api/admin/account/two-step", ):
        assert client.get(path, headers=ADMIN_HEADERS).status_code == 400
    assert client.post("/api/admin/account/two-step/setup", json={"password": PASSWORD}, headers=ADMIN_HEADERS).status_code == 400


# --- passwords and sessions -------------------------------------------------------------------------------------------------------------
def test_changing_a_password_ends_the_other_sessions_and_hands_back_a_fresh_token(client):
    shop(client)
    first, second = sign_in(client).get_json()["token"], sign_in(client).get_json()["token"]
    assert works(client, first) and works(client, second)
    changed = client.put("/api/admin/account/password", json={"current": PASSWORD, "new": NEW}, headers=head(first))
    assert changed.status_code == 200
    fresh = changed.get_json()["token"]
    assert works(client, fresh) and not works(client, first) and not works(client, second)
    assert sign_in(client, PASSWORD).status_code == 400 and sign_in(client, NEW).get_json().get("token")


def test_five_wrong_passwords_lock_the_account_for_a_while_even_for_the_right_one(client):
    shop(client)
    for _ in range(accounts.LOCK_AFTER):
        assert sign_in(client, "wrong password!").status_code == 400
    locked = sign_in(client)
    assert locked.status_code == 400 and "Too many" in locked.get_json()["error"]
    accounts._failures.clear()  # the window passes
    assert sign_in(client).get_json().get("token")


def test_a_successful_sign_in_resets_the_count_of_wrong_attempts(client):
    shop(client)
    for _ in range(accounts.LOCK_AFTER - 1):
        sign_in(client, "wrong password!")
    assert sign_in(client).get_json().get("token")
    for _ in range(accounts.LOCK_AFTER - 1):
        sign_in(client, "wrong password!")
    assert sign_in(client).get_json().get("token")


# --- password reset ---------------------------------------------------------------------------------------------------------------------
def make_link(client, email=EMAIL):
    return client.post(f"/api/admin/stores/cafe/accounts/{email}/reset-link", headers=ADMIN_HEADERS).get_json()["link"]


def token_of(link):
    return link.split("reset=")[1]


def test_the_server_admin_creates_a_link_the_owner_uses_once_and_it_ends_old_sessions(client):
    shop(client)
    old = sign_in(client).get_json()["token"]
    link = make_link(client)
    assert link.startswith("http") and "/admin?reset=" in link
    done = client.post("/api/admin/password-reset", json={"token": token_of(link), "new": NEW})
    assert done.status_code == 200 and not works(client, old)
    assert sign_in(client, PASSWORD).status_code == 400 and sign_in(client, NEW).get_json().get("token")
    again = client.post("/api/admin/password-reset", json={"token": token_of(link), "new": "yet another phrase!"})
    assert again.status_code == 400 and "already been used" in again.get_json()["error"]


def test_a_newer_link_replaces_the_older_one_and_a_bad_or_expired_link_is_refused(client, monkeypatch):
    shop(client)
    old, new = make_link(client), make_link(client)
    assert client.post("/api/admin/password-reset", json={"token": token_of(old), "new": NEW}).status_code == 400
    assert client.post("/api/admin/password-reset", json={"token": "garbage", "new": NEW}).status_code == 400
    assert client.post("/api/admin/password-reset", json={"token": token_of(new), "new": "short"}).status_code == 400  # a rejected password does not burn the link
    monkeypatch.setattr(accounts, "RESET_TTL", -1)
    assert client.post("/api/admin/password-reset", json={"token": token_of(new), "new": NEW}).status_code == 400
    assert sign_in(client).get_json().get("token")  # nothing changed


def test_a_reset_clears_a_guessing_lock_but_keeps_two_step_on(client):
    shop(client)
    secret, _ = turn_on_two_step(client, sign_in(client).get_json()["token"])
    for _ in range(accounts.LOCK_AFTER):
        sign_in(client, "wrong password!")
    assert "Too many" in sign_in(client).get_json()["error"]
    client.post("/api/admin/password-reset", json={"token": token_of(make_link(client)), "new": NEW})
    assert sign_in(client, NEW).get_json()["needs_two_step"] is True  # the password was reset; the second step is still required


def test_only_the_server_admin_makes_links_and_only_for_accounts_in_that_store(client):
    shop(client)
    owner = head(sign_in(client).get_json()["token"])
    assert client.post(f"/api/admin/stores/cafe/accounts/{EMAIL}/reset-link", headers=owner).status_code == 403
    assert client.post("/api/admin/stores/cafe/accounts/nobody@cafe.test/reset-link", headers=ADMIN_HEADERS).status_code == 400
    client.post("/api/admin/stores", json={"slug": "other", "name": "Other"}, headers=ADMIN_HEADERS)
    assert client.post(f"/api/admin/stores/other/accounts/{EMAIL}/reset-link", headers=ADMIN_HEADERS).status_code == 400  # not in that store


class FakeSMTP:
    sent: list = []
    calls: list = []

    def __init__(self, host, port, timeout=None, context=None):
        FakeSMTP.calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        FakeSMTP.calls.append(("starttls",))

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user))

    def send_message(self, message):
        FakeSMTP.sent.append(message)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.calls = [], []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_HOST", "mail.example.test")
    monkeypatch.setattr(config, "SMTP_FROM", "Zaldi <no-reply@shop.test>")
    monkeypatch.setattr(config, "SMTP_USER", "mailer")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "mailpass")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    return FakeSMTP


def test_without_email_set_up_forgot_password_sends_nothing_and_says_so(client):
    shop(client)
    out = client.post("/api/admin/forgot-password", json={"email": EMAIL}).get_json()
    assert out == {"ok": True, "email_enabled": False} and not FakeSMTP.sent


def test_forgot_password_emails_a_working_link_and_never_reveals_whether_the_account_exists(client, smtp):
    shop(client)
    unknown = client.post("/api/admin/forgot-password", json={"email": "nobody@cafe.test"}).get_json()
    known = client.post("/api/admin/forgot-password", json={"email": EMAIL}).get_json()
    assert unknown == known == {"ok": True, "email_enabled": True}  # the same answer either way
    assert len(smtp.sent) == 1 and smtp.sent[0]["To"] == EMAIL
    assert ("starttls",) in smtp.calls and ("login", "mailer") in smtp.calls
    body = smtp.sent[0].get_content()
    link = next(line for line in body.splitlines() if "/admin?reset=" in line)
    assert client.post("/api/admin/password-reset", json={"token": token_of(link), "new": NEW}).status_code == 200
    assert sign_in(client, NEW).get_json().get("token")


def test_asking_again_within_a_minute_does_not_send_another_email_and_junk_is_ignored(client, smtp):
    shop(client)
    for email in (EMAIL, EMAIL, "not an email", "", None):
        client.post("/api/admin/forgot-password", json={"email": email})
    assert len(smtp.sent) == 1


def test_an_email_failure_is_swallowed_and_logged_without_the_message(client, smtp, monkeypatch, caplog):
    def broken(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", broken)
    shop(client)
    assert client.post("/api/admin/forgot-password", json={"email": EMAIL}).status_code == 200
    assert mailer.send("a@b.test", "s", "secret body text") is False and "secret body text" not in caplog.text


# --- the accounts screen -----------------------------------------------------------------------------------------------------------------
def test_the_account_list_shows_roles_and_two_step_and_a_role_change_ends_that_accounts_sessions(client):
    shop(client)
    shop(client, "viewer@cafe.test", "viewer")
    owner = sign_in(client).get_json()["token"]
    turn_on_two_step(client, owner)
    listed = {a["email"]: a for a in client.get("/api/admin/stores/cafe/accounts", headers=ADMIN_HEADERS).get_json()["accounts"]}
    assert listed[EMAIL]["two_step"] is True and listed["viewer@cafe.test"]["two_step"] is False and listed["viewer@cafe.test"]["role"] == "viewer"
    viewer = sign_in(client, email="viewer@cafe.test").get_json()["token"]
    assert works(client, viewer)
    changed = client.put("/api/admin/stores/cafe/accounts/viewer@cafe.test", json={"role": "owner"}, headers=ADMIN_HEADERS)
    assert changed.status_code == 200 and not works(client, viewer)  # the old token still says viewer
    assert sign_in(client, email="viewer@cafe.test").get_json()["role"] == "owner"
    assert client.put("/api/admin/stores/cafe/accounts/viewer@cafe.test", json={"role": "boss"}, headers=ADMIN_HEADERS).status_code == 400


def test_a_deleted_account_cannot_sign_in_and_its_token_dies_and_owners_cannot_delete(client):
    shop(client)
    shop(client, "other@cafe.test", "viewer")
    token = sign_in(client).get_json()["token"]
    assert client.delete("/api/admin/stores/cafe/accounts/other@cafe.test", headers=head(token)).status_code == 403
    assert client.delete("/api/admin/stores/cafe/accounts/other@cafe.test", headers=ADMIN_HEADERS).status_code == 204
    assert sign_in(client, email="other@cafe.test").status_code == 400
    assert client.delete("/api/admin/stores/cafe/accounts/other@cafe.test", headers=ADMIN_HEADERS).status_code == 400  # already gone
    assert client.delete(f"/api/admin/stores/cafe/accounts/{EMAIL}", headers=ADMIN_HEADERS).status_code == 204 and not works(client, token)


def test_deleting_a_store_needs_its_id_typed_and_takes_its_accounts_data_with_it(client):
    shop(client)
    assert client.delete("/api/admin/stores/cafe", headers=ADMIN_HEADERS).status_code == 400
    assert client.delete("/api/admin/stores/cafe", json={"confirm": "wrong"}, headers=ADMIN_HEADERS).status_code == 400
    assert stores.exists("cafe")
    assert client.delete("/api/admin/stores/cafe", json={"confirm": "cafe"}, headers=ADMIN_HEADERS).status_code == 204 and not stores.exists("cafe")


# --- older databases ---------------------------------------------------------------------------------------------------------------------
def test_an_older_accounts_table_gains_the_new_columns_and_keeps_its_rows(temp_db):
    if config.DATABASE_URL:
        pytest.skip("this checks the SQLite migration")
    config.DB_PATH.unlink()
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("CREATE TABLE admin_users (email TEXT PRIMARY KEY, password_hash TEXT NOT NULL, store TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'owner', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO admin_users (email, password_hash, store) VALUES ('old@x.test', 'h', 'default')")
    init_db()
    with connect() as conn:
        row = dict(conn.execute("SELECT * FROM admin_users WHERE email = 'old@x.test'").fetchone())
    assert row["auth_version"] == 0 and row["totp_enabled"] == 0 and row["reset_nonce"] is None and row["recovery_codes"] is None
    with pytest.raises(ValidationError):
        accounts.authenticate("old@x.test", "anything")  # the old row has no real password hash; it must not crash
