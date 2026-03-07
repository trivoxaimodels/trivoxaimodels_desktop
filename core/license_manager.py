"""
License Manager for Trivox AI Models

Enforces payment requirement with ONE FREE TRIAL generation.
Features:
- One free trial generation for new users
- Hardware binding (prevents license sharing)
- Offline validation with cache
- Secure local storage
"""

import os
import json
import hashlib
import platform
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

from config.payment_config import payment_settings
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LicenseData:
    """License data structure for local storage."""

    key: str
    user_id: str
    plan_id: str
    credits: int
    created_at: str
    expires_at: str
    hardware_fingerprint: str
    is_active: bool = True
    last_validated: Optional[str] = None
    offline_grace_period_end: Optional[str] = None


@dataclass
class TrialData:
    """Trial data structure for tracking free generations."""

    generations_used: int = 0
    generations_remaining: int = 1  # Default to 1 free generation
    first_used_at: Optional[str] = None
    last_used_at: Optional[str] = None
    hardware_fingerprint: str = ""


class LicenseManager:
    """
    Manages license validation and trial tracking.

    Allows ONE free generation before requiring license.
    """

    OFFLINE_GRACE_DAYS = 7

    def __init__(self):
        # Use user-writable location for config files
        import os

        app_data = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or str(Path.home())
        )
        config_dir = Path(app_data) / "Trivox AI Models" / "config"

        self.LICENSE_FILE = config_dir / "license.json"
        self.TRIAL_FILE = config_dir / "trial.json"

        self._current_license: Optional[LicenseData] = None
        self._trial_data: Optional[TrialData] = None
        self._hardware_fp = self._generate_hardware_fingerprint()
        self._ensure_dirs()
        self._load_license()
        self._load_trial()

    def _ensure_dirs(self):
        """Ensure directories exist."""
        self.LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _generate_hardware_fingerprint(self) -> str:
        """Generate unique hardware fingerprint."""
        system_info = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
            "uuid": self._get_system_uuid(),
        }
        info_string = json.dumps(system_info, sort_keys=True)
        fingerprint = hashlib.sha256(info_string.encode()).hexdigest()[:32]
        return fingerprint

    def _get_system_uuid(self) -> str:
        """Get system UUID."""
        try:
            if platform.system() == "Windows":
                import subprocess

                result = subprocess.run(
                    ["wmic", "csproduct", "get", "uuid"], capture_output=True, text=True
                )
                return result.stdout.strip().split("\n")[-1].strip()
            else:
                machine_id_path = Path("/etc/machine-id")
                if machine_id_path.exists():
                    return machine_id_path.read_text().strip()
                return str(uuid.getnode())
        except Exception:
            return str(uuid.uuid4())

    def _load_license(self):
        """Load license from storage."""
        if not self.LICENSE_FILE.exists():
            return
        try:
            data = json.loads(self.LICENSE_FILE.read_text())
            self._current_license = LicenseData(**data)
        except Exception as e:
            logger.error(f"Failed to load license: {e}")

    def _load_trial(self):
        """Load trial data from storage."""
        if not self.TRIAL_FILE.exists():
            # Initialize trial data
            self._trial_data = TrialData(
                generations_remaining=payment_settings.trial_generations,
                hardware_fingerprint=self._hardware_fp,
            )
            self._save_trial()
            return

        try:
            data = json.loads(self.TRIAL_FILE.read_text())
            self._trial_data = TrialData(**data)
        except Exception as e:
            logger.error(f"Failed to load trial: {e}")
            self._trial_data = TrialData(
                generations_remaining=payment_settings.trial_generations,
                hardware_fingerprint=self._hardware_fp,
            )

    def _save_license(self):
        """Save license to storage."""
        if self._current_license:
            try:
                self.LICENSE_FILE.write_text(
                    json.dumps(asdict(self._current_license), indent=2)
                )
            except Exception as e:
                logger.error(f"Failed to save license: {e}")

    def _save_trial(self):
        """Save trial data to storage."""
        if self._trial_data:
            try:
                self.TRIAL_FILE.write_text(
                    json.dumps(asdict(self._trial_data), indent=2)
                )
            except Exception as e:
                logger.error(f"Failed to save trial: {e}")

    # ═════════════════════════════════════════════════════════════════
    # TRIAL METHODS — SERVER-VALIDATED
    # Server is the source of truth. Local files are read-only cache.
    # ═════════════════════════════════════════════════════════════════

    def has_trial_available(self) -> bool:
        """Check if user has free trial generations available (server-side)."""
        # 1. Check server first
        try:
            from core.server_auth import check_device_server
            status = check_device_server(self._hardware_fp)
            if status.get("online"):
                remaining = status.get("trial_remaining", 0)
                # Sync local cache
                if self._trial_data:
                    self._trial_data.generations_remaining = remaining
                    self._save_trial()
                return remaining > 0
        except Exception as e:
            logger.warning(f"Server trial check failed, using local: {e}")

        # 2. Fallback: local cache
        if not self._trial_data:
            return False

        # Check hardware fingerprint (prevent sharing trial)
        if self._trial_data.hardware_fingerprint != self._hardware_fp:
            logger.warning("Trial hardware mismatch")
            return False

        return self._trial_data.generations_remaining > 0

    def get_trial_remaining(self) -> int:
        """Get number of remaining trial generations (server-side)."""
        # Try server first
        try:
            from core.server_auth import get_trial_remaining_server
            remaining = get_trial_remaining_server(self._hardware_fp)
            return max(0, remaining)
        except Exception:
            pass

        # Fallback: local
        if not self._trial_data:
            return 0
        return max(0, self._trial_data.generations_remaining)

    def use_trial_generation(self) -> bool:
        """
        Use one trial generation — SERVER-SIDE ATOMIC.
        Deleting local files cannot reset this counter.

        Returns True if successful, False if no trials remaining.
        """
        # 1. Try to deduct on server (atomic, tamper-proof)
        try:
            from core.server_auth import use_trial_server
            result = use_trial_server(self._hardware_fp)
            if result.get("success"):
                # Update local cache to reflect server state
                now = datetime.utcnow().isoformat()
                if self._trial_data:
                    if self._trial_data.generations_used == 0:
                        self._trial_data.first_used_at = now
                    self._trial_data.generations_used += 1
                    self._trial_data.generations_remaining = result.get("remaining", 0)
                    self._trial_data.last_used_at = now
                    self._save_trial()
                logger.info(f"Trial generation used (server). Remaining: {result.get('remaining', 0)}")
                return True
            else:
                logger.info(f"Trial denied by server: {result.get('message', 'No credits')}")
                return False
        except Exception as e:
            logger.warning(f"Server trial deduction failed: {e}")

        # 2. Fallback: local deduction (only if offline)
        if not self.has_trial_available():
            return False

        now = datetime.utcnow().isoformat()
        if self._trial_data.generations_used == 0:
            self._trial_data.first_used_at = now

        self._trial_data.generations_used += 1
        self._trial_data.generations_remaining -= 1
        self._trial_data.last_used_at = now

        self._save_trial()

        logger.info(
            f"Trial generation used (offline). Remaining: {self._trial_data.generations_remaining}"
        )
        return True

    def reset_trial(self):
        """Reset trial data (for testing only — does NOT affect server)."""
        self._trial_data = TrialData(
            generations_remaining=payment_settings.trial_generations,
            hardware_fingerprint=self._hardware_fp,
        )
        self._save_trial()

    # ═════════════════════════════════════════════════════════════════
    # LICENSE METHODS
    # ═════════════════════════════════════════════════════════════════

    def has_valid_license(self) -> bool:
        """Check if user has valid license."""
        if not self._current_license:
            return False

        if not self._current_license.is_active:
            return False

        expires_at = datetime.fromisoformat(self._current_license.expires_at)
        if datetime.utcnow() > expires_at:
            return False

        # Admin licenses (I3D-ADMIN-*) bypass hardware fingerprint check
        is_admin_license = self._current_license.key.startswith("I3D-ADMIN-")
        if is_admin_license:
            logger.info(f"Admin license detected: {self._current_license.key[:20]}...")
            return True

        # Check hardware fingerprint for non-admin licenses
        if self._current_license.hardware_fingerprint != self._hardware_fp:
            # Check if within grace period
            if self._current_license.offline_grace_period_end:
                grace_end = datetime.fromisoformat(
                    self._current_license.offline_grace_period_end
                )
                if datetime.utcnow() < grace_end:
                    logger.info(f"License valid within grace period until {grace_end}")
                    return True
            logger.warning("Hardware fingerprint mismatch and grace period expired")
            return False

        return True

    def validate_license_online(self, license_key: str) -> Dict[str, Any]:
        """Validate license online via Supabase RPC, or offline for admin licenses."""
        from core.supabase_client import get_supabase

        is_admin = license_key.startswith("I3D-ADMIN-")

        try:
            client = get_supabase()
            if not client:
                if is_admin:
                    logger.info(
                        f"Offline mode: Activating admin license {license_key[:20]}..."
                    )
                    return {
                        "valid": True,
                        "license": {
                            "user_id": "admin_user",
                            "plan_id": "admin",
                            "credits": 999999,
                        },
                        "message": "Admin license activated (offline mode)",
                    }
                return {
                    "valid": False,
                    "message": "Connection failed. Could not reach server. Admin licenses work offline.",
                }

            logger.info(
                f"Validating license with Supabase: {license_key} on device {self._hardware_fp}"
            )

            response = client.rpc(
                "validate_license",
                {"p_license_key": license_key, "p_device_id": self._hardware_fp},
            ).execute()

            result = response.data

            if not result:
                return {"valid": False, "message": "Empty response from server."}

            if result.get("valid"):
                return {
                    "valid": True,
                    "license": {
                        "user_id": "supabase_user",
                        "plan_id": result.get("plan", "starter"),
                        "credits": 999999,
                    },
                    "message": result.get("message", "License validated successfully"),
                }
            else:
                return {
                    "valid": False,
                    "message": result.get("message", "Invalid license"),
                }

        except Exception as e:
            logger.error(f"Online validation failed: {e}")
            if is_admin:
                return {
                    "valid": True,
                    "license": {
                        "user_id": "admin_user",
                        "plan_id": "admin",
                        "credits": 999999,
                    },
                    "message": "Admin license activated (offline fallback)",
                }
            return {"valid": False, "message": f"Validation error: {str(e)}"}

    def activate_license(self, license_key: str, license_obj) -> bool:
        """Activate license on this machine."""
        try:
            # Admin licenses get longer grace periods
            is_admin = license_key.startswith("I3D-ADMIN-")
            grace_days = 365 if is_admin else self.OFFLINE_GRACE_DAYS
            grace_period_end = datetime.utcnow() + timedelta(days=grace_days)

            # Admin licenses get 10-year expiration (effectively lifetime)
            if is_admin:
                expires_at = datetime.utcnow() + timedelta(days=3650)
            else:
                # Check if license_obj has an expiration or default to 30 days
                obj_exp = (
                    license_obj.get("expires_at")
                    if isinstance(license_obj, dict)
                    else getattr(license_obj, "expires_at", None)
                )

                if obj_exp:
                    if isinstance(obj_exp, str):
                        try:
                            expires_at = datetime.fromisoformat(
                                obj_exp.replace("Z", "+00:00")
                            )
                        except ValueError:
                            expires_at = datetime.utcnow() + timedelta(days=30)
                    else:
                        expires_at = obj_exp
                else:
                    expires_at = datetime.utcnow() + timedelta(days=30)

            # Extract fields safely (dict or object)
            user_id = (
                license_obj.get("user_id", "local_user")
                if isinstance(license_obj, dict)
                else getattr(license_obj, "user_id", "local_user")
            )
            plan_id = (
                license_obj.get("plan_id", "starter")
                if isinstance(license_obj, dict)
                else getattr(license_obj, "plan_id", "starter")
            )
            credits = (
                license_obj.get("credits", 0)
                if isinstance(license_obj, dict)
                else getattr(license_obj, "credits", 0)
            )

            self._current_license = LicenseData(
                key=license_key,
                user_id=user_id,
                plan_id=plan_id,
                credits=credits,
                created_at=datetime.utcnow().isoformat(),
                expires_at=expires_at.isoformat(),
                hardware_fingerprint=self._hardware_fp,
                is_active=True,
                last_validated=datetime.utcnow().isoformat(),
                offline_grace_period_end=grace_period_end.isoformat(),
            )

            self._save_license()
            logger.info(f"License activated: {license_key[:8]}... (Admin: {is_admin})")
            return True
        except Exception as e:
            logger.error(f"Failed to activate license: {e}")
            return False

    def deactivate_license(self):
        """Deactivate current license."""
        if self._current_license:
            self._current_license.is_active = False
            self._save_license()

    def remove_license(self):
        """Remove license completely."""
        if self.LICENSE_FILE.exists():
            self.LICENSE_FILE.unlink()
        self._current_license = None

    def get_license_info(self) -> Optional[Dict]:
        """Get license information."""
        if not self._current_license:
            return None

        license_data = self._current_license
        expires_at = datetime.fromisoformat(license_data.expires_at)
        days_remaining = (expires_at - datetime.utcnow()).days

        return {
            "key": license_data.key[:8] + "...",
            "plan_id": license_data.plan_id,
            "credits": license_data.credits,
            "expires_at": license_data.expires_at,
            "days_remaining": days_remaining,
            "is_active": license_data.is_active,
        }

    def deduct_credits(self, amount: int) -> bool:
        """Deduct credits from license."""
        if not self._current_license:
            return False

        if self._current_license.credits < amount:
            return False

        self._current_license.credits -= amount
        self._save_license()
        return True

    def get_credits(self) -> int:
        """Get remaining credits."""
        if not self._current_license:
            return 0
        return self._current_license.credits

    def can_use_app(self) -> bool:
        """
        Check if user can use the app (either has trial or license).

        This is the main check before allowing any generation.
        """
        return self.has_trial_available() or self.has_valid_license()

    def require_license_or_trial(self) -> bool:
        """
        Enforce license or trial requirement.

        Returns True if can proceed, raises exception otherwise.
        """
        if self.can_use_app():
            return True

        raise LicenseRequiredError(
            "You have used your free trial. Please purchase a license to continue."
        )

    # ═════════════════════════════════════════════════════════════════
    # ADMIN LICENSE METHODS
    # ═════════════════════════════════════════════════════════════════

    def is_admin_license(self) -> bool:
        """Check if current license is an admin license (I3D-ADMIN-*)."""
        if not self._current_license:
            return False
        if not self._current_license.is_active:
            return False
        return self._current_license.key.startswith("I3D-ADMIN-")

    def _get_admin_auth_path(self) -> Path:
        """Get path to admin auth file."""
        return self.LICENSE_FILE.parent / "admin_auth.json"

    def is_admin_password_set(self) -> bool:
        """Check if an admin password has been configured."""
        auth_path = self._get_admin_auth_path()
        if not auth_path.exists():
            return False
        try:
            data = json.loads(auth_path.read_text())
            return bool(data.get("admin_password_hash"))
        except Exception:
            return False

    def set_admin_password(self, password: str) -> bool:
        """Set the admin password for desktop admin panel access."""
        try:
            auth_path = self._get_admin_auth_path()
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
            data = {"admin_password_hash": pw_hash}
            auth_path.write_text(json.dumps(data, indent=2))
            logger.info("Admin password set successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set admin password: {e}")
            return False

    def verify_admin_password(self, password: str) -> bool:
        """Verify the admin password for desktop admin panel access."""
        auth_path = self._get_admin_auth_path()
        if not auth_path.exists():
            return False
        try:
            data = json.loads(auth_path.read_text())
            stored_hash = data.get("admin_password_hash", "")
            pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return pw_hash == stored_hash
        except Exception as e:
            logger.error(f"Failed to verify admin password: {e}")
            return False

    def get_license_key(self) -> Optional[str]:
        """Get the current license key (full key for internal use)."""
        if not self._current_license:
            return None
        return self._current_license.key


class LicenseRequiredError(Exception):
    """Exception raised when license is required but not present."""

    pass


# Global instance
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """Get or create license manager instance."""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager
