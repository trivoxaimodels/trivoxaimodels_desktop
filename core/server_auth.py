"""
Server-Side Device Authentication for Trivox AI Models

All device registration, login, and trial tracking is validated against
Supabase. Local files serve as read-only cache for offline fallback.

Tampering detection: if local files are deleted but the server already
has a record, the user is warned and the attempt is logged.
"""

import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Optional, Dict, Any


def _get_supabase():
    """Get Supabase client, returns None if unavailable."""
    try:
        from core.supabase_client import get_supabase_client
        return get_supabase_client()
    except Exception:
        return None


def _get_config_dir() -> Path:
    """Get user-writable config directory."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "trivoxaimodels" / "config"
    return Path(os.path.expanduser("~")) / ".trivoxaimodels" / "config"


def _get_local_cache_file() -> Path:
    """Local cache file for offline fallback."""
    return _get_config_dir() / "device_server_cache.json"


def _load_local_cache() -> dict:
    """Load cached server state from local file."""
    cache_file = _get_local_cache_file()
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_local_cache(data: dict):
    """Save server state to local cache for offline fallback."""
    cache_file = _get_local_cache_file()
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  SERVER-SIDE DEVICE OPERATIONS
# ═══════════════════════════════════════════════════════════════════


def check_device_server(fingerprint: str) -> Dict[str, Any]:
    """
    Check device registration status on the server.

    Returns:
        {
            'found': bool,
            'registered': bool,
            'trial_remaining': int,
            'is_banned': bool,
            'ban_reason': str,
            'tamper_attempts': int,
            'online': bool  # whether server was reachable
        }
    """
    sb = _get_supabase()
    if not sb:
        # Offline fallback
        cache = _load_local_cache()
        if cache.get("fingerprint") == fingerprint:
            cache["online"] = False
            return cache
        return {
            "found": False,
            "registered": False,
            "trial_remaining": 1,
            "is_banned": False,
            "tamper_attempts": 0,
            "online": False,
        }

    try:
        result = sb.rpc("check_device", {"p_fingerprint": fingerprint}).execute()
        data = result.data or {}
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif isinstance(data, list):
            data = {}

        data["online"] = True

        # Cache the result locally
        cache_data = {**data, "fingerprint": fingerprint, "cached_at": time.time()}
        _save_local_cache(cache_data)

        return data
    except Exception as e:
        print(f"[ServerAuth] check_device failed: {e}")
        cache = _load_local_cache()
        if cache.get("fingerprint") == fingerprint:
            cache["online"] = False
            return cache
        return {
            "found": False,
            "registered": False,
            "trial_remaining": 1,
            "is_banned": False,
            "tamper_attempts": 0,
            "online": False,
        }


def register_device_server(
    fingerprint: str,
    password_hash: str,
    machine_name: str = "",
    platform_info: str = "",
    app_version: str = "",
) -> Dict[str, Any]:
    """
    Register a device on the server.

    Returns:
        {
            'success': bool,
            'already_registered': bool,
            'trial_remaining': int,
            'message': str,
            'is_banned': bool (if already registered and banned)
        }
    """
    sb = _get_supabase()
    if not sb:
        return {
            "success": False,
            "already_registered": False,
            "message": "Cannot connect to server. Please check your internet connection.",
            "offline": True,
        }

    try:
        result = sb.rpc("register_device_server", {
            "p_fingerprint": fingerprint,
            "p_password_hash": password_hash,
            "p_machine_name": machine_name,
            "p_platform": platform_info,
            "p_app_version": app_version,
        }).execute()

        data = result.data or {}
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif isinstance(data, list):
            data = {}

        # Workaround for postgrest-py issue: map 'msg' back to 'message'
        if "msg" in data:
            data["message"] = data.pop("msg")

        # If registration was successful, cache the record
        if data.get("success"):
            cache_data = {
                "fingerprint": fingerprint,
                "found": True,
                "registered": True,
                "trial_remaining": data.get("trial_remaining", 1),
                "is_banned": False,
                "tamper_attempts": 0,
                "online": True,
                "cached_at": time.time(),
                "password_hash": password_hash,
            }
            _save_local_cache(cache_data)

        return data
    except Exception as e:
        # Workaround for postgrest-py "JSON could not be generated" error 
        # when a function returns jsonb but the client library fails to parse it properly
        # The actual response is sometimes hidden in the 'details' field as a bytes string
        try:
            # Check if it's a dict (some versions of the client return dict for errors)
            error_msg = str(e)
            details_str = ""
            
            if isinstance(e, dict):
                error_msg = e.get('message', '')
                details_str = e.get('details', '')
            elif hasattr(e, 'message'):
                error_msg = e.message
                details_str = getattr(e, 'details', '')

            if error_msg == 'JSON could not be generated' and details_str:
                if details_str.startswith("b'") or details_str.startswith('b"'):
                    details_str = details_str[2:-1]  # Remove b' '
                
                # Check if it looks like json
                if "{" in details_str:
                    import json
                    # Clean up common escapes in the "details" string
                    cleaned_details = details_str.replace("\\\"", "\"").replace("\\'", "'").replace("\\\\", "\\")
                    parsed = json.loads(cleaned_details)
                    if parsed.get("success") or parsed.get("already_registered"):
                        return parsed
        except Exception as inner_e:
            print(f"[ServerAuth] postgrest parse workaround failed: {inner_e}")
            
        print(f"[ServerAuth] register_device_server failed: {e}")
        return {
            "success": False,
            "already_registered": False,
            "message": f"Server error: {e}",
        }


def verify_device_login_server(fingerprint: str) -> Dict[str, Any]:
    """
    Get password hash from server for login verification.

    Returns:
        {
            'found': bool,
            'password_hash': str,
            'is_banned': bool,
            'ban_reason': str,
            'online': bool
        }
    """
    sb = _get_supabase()
    if not sb:
        # Offline fallback: use cached password hash
        cache = _load_local_cache()
        if cache.get("fingerprint") == fingerprint and cache.get("password_hash"):
            return {
                "found": True,
                "password_hash": cache["password_hash"],
                "is_banned": cache.get("is_banned", False),
                "online": False,
            }
        return {"found": False, "password_hash": "", "online": False}

    try:
        result = sb.rpc("verify_device_login", {"p_fingerprint": fingerprint}).execute()
        data = result.data or {}
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif isinstance(data, list):
            data = {}

        data["online"] = True

        # Cache the password hash for offline fallback
        if data.get("found") and data.get("password_hash"):
            cache = _load_local_cache()
            cache["password_hash"] = data["password_hash"]
            cache["fingerprint"] = fingerprint
            cache["is_banned"] = data.get("is_banned", False)
            cache["cached_at"] = time.time()
            _save_local_cache(cache)

        return data
    except Exception as e:
        print(f"[ServerAuth] verify_device_login failed: {e}")
        cache = _load_local_cache()
        if cache.get("fingerprint") == fingerprint and cache.get("password_hash"):
            return {
                "found": True,
                "password_hash": cache["password_hash"],
                "is_banned": cache.get("is_banned", False),
                "online": False,
            }
        return {"found": False, "password_hash": "", "online": False}


def use_trial_server(fingerprint: str) -> Dict[str, Any]:
    """
    Atomically consume 1 trial credit on the server.
    Deleting local files cannot reset this.

    Returns:
        {'success': bool, 'remaining': int, 'message': str}
    """
    sb = _get_supabase()
    if not sb:
        return {
            "success": False,
            "remaining": 0,
            "message": "Cannot connect to server. Trial requires internet.",
        }

    try:
        result = sb.rpc("use_device_trial", {"p_fingerprint": fingerprint}).execute()
        data = result.data or {}
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif isinstance(data, list):
            data = {}

        # Workaround for postgrest-py issue: map 'msg' back to 'message'
        if "msg" in data:
            data["message"] = data.pop("msg")

        # Update local cache
        if data.get("success"):
            cache = _load_local_cache()
            cache["trial_remaining"] = data.get("remaining", 0)
            cache["cached_at"] = time.time()
            _save_local_cache(cache)

        return data
    except Exception as e:
        print(f"[ServerAuth] use_trial_server failed: {e}")
        return {
            "success": False,
            "remaining": 0,
            "message": f"Server error: {e}",
        }


def report_tamper_attempt(fingerprint: str, reason: str = "Local files deleted") -> bool:
    """
    Report a tampering attempt to the server.
    Called when we detect the user deleted local auth files but
    the server already has their record.
    """
    sb = _get_supabase()
    if not sb:
        return False

    try:
        result = sb.rpc("report_tamper_attempt", {
            "p_fingerprint": fingerprint,
            "p_reason": reason,
        }).execute()
        data = result.data or {}
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return data.get("logged", False)
    except Exception as e:
        print(f"[ServerAuth] report_tamper_attempt failed: {e}")
        return False


def get_trial_remaining_server(fingerprint: str) -> int:
    """Get remaining trial credits from server."""
    status = check_device_server(fingerprint)
    return status.get("trial_remaining", 0)
