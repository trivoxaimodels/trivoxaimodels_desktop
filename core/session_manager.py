"""
Session Manager for TrivoxModels Desktop

Manages user sessions with:
  - Device fingerprint authentication (mirrors web app server_auth.py)
  - Username/password login (mirrors web app credit_manager.py)
  - Credit balance tracking via Supabase
  - Offline grace period support
"""

import time
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field, asdict

from .device_fingerprint import get_device_fingerprint, get_device_fingerprint_short
from . import credit_manager
from . import server_auth


@dataclass
class UserSession:
    """User session data."""

    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    device_fingerprint: str = ""
    credits_balance: int = 0
    trial_remaining: int = 0
    trial_used: int = 0
    is_admin: bool = False
    is_authenticated: bool = False
    auth_method: str = ""  # "device", "password", "google", "github"
    login_time: float = field(default_factory=time.time)
    last_validation: float = field(default_factory=time.time)


class SessionManager:
    """
    Manages user authentication sessions for the desktop app.

    Uses the same Supabase tables as the web app:
      - web_users for account data
      - user_credits for balance
      - registered_devices for device tracking
    """

    OFFLINE_GRACE_HOURS = 24
    VALIDATION_INTERVAL = 300  # seconds

    def __init__(self):
        self._session: Optional[UserSession] = None
        self._device_fp: str = get_device_fingerprint()
        self._device_fp_short: str = get_device_fingerprint_short()
        self._on_session_change: Optional[Callable] = None
        
        # Path for local session storage
        self._session_path = self._get_session_path()
        
        # Try to load existing session
        self.load_session()

    def _get_session_path(self) -> Path:
        """Get the path to store local session data."""
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = Path(appdata) / "trivoxaimodels"
        else:
            base_dir = Path.home() / ".trivoxaimodels"
        
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "session.json"

    def save_session(self):
        """Save the current session to local storage."""
        if not self._session:
            if self._session_path.exists():
                self._session_path.unlink()
            return

        try:
            session_data = asdict(self._session)
            # Remove objects that can't be serialized if any (though currently all are simple)
            with open(self._session_path, "w") as f:
                json.dump(session_data, f)
        except Exception as e:
            print(f"Failed to save session: {e}")

    def load_session(self):
        """Load session from local storage if available."""
        if not self._session_path.exists():
            return

        try:
            with open(self._session_path, "r") as f:
                session_data = json.load(f)
            
            # Reconstruct UserSession
            self._session = UserSession(**session_data)
            
            # Validate fingerprint matches current machine
            if self._session.device_fingerprint and self._session.device_fingerprint != self._device_fp:
                # Fingerprint mismatch - invalid session for this device
                self._session = None
                self._session_path.unlink()
                return

            print(f"Restored session for {self._session.email or self._session.username}")
        except Exception as e:
            print(f"Failed to load session: {e}")
            self._session = None

    @property
    def device_fingerprint(self) -> str:
        return self._device_fp

    @property
    def device_fingerprint_short(self) -> str:
        return self._device_fp_short

    @property
    def session(self) -> Optional[UserSession]:
        return self._session

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None and getattr(self._session, 'is_authenticated', False)

    @property
    def user_id(self) -> Optional[str]:
        return self._session.user_id if self._session else None

    @property
    def credits(self) -> int:
        return self._session.credits_balance if self._session else 0

    @property
    def trial_remaining(self) -> int:
        return self._session.trial_remaining if self._session else 0

    def set_session_change_callback(self, callback: Callable):
        self._on_session_change = callback

    def _notify_session_change(self):
        if self._on_session_change:
            self._on_session_change(self._session)

    # ═══════════════════════════════════════════════════════════
    #  DEVICE LOGIN (primary desktop flow)
    # ═══════════════════════════════════════════════════════════

    def login_with_device(self) -> Dict[str, Any]:
        """
        Login using device fingerprint.
        Checks registered_devices table directly (mirrors web app server_auth.py).
        """
        device_status = server_auth.check_device_server(self._device_fp)

        if device_status.get("is_banned"):
            return {
                "success": False,
                "error": "Device is banned",
                "reason": device_status.get("ban_reason", "Contact support"),
            }

        if device_status.get("registered") and device_status.get("user_id"):
            user_id = str(device_status["user_id"])
            # Get full balance from Supabase (same tables as web app)
            balance_info = credit_manager.get_user_balance(user_id, self._device_fp)

            self._session = UserSession(
                user_id=user_id,
                device_fingerprint=self._device_fp,
                credits_balance=balance_info.get("credits_balance", 0),
                trial_remaining=balance_info.get("trial_remaining", 0),
                trial_used=balance_info.get("trial_used", 0),
                is_authenticated=True,
                auth_method="device",
            )
            self._notify_session_change()

            return {
                "success": True,
                "user_id": user_id,
                "credits": balance_info.get("credits_balance", 0),
                "trial_remaining": balance_info.get("trial_remaining", 0),
            }

        # Device not registered
        return {
            "success": False,
            "error": "Device not registered",
            "needs_registration": True,
            "trial_remaining": device_status.get("trial_remaining", 1),
        }

    def register_device(self, user_id: str = None) -> Dict[str, Any]:
        """
        Register the current device.
        Creates web_users entry + registered_devices entry via server_auth.
        """
        result = server_auth.register_device_server(
            self._device_fp,
            password_hash="",
            machine_name=f"Desktop App ({self._device_fp_short})",
        )

        if result.get("success"):
            actual_user_id = str(result.get("user_id", ""))
            if actual_user_id:
                balance_info = credit_manager.get_user_balance(
                    actual_user_id, self._device_fp
                )

                self._session = UserSession(
                    user_id=actual_user_id,
                    device_fingerprint=self._device_fp,
                    credits_balance=balance_info.get("credits_balance", 0),
                    trial_remaining=balance_info.get("trial_remaining", 0),
                    trial_used=balance_info.get("trial_used", 0),
                    is_authenticated=True,
                    auth_method="device",
                )
                self._notify_session_change()

        return result

    # ═══════════════════════════════════════════════════════════
    #  USERNAME/PASSWORD LOGIN (same as web app)
    # ═══════════════════════════════════════════════════════════

    def login_with_password(self, username: str, password: str) -> Dict[str, Any]:
        """
        Login using username/password.
        Uses the same verify_user_login as the web app.
        """
        result = credit_manager.verify_user_login(username, password)

        if result.get("success"):
            user_id = str(result["user_id"])
            balance_info = credit_manager.get_user_balance(user_id, self._device_fp)

            self._session = UserSession(
                user_id=user_id,
                username=result.get("username"),
                device_fingerprint=self._device_fp,
                credits_balance=balance_info.get("credits_balance", 0),
                trial_remaining=balance_info.get("trial_remaining", 0),
                trial_used=balance_info.get("trial_used", 0),
                is_admin=result.get("is_admin", False),
                is_authenticated=True,
                auth_method="password",
            )

            # Link device to user account
            try:
                from .supabase_client import get_supabase

                sb = get_supabase()
                if sb:
                    # Update or create device entry
                    existing = (
                        sb.table("registered_devices")
                        .select("id")
                        .eq("device_fingerprint", self._device_fp)
                        .execute()
                    )
                    if existing.data:
                        sb.table("registered_devices").update(
                            {
                                "user_id": user_id,
                                "is_registered": True,
                            }
                        ).eq("device_fingerprint", self._device_fp).execute()
                    else:
                        sb.table("registered_devices").insert(
                            {
                                "device_fingerprint": self._device_fp,
                                "user_id": user_id,
                                "is_registered": True,
                                "device_name": f"Desktop App ({self._device_fp_short})",
                            }
                        ).execute()
            except Exception:
                pass

            self._notify_session_change()

        return result

    # ═══════════════════════════════════════════════════════════
    #  SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def validate_session(self) -> bool:
        """Validate the current session with the server."""
        if not self._session:
            return False

        elapsed = time.time() - self._session.last_validation
        if elapsed < self.VALIDATION_INTERVAL:
            return True

        # Re-validate with server
        if self._session.auth_method == "device":
            device_status = server_auth.check_device_server(self._device_fp)
            if device_status.get("is_banned"):
                self.logout()
                return False
            if device_status.get("registered"):
                self._session.last_validation = time.time()
                balance = credit_manager.get_user_balance(
                    self._session.user_id, self._device_fp
                )
                self._session.credits_balance = balance.get("credits_balance", 0)
                self._session.trial_remaining = balance.get("trial_remaining", 0)
                return True
        elif self._session.auth_method == "password":
            balance = credit_manager.get_user_balance(
                self._session.user_id, self._device_fp
            )
            if "error" not in balance:
                self._session.last_validation = time.time()
                self._session.credits_balance = balance.get("credits_balance", 0)
                self._session.trial_remaining = balance.get("trial_remaining", 0)
                return True

        # Check offline grace period
        hours_since_login = (time.time() - self._session.login_time) / 3600
        if hours_since_login < self.OFFLINE_GRACE_HOURS:
            return True

        self.logout()
        return False

    def refresh_credits(self) -> int:
        """Refresh credit balance from server."""
        if not self._session:
            return 0

        balance = credit_manager.get_user_balance(
            self._session.user_id, self._device_fp
        )
        self._session.credits_balance = balance.get("credits_balance", 0)
        self._session.trial_remaining = balance.get("trial_remaining", 0)
        return self._session.credits_balance

    def deduct_credit(
        self,
        resolution: str = "1024",
        model_id: str = "tripo3d",
        input_type: str = "image",
        output_format: str = "glb",
        is_trial: bool = False,
    ) -> Dict[str, Any]:
        """Deduct credits for a generation (same as web app)."""
        if not self._session:
            return {"success": False, "error": "No active session"}

        result = credit_manager.deduct_credits(
            self._session.user_id,
            resolution,
            model_id,
            input_type,
            output_format,
            is_trial=is_trial,
            device_fingerprint=self._device_fp,
        )

        if result.get("success"):
            self._session.credits_balance = result.get("balance_after", 0)
            if result.get("source") == "trial_free":
                self._session.trial_remaining = 0
                self._session.trial_used = 1
            self._notify_session_change()

        return result

    def logout(self):
        """Logout the current user."""
        self._session = None
        if self._session_path.exists():
            self._session_path.unlink()
        self._notify_session_change()

    def get_session_info(self) -> Dict[str, Any]:
        """Get session information for display."""
        if not self._session:
            return {
                "authenticated": False,
                "device_id": self._device_fp_short,
            }

        return {
            "authenticated": True,
            "user_id": self._session.user_id,
            "username": self._session.username,
            "email": self._session.email,
            "device_id": self._device_fp_short,
            "auth_method": self._session.auth_method,
            "credits": self._session.credits_balance,
            "trial_remaining": self._session.trial_remaining,
            "is_admin": self._session.is_admin,
        }
