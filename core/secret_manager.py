import os
import json
from typing import Optional, Dict
from core.supabase_client import get_supabase
from core.license_manager import get_license_manager
from core.logger import get_logger

logger = get_logger(__name__)


class SecretManager:
    """
    Securely fetches API keys and secrets from multiple sources.

    Priority order:
    1. Environment variables (for development)
    2. Local cache (for performance)
    3. Web API (for payment config from unified admin)
    4. Supabase RPC (for other app config)

    Requires a valid license to access remote sources.
    """

    _secrets_cache: Dict[str, str] = {}

    @classmethod
    def get_secret(cls, key_name: str, use_cache: bool = True) -> Optional[str]:
        """
        Get a secret value with multi-tier fallback.
        """
        # 1. Check local environment (for development)
        if os.environ.get(key_name):
            return os.environ.get(key_name)

        # 2. Check cache
        if use_cache and key_name in cls._secrets_cache:
            return cls._secrets_cache[key_name]

        # 3. Try Web API for payment keys (unified admin system)
        if cls._is_payment_key(key_name):
            try:
                val = cls._fetch_from_web_api(key_name)
                if val:
                    cls._secrets_cache[key_name] = val
                    return val
            except Exception as e:
                logger.debug(f"Web API fetch failed for {key_name}: {e}")

        # SECURITY FIX: Direct fetching of AI model keys from Supabase is disabled.
        # All AI model generation should happen via the web proxy to prevent key exposure.
        # _fetch_remote_secret is removed.

        return None

    @classmethod
    def _is_payment_key(cls, key_name: str) -> bool:
        """Check if key is a payment provider key"""
        payment_prefixes = [
            "RAZORPAY_",
            "STRIPE_",
            "PAYPAL_",
            "GUMROAD_",
            "LEMONSQUEEZY_",
            "CASHFREE_",
        ]
        return any(key_name.startswith(prefix) for prefix in payment_prefixes)

    @classmethod
    def _fetch_from_web_api(cls, key_name: str) -> Optional[str]:
        """
        Fetch payment keys from web API (unified admin system).
        """
        try:
            from core.payment_config_sync import get_secure_key_manager

            # Determine provider from key name
            if key_name.startswith("RAZORPAY_"):
                provider = "razorpay"
            elif key_name.startswith("STRIPE_"):
                provider = "stripe"
            elif key_name.startswith("PAYPAL_"):
                provider = "paypal"
            elif key_name.startswith("GUMROAD_"):
                provider = "gumroad"
            else:
                return None

            # Get secure key manager
            key_mgr = get_secure_key_manager()
            keys = key_mgr.get_api_keys(provider)

            if not keys:
                return None

            # Map key name to field
            key_mapping = {
                "RAZORPAY_KEY_ID": "key_id",
                "RAZORPAY_KEY_SECRET": "key_secret",
                "RAZORPAY_WEBHOOK_SECRET": "webhook_secret",
                "STRIPE_PUBLISHABLE_KEY": "key_id",
                "STRIPE_SECRET_KEY": "key_secret",
                "STRIPE_WEBHOOK_SECRET": "webhook_secret",
                "PAYPAL_CLIENT_ID": "key_id",
                "PAYPAL_CLIENT_SECRET": "key_secret",
                "GUMROAD_ACCESS_TOKEN": "key_id",
            }

            field = key_mapping.get(key_name)
            if field:
                return keys.get(field)

            return None

        except Exception as e:
            logger.debug(f"Web API fetch error: {e}")
            return None


# Helper
def get_secret(key: str) -> Optional[str]:
    return SecretManager.get_secret(key)
