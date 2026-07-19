"""User authentication — DB-backed multi-user with roles.

Roles:
  admin     — full access, INCLUDING creating/deleting users.
  operator  — full access EXCEPT user management.

Bootstrap & lockout safety:
- On startup the env admin (AUTH_USERNAME / AUTH_PASSWORD_HASH, or the dev
  default admin/admin) is seeded as the first `admin` user IF the users table is
  empty. So an existing deployment keeps its exact login, now as a real account
  whose password can be changed in-app.
- The env credentials remain an *emergency fallback*: the env admin username +
  the env password always logs in (and re-creates the admin row if it was
  deleted), so a database mistake can never lock you out. Rotate by changing the
  env var. Non-env users live entirely in the database.

Secrets (env):
  AUTH_USERNAME        bootstrap/emergency admin username        (default admin)
  AUTH_PASSWORD_HASH   PBKDF2 hash — python3 main.py hash-password "..."
  AUTH_PASSWORD        dev-only plaintext fallback (hashed in memory at startup)

Security:
- Passwords: PBKDF2-HMAC-SHA256, 200k iterations, per-hash salt, constant-time
  compare.
- Sessions: opaque random tokens (secrets.token_urlsafe) stored in the
  auth_sessions table with a TTL; validated per request against a short in-memory
  cache backed by the DB. Deleting a user / changing a password revokes sessions.
- Login attempts are rate-limited (5 fails -> 60s lockout, per username).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets as _secrets
import time
from typing import Any, Dict, List, Optional

from . import db

log = logging.getLogger("terminal.auth")

TOKEN_TTL = 7 * 86400
PBKDF2_ITERATIONS = 200_000
MAX_FAILS = 5
LOCKOUT_SEC = 60
ROLES = ("admin", "operator")


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


class AuthService:
    def __init__(self) -> None:
        self._fails: Dict[str, list] = {}
        # token -> {username, role, user_id, must_change_password, expires_ts}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.username = "admin"
        self.env_password_hash = ""
        self.default_creds = False
        self.env_managed = True
        self._load_env()

    # ----------------------------------------------------------- env config
    def _load_env(self) -> None:
        self.username = os.environ.get("AUTH_USERNAME", "admin").strip() or "admin"
        pw_hash = os.environ.get("AUTH_PASSWORD_HASH", "").strip()
        pw_plain = os.environ.get("AUTH_PASSWORD", "")
        self.default_creds = False
        if pw_hash:
            self.env_password_hash = pw_hash
        elif pw_plain:
            self.env_password_hash = hash_password(pw_plain)
            log.warning("AUTH_PASSWORD (plaintext env) in use — prefer AUTH_PASSWORD_HASH")
        else:
            self.env_password_hash = hash_password("admin")
            self.default_creds = True
            log.warning("No AUTH_PASSWORD_HASH / AUTH_PASSWORD — bootstrap admin is "
                        "admin/admin. Set the env vars before exposing to a network.")

    def reload(self) -> None:
        self._load_env()

    def bootstrap(self) -> None:
        """Seed the env admin as the first DB user when the table is empty."""
        try:
            if db.count_users() == 0:
                db.create_user(self.username, self.env_password_hash, "admin")
                log.warning("Seeded bootstrap admin '%s' (role=admin)%s", self.username,
                            "  [default admin/admin — change it!]" if self.default_creds else "")
        except Exception as exc:
            log.error("auth bootstrap failed: %s", exc)

    # --------------------------------------------------------------- helpers
    def _is_env_admin(self, username: Optional[str]) -> bool:
        return bool(username) and username.lower() == self.username.lower()

    def _verify_env(self, password: str) -> bool:
        return verify_password(password, self.env_password_hash)

    def _locked_out(self, username: str) -> bool:
        now = time.time()
        fails = [t for t in self._fails.get(username, []) if now - t < LOCKOUT_SEC]
        self._fails[username] = fails
        return len(fails) >= MAX_FAILS

    def _forget_user(self, user_id: int) -> None:
        for tok in [t for t, i in self._cache.items() if i.get("user_id") == user_id]:
            self._cache.pop(tok, None)

    # ----------------------------------------------------------------- login
    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        if self._locked_out(username):
            return {"error": "locked", "retry_in": LOCKOUT_SEC}
        user = db.get_user_by_name(username)
        ok = bool(user) and verify_password(password, user["password_hash"])
        if not ok and self._is_env_admin(username) and self._verify_env(password):
            # emergency env fallback — recreate the admin row if it was deleted
            if not user:
                uid = db.create_user(self.username, self.env_password_hash, "admin")
                user = db.get_user(uid)
            ok = True
        if not ok or not user:
            self._fails.setdefault(username, []).append(time.time())
            return None
        self._fails.pop(username, None)
        token = _secrets.token_urlsafe(32)
        db.create_session(token, user["id"], TOKEN_TTL)
        self._cache[token] = {
            "username": user["username"], "role": user["role"], "user_id": user["id"],
            "must_change_password": bool(user["must_change_password"]),
            "expires_ts": time.time() + TOKEN_TTL,
        }
        return {"token": token, "user": {
            "username": user["username"], "role": user["role"],
            "must_change_password": bool(user["must_change_password"]),
            "default_creds": self.default_creds and self._is_env_admin(user["username"]),
        }}

    # -------------------------------------------------------------- validate
    def validate(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        now = time.time()
        info = self._cache.get(token)
        if info is None:
            sess = db.get_session(token)
            if not sess:
                return None
            info = {
                "username": sess["username"], "role": sess["role"],
                "user_id": sess["user_id"],
                "must_change_password": bool(sess["must_change_password"]),
                "expires_ts": sess["expires_ts"],
            }
            self._cache[token] = info
        if info["expires_ts"] < now:
            self._cache.pop(token, None)
            db.delete_session(token)
            return None
        return {"username": info["username"], "role": info["role"],
                "user_id": info["user_id"],
                "must_change_password": info["must_change_password"]}

    def logout(self, token: Optional[str]) -> None:
        self._cache.pop(token or "", None)
        if token:
            db.delete_session(token)

    # ------------------------------------------------- self-service password
    def change_password(self, user_id: int, current: str, new: str) -> Optional[bool]:
        """True on success, False on wrong current password, None if too weak."""
        user = db.get_user(user_id)
        if not user:
            return False
        ok = verify_password(current, user["password_hash"])
        if not ok and self._is_env_admin(user["username"]) and self._verify_env(current):
            ok = True
        if not ok:
            return False
        if len(new) < 6:
            return None
        db.set_user_password(user_id, hash_password(new), must_change=False)
        db.delete_user_sessions(user_id)   # revoke everywhere; client re-logs-in
        self._forget_user(user_id)
        return True

    # ---------------------------------------------------- admin: manage users
    def create_user(self, username: str, password: str, role: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip()
        role = role if role in ROLES else "operator"
        if not username:
            return {"error": "username"}
        if len(password or "") < 6:
            return {"error": "weak"}
        if db.get_user_by_name(username):
            return {"error": "exists"}
        uid = db.create_user(username, hash_password(password), role)
        return {"id": uid, "username": username, "role": role}

    def list_users(self) -> List[Dict[str, Any]]:
        return db.list_users()

    def delete_user(self, user_id: int, acting_user_id: int) -> Dict[str, Any]:
        if user_id == acting_user_id:
            return {"error": "self"}
        users = db.list_users()
        target = next((u for u in users if u["id"] == user_id), None)
        if not target:
            return {"error": "notfound"}
        admins = [u for u in users if u["role"] == "admin"]
        if target["role"] == "admin" and len(admins) <= 1:
            return {"error": "last_admin"}
        db.delete_user(user_id)
        self._forget_user(user_id)
        return {"ok": True}


auth_service = AuthService()
