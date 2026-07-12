"""Environment-driven single-user authentication.

Secrets — set these as environment variables (Vercel dashboard, or backend/.env
for local development; see .env.example):

  AUTH_USERNAME        login username                        (default: admin)
  AUTH_PASSWORD_HASH   PBKDF2 hash of the password — generate it with:
                         python3 main.py hash-password "your-password"
                       The plaintext password is never stored anywhere.
  AUTH_TOKEN_SECRET    random signing secret for session tokens — generate:
                         python3 main.py generate-secret
  AUTH_PASSWORD        (dev-only fallback) plaintext password; hashed in memory
                       at startup. Prefer AUTH_PASSWORD_HASH in production.

Security model:
- Password check: PBKDF2-HMAC-SHA256, 200k iterations, per-hash salt,
  constant-time comparison.
- Session tokens: stateless HMAC-SHA256 signatures. The signing key combines
  BOTH secrets — sha256(AUTH_TOKEN_SECRET | AUTH_PASSWORD_HASH) — so rotating
  either one instantly invalidates every issued token. No disk writes on
  login (safe on read-only/serverless hosting).
- Login attempts rate-limited (5 failures → 60s lockout, per process).
- Nothing secret ever reaches the frontend: the client only holds the opaque
  signed token.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets as _secrets
import time
from typing import Any, Dict, Optional

log = logging.getLogger("terminal.auth")

TOKEN_TTL = 7 * 86400
PBKDF2_ITERATIONS = 200_000
MAX_FAILS = 5
LOCKOUT_SEC = 60


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                 PBKDF2_ITERATIONS).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                        bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def generate_secret() -> str:
    return _secrets.token_hex(32)


class EnvAuth:
    def __init__(self) -> None:
        self._fails: Dict[str, list] = {}
        self.username = "admin"
        self.password_hash = ""
        self.default_creds = False
        self.env_managed = True
        self._token_key = b""
        self.reload()

    # ------------------------------------------------------------ env load
    def reload(self) -> None:
        self.username = os.environ.get("AUTH_USERNAME", "admin").strip() or "admin"

        pw_hash = os.environ.get("AUTH_PASSWORD_HASH", "").strip()
        pw_plain = os.environ.get("AUTH_PASSWORD", "")
        self.default_creds = False
        if pw_hash:
            self.password_hash = pw_hash
        elif pw_plain:
            self.password_hash = hash_password(pw_plain)
            log.warning("AUTH_PASSWORD (plaintext env) in use — prefer "
                        "AUTH_PASSWORD_HASH in production "
                        "(python3 main.py hash-password \"...\")")
        else:
            self.password_hash = hash_password("admin")
            self.default_creds = True
            log.warning("No AUTH_PASSWORD_HASH / AUTH_PASSWORD set — using "
                        "default admin/admin. Configure the environment "
                        "variables before exposing this to a network.")

        token_secret = os.environ.get("AUTH_TOKEN_SECRET", "").strip()
        if not token_secret:
            token_secret = "derived-from-password-hash"
            log.warning("AUTH_TOKEN_SECRET not set — deriving the signing key "
                        "from the password hash. Set a dedicated secret "
                        "(python3 main.py generate-secret) for best practice.")
        # BOTH secrets feed the signing key: rotating either kills all tokens.
        self._token_key = hashlib.sha256(
            f"{token_secret}|{self.password_hash}".encode()).digest()

    # --------------------------------------------------------------- tokens
    def _sign(self, payload: str) -> str:
        return hmac.new(self._token_key, payload.encode(), hashlib.sha256).hexdigest()

    def issue_token(self) -> str:
        payload = f"{self.username}|{int(time.time() + TOKEN_TTL)}"
        b64 = base64.urlsafe_b64encode(payload.encode()).decode()
        return f"{b64}.{self._sign(payload)}"

    def validate(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        try:
            b64, sig = token.split(".")
            payload = base64.urlsafe_b64decode(b64.encode()).decode()
        except (ValueError, UnicodeDecodeError):
            return None
        if not hmac.compare_digest(sig, self._sign(payload)):
            return None
        username, _, expires = payload.rpartition("|")
        try:
            if float(expires) < time.time():
                return None
        except ValueError:
            return None
        if not hmac.compare_digest(username, self.username):
            return None
        return {"username": username, "role": "admin"}

    # ---------------------------------------------------------------- login
    def _locked_out(self, username: str) -> bool:
        now = time.time()
        fails = [t for t in self._fails.get(username, []) if now - t < LOCKOUT_SEC]
        self._fails[username] = fails
        return len(fails) >= MAX_FAILS

    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = username.strip()
        if self._locked_out(username):
            return {"error": "locked", "retry_in": LOCKOUT_SEC}
        if (username.lower() != self.username.lower()
                or not verify_password(password, self.password_hash)):
            self._fails.setdefault(username, []).append(time.time())
            return None
        self._fails.pop(username, None)
        return {
            "token": self.issue_token(),
            "user": {"username": self.username, "role": "admin",
                     "default_creds": self.default_creds},
        }


auth_service = EnvAuth()
