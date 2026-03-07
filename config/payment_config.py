"""
Payment Configuration for Trivox AI Models

Switch between payment providers by changing PAYMENT_PROVIDER variable.
No code changes needed elsewhere!
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum


class PaymentProvider(str, Enum):
    """Available payment providers."""

    GUMROAD = "gumroad"
    LEMONSQUEEZY = "lemonsqueezy"
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    CASHFREE = "cashfree"
    UPI = "upi"  # Manual UPI QR mode


# ═══════════════════════════════════════════════════════════════
# 🔧 SWITCH PAYMENT PROVIDER HERE
# ═══════════════════════════════════════════════════════════════
try:
    from core.payment_config_sync import get_payment_config_sync
    sync = get_payment_config_sync()
    active = sync.get_active_provider()
    # Ensure the returned active provider is cast/mapped to the PaymentProvider enum
    if isinstance(active, str):
        PAYMENT_PROVIDER = PaymentProvider(active.lower())
    else:
        PAYMENT_PROVIDER = active
except Exception:
    PAYMENT_PROVIDER = PaymentProvider.GUMROAD  # Fallback

# Options:
# - PaymentProvider.GUMROAD      # No registration, 10% fee, fastest setup
# - PaymentProvider.LEMONSQUEEZY # No registration, 5% fee
# - PaymentProvider.RAZORPAY     # Indian, 2% fee, requires GST
# - PaymentProvider.STRIPE       # Global, 2-3% fee, requires business
# - PaymentProvider.PAYPAL       # Global, 2.5% fee
# - PaymentProvider.CASHFREE     # Indian, 1.9% fee, requires GST
# - PaymentProvider.UPI          # Manual, 0% fee, no automation
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PaymentSettings:
    """Payment configuration settings."""

    # Provider selection
    provider: PaymentProvider = PAYMENT_PROVIDER

    # Test mode (use sandbox/test credentials)
    test_mode: bool = True

    # Currency
    currency: str = "INR"  # USD for international

    # FREE TRIAL SETTINGS
    # Number of free generations allowed before requiring license
    trial_generations: int = 1  # 1 free generation

    # License key settings
    license_key_length: int = 32
    license_key_prefix: str = "I3D"

    # Webhook settings
    webhook_secret: Optional[str] = None
    webhook_url: Optional[str] = None


@dataclass(frozen=True)
class PricingConfig:
    """Pricing tiers for subscriptions and credits."""

    # Subscription plans - NO FREE PLAN (pay-only)
    plans: Dict[str, Dict] = field(
        default_factory=lambda: {
            "starter": {
                "name": "Starter",
                "price": 499,  # INR per month
                "credits_per_month": 100,
                "features": [
                    "Multi-angle (3 images)",
                    "Standard quality",
                    "Email support",
                ],
            },
            "pro": {
                "name": "Pro",
                "price": 999,  # INR per month
                "credits_per_month": 300,
                "features": [
                    "Multi-angle (5 images)",
                    "High quality",
                    "Priority support",
                    "API access",
                ],
            },
            "enterprise": {
                "name": "Enterprise",
                "price": 4999,  # INR per month
                "credits_per_month": 2000,
                "features": [
                    "Unlimited multi-angle",
                    "Production quality",
                    "Dedicated support",
                    "Custom models",
                ],
            },
        }
    )

    # Pay-per-use credits
    credit_packs: Dict[str, Dict] = field(
        default_factory=lambda: {
            "small": {
                "name": "100 Credits",
                "credits": 100,
                "price": 199,
            },
            "medium": {
                "name": "500 Credits",
                "credits": 500,
                "price": 799,
            },
            "large": {
                "name": "2000 Credits",
                "credits": 2000,
                "price": 2499,
            },
        }
    )

    # Cost per API operation (in credits)
    operation_costs: Dict[str, int] = field(
        default_factory=lambda: {
            "local_processing": 1,
            "hitem3d_api_512": 15,
            "hitem3d_api_1024": 20,
            "hitem3d_api_1536": 50,
            "hitem3d_api_1536pro": 70,
        }
    )


@dataclass(frozen=True)
class GumroadConfig:
    """Gumroad-specific configuration."""

    app_name: str = "Trivox AI Models"
    app_url: str = "https://trivoxaimodels-r5ip.onrender.com"

    # Get these from Gumroad Settings > Advanced > Application
    access_token: Optional[str] = None  # GUMROAD_ACCESS_TOKEN env var

    # Product IDs (create products in Gumroad dashboard)
    product_ids: Dict[str, str] = field(
        default_factory=lambda: {
            "starter_monthly": "xeeeml",  # Fill after creating product
            "pro_monthly": "",
            "enterprise_monthly": "",
            "credits_small": "",
            "credits_medium": "",
            "credits_large": "",
        }
    )


@dataclass(frozen=True)
class RazorpayConfig:
    """
    Razorpay-specific configuration.

    SECURITY NOTICE: API keys are fetched securely via SecretManager which provides
    three-tier security: Environment Variables -> Local Cache -> Remote Supabase RPC.
    This ensures keys cannot be tampered with or exposed in the code.

    To configure:
    1. Set environment variables: RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
    2. OR store in Supabase and fetch via get_app_config RPC (requires valid license)
    """

    # Get from Razorpay Dashboard > Settings > API Keys
    # These are fetched securely via SecretManager, not hardcoded here
    key_id: Optional[str] = field(default_factory=lambda: os.getenv("RAZORPAY_KEY_ID"))
    key_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("RAZORPAY_KEY_SECRET")
    )

    # Webhook secret - used to verify webhook signatures
    webhook_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("RAZORPAY_WEBHOOK_SECRET")
    )

    # Plan IDs (create in Razorpay dashboard)
    plan_ids: Dict[str, str] = field(
        default_factory=lambda: {
            "starter": "plan_xxxxxxxxxxxxx",
            "pro": "plan_xxxxxxxxxxxxx",
            "enterprise": "plan_xxxxxxxxxxxxx",
        }
    )

    @property
    def is_configured(self) -> bool:
        """Check if Razorpay credentials are configured."""
        return bool(self.key_id and self.key_secret)

    @property
    def is_test_mode(self) -> bool:
        """Check if using test keys."""
        return bool(self.key_id and self.key_id.startswith("rzp_test"))


@dataclass(frozen=True)
class StripeConfig:
    """Stripe-specific configuration."""

    # Get from Stripe Dashboard > Developers > API Keys
    publishable_key: Optional[str] = None  # STRIPE_PUBLISHABLE_KEY env var
    secret_key: Optional[str] = None  # STRIPE_SECRET_KEY env var
    webhook_secret: Optional[str] = None  # STRIPE_WEBHOOK_SECRET env var

    # Price IDs (create in Stripe dashboard)
    price_ids: Dict[str, str] = field(
        default_factory=lambda: {
            "starter_monthly": "price_xxxxxxxxxxxxx",
            "pro_monthly": "price_xxxxxxxxxxxxx",
            "enterprise_monthly": "price_xxxxxxxxxxxxx",
        }
    )


@dataclass(frozen=True)
class LemonSqueezyConfig:
    """LemonSqueezy-specific configuration."""

    # Get from LemonSqueezy Settings > API
    api_key: Optional[str] = None  # LEMONSQUEEZY_API_KEY env var
    store_id: Optional[str] = None  # LEMONSQUEEZY_STORE_ID env var

    # Product/Variant IDs
    product_ids: Dict[str, str] = field(
        default_factory=lambda: {
            "starter": "",
            "pro": "",
            "enterprise": "",
        }
    )


@dataclass(frozen=True)
class PayPalConfig:
    """PayPal-specific configuration."""

    # Get from PayPal Developer Dashboard
    client_id: Optional[str] = None  # PAYPAL_CLIENT_ID env var
    client_secret: Optional[str] = None  # PAYPAL_CLIENT_SECRET env var

    # Sandbox or Live
    mode: str = "sandbox"  # Change to "live" for production


@dataclass(frozen=True)
class UPIConfig:
    """UPI Manual QR configuration."""

    # Your UPI ID (e.g., yourname@upi)
    upi_id: Optional[str] = None  # UPI_ID env var

    # QR Code image path (display in app)
    qr_code_path: Optional[str] = None

    # Manual verification settings
    verification_method: str = "manual"  # "manual" or "screenshot_upload"

    # Support contact for payment issues
    support_email: Optional[str] = None
    support_phone: Optional[str] = None


# Global instances
payment_settings = PaymentSettings()
pricing_config = PricingConfig()
gumroad_config = GumroadConfig()
razorpay_config = RazorpayConfig()
stripe_config = StripeConfig()
lemon_squeezy_config = LemonSqueezyConfig()
paypal_config = PayPalConfig()
upi_config = UPIConfig()


__all__ = [
    "PaymentProvider",
    "PAYMENT_PROVIDER",
    "PaymentSettings",
    "PricingConfig",
    "GumroadConfig",
    "RazorpayConfig",
    "StripeConfig",
    "LemonSqueezyConfig",
    "PayPalConfig",
    "UPIConfig",
    "payment_settings",
    "pricing_config",
    "gumroad_config",
    "razorpay_config",
    "stripe_config",
    "lemon_squeezy_config",
    "paypal_config",
    "upi_config",
]
