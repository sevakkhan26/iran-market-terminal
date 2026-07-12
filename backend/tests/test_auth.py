"""Env-driven auth: two-secret model, hashing, stateless tokens, rate limit."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.auth import EnvAuth, hash_password, verify_password


def make_auth(monkeypatch, username="admin", password="admin",
              token_secret="unit-test-secret"):
    monkeypatch.setenv("AUTH_USERNAME", username)
    monkeypatch.setenv("AUTH_PASSWORD_HASH", hash_password(password))
    monkeypatch.setenv("AUTH_TOKEN_SECRET", token_secret)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)
    return EnvAuth()


def test_hash_roundtrip():
    h = hash_password("secret-1")
    assert h.startswith("pbkdf2$")
    assert verify_password("secret-1", h)
    assert not verify_password("nope", h)
    assert not verify_password("secret-1", "garbage")
    assert hash_password("x") != hash_password("x")   # unique salts


def test_login_and_token(monkeypatch):
    a = make_auth(monkeypatch, username="sobhan", password="strong-pw-1")
    assert a.default_creds is False
    assert a.login("sobhan", "wrong") is None
    res = a.login("SOBHAN", "strong-pw-1")            # case-insensitive username
    assert res and res["token"]
    session = a.validate(res["token"])
    assert session and session["username"] == "sobhan"
    assert a.validate("garbage") is None
    assert a.validate(res["token"][:-2] + "xx") is None   # tampered signature


def test_both_secrets_feed_token_key(monkeypatch):
    a = make_auth(monkeypatch, password="pw-abcdef", token_secret="secret-A")
    token = a.login("admin", "pw-abcdef")["token"]
    assert a.validate(token)
    # rotating the TOKEN secret kills tokens (password unchanged)
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "secret-B")
    a.reload()
    assert a.validate(token) is None
    fresh = a.login("admin", "pw-abcdef")["token"]     # login still works
    assert a.validate(fresh)
    # rotating the PASSWORD hash also kills tokens (token secret unchanged)
    monkeypatch.setenv("AUTH_PASSWORD_HASH", hash_password("new-pw-123"))
    a.reload()
    assert a.validate(fresh) is None
    assert a.login("admin", "pw-abcdef") is None
    assert a.login("admin", "new-pw-123")["token"]


def test_plaintext_dev_fallback(monkeypatch):
    monkeypatch.setenv("AUTH_USERNAME", "dev")
    monkeypatch.delenv("AUTH_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("AUTH_PASSWORD", "dev-pass-1")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "s")
    a = EnvAuth()
    assert a.default_creds is False
    assert a.login("dev", "dev-pass-1")["token"]


def test_default_creds_flag(monkeypatch):
    for var in ("AUTH_USERNAME", "AUTH_PASSWORD_HASH", "AUTH_PASSWORD",
                "AUTH_TOKEN_SECRET"):
        monkeypatch.delenv(var, raising=False)
    a = EnvAuth()
    assert a.default_creds is True
    assert a.login("admin", "admin")["user"]["default_creds"] is True


def test_rate_limit(monkeypatch):
    a = make_auth(monkeypatch)
    for _ in range(5):
        assert a.login("admin", "bad") is None
    locked = a.login("admin", "admin")
    assert locked and locked.get("error") == "locked"
