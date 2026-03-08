"""
Payment Configuration Sync Module

Synchronizes payment configuration from web app to desktop app.
This ensures desktop app uses the same payment settings as configured in web admin.

Features:
- Fetches payment config from web API
- Caches config locally with TTL
- Automatically syncs on startup and periodically
- Provides secure key retrieval for payment providers
- Handles offline mode gracefully
"""

import os
import json

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

from core.logger import get_logger

from core.supabase_client import get_supabase

logger = get_logger(__name__)

# Configuration
WEB_API_BASE_URL = os.getenv("WEB_API_URL", "https://voxelcraft.onrender.com/api/v1")
CACHE_FILE_PATH = Path.home() / ".VoxelCraft" / "payment_config_cache.json"
CACHE_TTL_MINUTES = 5


@dataclass
class PaymentConfig:
    """Payment configuration data structure"""

    provider: str = "gumroad"
    currency: str = "USD"
    test_mode: bool = True
    credit_packs: Dict[str, Any] = None
    provider_settings: Dict[str, Any] = None
    updated_at: str = ""
    last_sync: Optional[datetime] = None

    def __post_init__(self):
        if self.credit_packs is None:
            self.credit_packs = {}
        if self.provider_settings is None:
            self.provider_settings = {}


class PaymentConfigSync:
    """
    Syncs payment configuration from web app to desktop app.

    This class ensures the desktop app uses the same payment settings
    as configured in the web admin panel.
    """

    _instance: Optional["PaymentConfigSync"] = None
    _config: Optional[PaymentConfig] = None
    _last_sync: Optional[datetime] = None

    def __new__(cls) -> "PaymentConfigSync":
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_from_cache()
        return cls._instance

    def __init__(self):
        """Initialize the sync manager"""
        pass

    def sync_config(self, force: bool = False) -> bool:
        """
        Synchronize payment configuration from Supabase payment_settings table.
        Reads the same table the web app admin panel writes to.

        Args:
            force: Force sync even if cache is still valid

        Returns:
            True if sync successful, False otherwise
        """
        try:
            # Check if we need to sync
            if not force and self._is_cache_valid():
                logger.debug("Payment config cache is still valid, skipping sync")
                return True

            # Read directly from Supabase payment_settings table
            # (same table the web admin panel writes to)
            client = get_supabase()
            if not client:
                logger.warning("Supabase client not available — using cache")
                return self._config is not None

            logger.info("Syncing payment config from Supabase payment_settings table")
            try:
                result = (
                    client.table("payment_settings")
                    .select("*")
                    .eq("is_active", True)
                    .order("updated_at", desc=True)
                    .limit(1)
                    .execute()
                )
            except Exception as query_err:
                logger.error(f"Supabase query failed: {query_err}")
                if self._config:
                    logger.info("Using cached payment config")
                    return True
                return False

            if result.data and len(result.data) > 0:
                data = result.data[0]

                # Update config from Supabase row
                self._config = PaymentConfig(
                    provider=data.get("provider", "gumroad"),
                    currency=data.get("currency", "INR"),
                    test_mode=data.get("test_mode", True),
                    credit_packs=data.get("credit_packs", {}),
                    provider_settings=data.get("provider_settings", {}),
                    updated_at=data.get("updated_at", ""),
                    last_sync=datetime.now(),
                )

                # Save to cache
                self._save_to_cache()

                logger.info(
                    f"Payment config synced from Supabase. "
                    f"Provider: {self._config.provider}, Currency: {self._config.currency}"
                )
                return True
            else:
                logger.warning("No active payment config found in Supabase")
                if self._config:
                    return True
                # Set defaults
                self._config = PaymentConfig(
                    provider="gumroad",
                    currency="INR",
                    last_sync=datetime.now(),
                )
                return False

        except Exception as e:
            logger.error(f"Error syncing payment config: {e}")
            if not self._config:
                self._config = PaymentConfig(last_sync=datetime.now())
            return False

    def _is_cache_valid(self) -> bool:
        """Check if cached config is still valid"""
        if self._config is None or self._config.last_sync is None:
            return False

        age = datetime.now() - self._config.last_sync
        return age < timedelta(minutes=CACHE_TTL_MINUTES)

    def _load_from_cache(self):
        """Load config from local cache file"""
        try:
            if CACHE_FILE_PATH.exists():
                with open(CACHE_FILE_PATH, "r") as f:
                    data = json.load(f)

                self._config = PaymentConfig(
                    provider=data.get("provider", "gumroad"),
                    currency=data.get("currency", "USD"),
                    test_mode=data.get("test_mode", True),
                    credit_packs=data.get("credit_packs", {}),
                    provider_settings=data.get("provider_settings", {}),
                    updated_at=data.get("updated_at", ""),
                    last_sync=datetime.fromisoformat(data.get("last_sync"))
                    if data.get("last_sync")
                    else None,
                )

                logger.info(
                    f"Loaded payment config from cache. Provider: {self._config.provider}"
                )
        except Exception as e:
            logger.warning(f"Failed to load payment config cache: {e}")
            self._config = None

    def _save_to_cache(self):
        """Save config to local cache file"""
        try:
            CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            if self._config:
                data = {
                    "provider": self._config.provider,
                    "currency": self._config.currency,
                    "test_mode": self._config.test_mode,
                    "credit_packs": self._config.credit_packs,
                    "provider_settings": self._config.provider_settings,
                    "updated_at": self._config.updated_at,
                    "last_sync": self._config.last_sync.isoformat()
                    if self._config.last_sync
                    else None,
                }

                with open(CACHE_FILE_PATH, "w") as f:
                    json.dump(data, f, indent=2)

                logger.debug("Payment config saved to cache")
        except Exception as e:
            logger.warning(f"Failed to save payment config cache: {e}")

    def get_config(self) -> Optional[PaymentConfig]:
        """Get current payment configuration"""
        self.sync_config()
        return self._config

    def get_active_provider(self) -> str:
        """Get currently active payment provider"""
        self.sync_config()
        return self._config.provider if self._config else "gumroad"

    def get_currency(self) -> str:
        """Get payment currency"""
        self.sync_config()
        return self._config.currency if self._config else "USD"

    def get_credit_packs(self) -> Dict[str, Any]:
        """Get credit packs configuration"""
        self.sync_config()
        return self._config.credit_packs if self._config else {}

    def get_provider_settings(self, provider: str = None) -> Dict[str, Any]:
        """Get settings for specific provider"""
        self.sync_config()

        if not self._config:
            return {}

        provider = provider or self._config.provider
        return self._config.provider_settings.get(provider, {})

    def is_test_mode(self) -> bool:
        """Check if in test mode"""
        self.sync_config()
        return self._config.test_mode if self._config else True

    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status information"""
        return {
            "synced": self._config is not None and self._config.last_sync is not None,
            "provider": self._config.provider if self._config else None,
            "last_sync": self._config.last_sync.isoformat()
            if self._config and self._config.last_sync
            else None,
            "cache_valid": self._is_cache_valid() if self._config else False,
            "source": "web_api" if self._config and self._config.last_sync else "cache",
        }


class SecureKeyManager:
    """
    Manages secure retrieval of API keys from web app.
    Keys are fetched on-demand and not stored locally.
    """

    def __init__(self):
        self.config_sync = PaymentConfigSync()

    def get_api_keys(self, provider: str) -> Optional[Dict[str, str]]:
        """
        Get API keys for specific provider from web app.

        Args:
            provider: Payment provider name (razorpay, stripe, etc.)

        Returns:
            Dict with key_id, key_secret, webhook_secret or None
        """
        try:
            # Lazy imports — only needed for API key fetching
            import requests
            from core.license_manager import get_license_manager

            # Get license for authentication
            license_mgr = get_license_manager()
            if not license_mgr or not license_mgr._current_license:
                logger.warning("No valid license - cannot fetch API keys")
                return None

            license_key = license_mgr._current_license.key
            device_fingerprint = license_mgr._current_license.hardware_fingerprint

            # Fetch keys from web API
            url = f"{WEB_API_BASE_URL}/payment-config/keys/{provider}"
            params = {
                "license_key": license_key,
                "device_fingerprint": device_fingerprint,
            }

            logger.debug(f"Fetching API keys for {provider}")
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                keys = response.json()

                if "error" in keys:
                    logger.error(f"API error: {keys['error']}")
                    return None

                return keys

            else:
                logger.error(f"Failed to fetch API keys: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching API keys: {e}")
            return None

    def get_razorpay_keys(self) -> Optional[Dict[str, str]]:
        """Get Razorpay API keys"""
        return self.get_api_keys("razorpay")

    def get_stripe_keys(self) -> Optional[Dict[str, str]]:
        """Get Stripe API keys"""
        return self.get_api_keys("stripe")

    def get_paypal_keys(self) -> Optional[Dict[str, str]]:
        """Get PayPal API keys"""
        return self.get_api_keys("paypal")

    def get_gumroad_keys(self) -> Optional[Dict[str, str]]:
        """Get Gumroad API keys"""
        return self.get_api_keys("gumroad")


# Global instances
_payment_config_sync: Optional[PaymentConfigSync] = None
_secure_key_manager: Optional[SecureKeyManager] = None


def get_payment_config_sync() -> PaymentConfigSync:
    """Get or create PaymentConfigSync instance"""
    global _payment_config_sync
    if _payment_config_sync is None:
        _payment_config_sync = PaymentConfigSync()
    return _payment_config_sync


def get_secure_key_manager() -> SecureKeyManager:
    """Get or create SecureKeyManager instance"""
    global _secure_key_manager
    if _secure_key_manager is None:
        _secure_key_manager = SecureKeyManager()
    return _secure_key_manager


def get_active_payment_provider() -> str:
    """Convenience function to get active provider"""
    return get_payment_config_sync().get_active_provider()


def get_payment_currency() -> str:
    """Convenience function to get payment currency"""
    return get_payment_config_sync().get_currency()


def get_credit_packs() -> Dict[str, Any]:
    """Convenience function to get credit packs"""
    return get_payment_config_sync().get_credit_packs()


# Integration helpers
def update_payment_config_in_dialog(dialog):
    """
    Update a dialog with current payment configuration.
    Call this when opening CreditPurchaseDialog.
    """
    try:
        config_sync = get_payment_config_sync()
        config_sync.sync_config()

        # Update dialog's internal state
        if hasattr(dialog, "active_provider"):
            dialog.active_provider = config_sync.get_active_provider()

        if hasattr(dialog, "currency"):
            dialog.currency = config_sync.get_currency()

        logger.debug("Payment dialog updated with web config")

    except Exception as e:
        logger.error(f"Failed to update payment dialog: {e}")


def clear_payment_config_cache():
    """Clear local payment config cache"""
    try:
        if CACHE_FILE_PATH.exists():
            CACHE_FILE_PATH.unlink()
            logger.info("Payment config cache cleared")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")


def initialize_payment_sync():
    """Initialize payment sync on app startup"""
    try:
        sync = get_payment_config_sync()
        success = sync.sync_config()

        if success:
            config = sync.get_config()
            logger.info(
                f"Payment sync initialized. Provider: {config.provider}, "
                f"Currency: {config.currency}, Test Mode: {config.test_mode}"
            )
        else:
            logger.warning("Failed to initialize payment sync - using defaults")

    except Exception as e:
        logger.error(f"Error initializing payment sync: {e}")


# Example usage
if __name__ == "__main__":
    # Test the sync
    sync = get_payment_config_sync()

    if sync.sync_config(force=True):
        config = sync.get_config()
        print(f"Provider: {config.provider}")
        print(f"Currency: {config.currency}")
        print(f"Test Mode: {config.test_mode}")
        print(f"Credit Packs: {len(config.credit_packs)}")
    else:
        print("Failed to sync config")
