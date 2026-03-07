"""
Server-side bcrypt password authentication for Trivox AI Models.
Password hash is stored in config; no plain password is ever saved.
"""

import os
import json
import hmac
import hashlib
import base64
import time
from pathlib import Path
from typing import Optional

try:
    import bcrypt
except ImportError:
    bcrypt = None  # type: ignore

# Config file under project (server-side only)
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
AUTH_FILE = CONFIG_DIR / "auth.json"
# Cookie/session signing (web); keep secret in env or auth file
SECRET_ENV = "IMAGETO3D_SECRET_KEY"
# Session validity seconds (web)
SESSION_VALIDITY_SECONDS = 24 * 3600


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _read_auth_config() -> dict:
    """Read auth config from disk. Never exposes hash to client."""
    if not AUTH_FILE.exists():
        return {}
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_auth_config(data: dict) -> None:
    _ensure_config_dir()
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_password_configured() -> bool:
    """Return True if a password hash is configured (app is protected)."""
    if os.getenv("IMAGETO3D_PASSWORD"):
        return True
    if not bcrypt:
        return False
    cfg = _read_auth_config()
    return bool(cfg.get("password_hash"))


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt. Use for initial setup only."""
    if not bcrypt:
        raise RuntimeError("bcrypt is not installed. Install with: pip install bcrypt")
    plain_bytes = plain.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("ascii")


def verify_password(plain: str) -> bool:
    """
    Verify plain password against the stored hash (server-side).
    Returns True only if hash is configured and password matches.
    """
    env_password = os.getenv("IMAGETO3D_PASSWORD")
    if env_password:
        return plain == env_password
    if not bcrypt:
        return False
    cfg = _read_auth_config()
    stored = cfg.get("password_hash")
    if not stored:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("ascii"))
    except Exception:
        return False


def set_password(plain: str) -> None:
    """Store a new password hash in config (server-side). Overwrites existing."""
    _write_auth_config({"password_hash": hash_password(plain)})


def get_secret_key() -> str:
    """Secret for signing session cookies. Generated once and stored."""
    cfg = _read_auth_config()
    key = cfg.get("secret_key") or os.getenv(SECRET_ENV)
    if not key:
        key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
        _ensure_config_dir()
        data = _read_auth_config()
        data["secret_key"] = key
        _write_auth_config(data)
    return key


def create_session_token() -> str:
    """Create a signed session token (expiry embedded)."""
    expiry = str(int(time.time()) + SESSION_VALIDITY_SECONDS)
    payload = expiry.encode("utf-8")
    secret = get_secret_key().encode("utf-8")
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + sig).decode("ascii").rstrip("=")


def verify_session_token(token: str) -> bool:
    """Verify signed session token and expiry."""
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(token + "==")
        if len(raw) < 10 + 32:
            return False
        payload = raw[:10]
        expiry = int(payload.decode("utf-8"))
        if time.time() > expiry:
            return False
        secret = get_secret_key().encode("utf-8")
        expected = hmac.new(secret, payload, hashlib.sha256).digest()
        return hmac.compare_digest(expected, raw[10:])
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    import getpass

    if len(sys.argv) >= 2 and sys.argv[1] in ("set-password", "set_password"):
        if bcrypt is None:
            print("Error: bcrypt is not installed. Run: pip install bcrypt")
            sys.exit(1)
        pwd = (sys.argv[2] if len(sys.argv) > 2 else None) or getpass.getpass(
            "New application password: "
        )
        pwd2 = getpass.getpass("Confirm password: ")
        if pwd != pwd2:
            print("Passwords do not match.")
            sys.exit(1)
        if len(pwd) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)
        set_password(pwd)
        print("Password set. Stored in config/auth.json (hash only).")
    else:
        print("Usage: python -m core.auth set-password  [password]")
        print("  If password is omitted, you will be prompted.")
