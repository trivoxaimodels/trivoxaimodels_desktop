"""
Supabase Client for Trivox AI Models

Provides connection to Supabase for:
  - Device registration and authentication
  - User profile management
  - Credit balance tracking
  - Usage logging
"""

import os
import sys
from pathlib import Path
from supabase import create_client, Client

# Auto-load .env if present (for local development and installed apps)
try:
    # Build list of candidate paths for .env
    _candidates = []
    # 1. Next to the source file (development)
    _candidates.append(Path(__file__).resolve().parent.parent / ".env")
    # 2. Next to the executable (PyInstaller frozen)
    if getattr(sys, 'frozen', False):
        _exe_dir = Path(sys.executable).resolve().parent
        _candidates.append(_exe_dir / ".env")
        # 3. PyInstaller _MEIPASS temp dir
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass:
            _candidates.append(Path(_meipass) / ".env")
        # 4. User data directory (Windows AppData)
        _appdata = os.environ.get("APPDATA", "")
        if _appdata:
            _candidates.append(Path(_appdata) / "trivoxaimodels" / ".env")

    for _env_path in _candidates:
        if _env_path.exists():
            try:
                content = _env_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = _env_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break  # Stop after first found .env
except Exception:
    pass


class SupabaseClient:
    _instance = None
    _client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.environ.get("SUPABASE_URL")
            # SECURITY FIX: Desktop app uses anon key, never service_role key.
            # RLS (Row Level Security) restricts what the device can access.
            key = os.environ.get("SUPABASE_ANON_KEY")
            
            if os.environ.get("SUPABASE_KEY"):
                print("WARNING: SUPABASE_KEY (service role) found in environment. This is a severe security risk in the desktop app.")
                # Fallback only for backward compatibility during dev
                if not key:
                    key = os.environ.get("SUPABASE_KEY")
            
            if not url or not key:
                # In development/frozen app, these should be loaded from .env or compiled configuration
                pass
            
            if url and key:
                cls._client = create_client(url, key)
            
        return cls._client


class SupabaseAuth:
    def get_client(self):
        return get_supabase()

    def sign_in_with_google(self) -> dict:
        client = self.get_client()
        if not client:
            return {}
        try:
            return {"url": client.auth.get_authorization_url(provider="google")}
        except Exception:
            try:
                # Workaround for older library versions
                res = client.auth.sign_in_with_oauth({"provider": "google"})
                return {"url": res.url}
            except Exception as e:
                print(f"Google OAuth error: {e}")
                return {}

    def sign_in_with_github(self) -> dict:
        client = self.get_client()
        if not client:
            return {}
        try:
            return {"url": client.auth.get_authorization_url(provider="github")}
        except Exception:
            try:
                res = client.auth.sign_in_with_oauth({"provider": "github"})
                return {"url": res.url}
            except Exception as e:
                print(f"GitHub OAuth error: {e}")
                return {}


# Default instances for backward compatibility with UI
auth = SupabaseAuth()

# Helper to easily get client
def get_supabase() -> Client:
    return SupabaseClient.get_client()

# Aliases for compatibility
get_supabase_client = get_supabase
