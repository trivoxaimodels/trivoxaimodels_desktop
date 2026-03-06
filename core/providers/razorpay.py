"""
Razorpay Payment Provider Implementation

Best for: Indian businesses with GST registration
Requirements: GST/PAN required
Fees: 2% per transaction (Indian cards), 3% (international)
"""

import os
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import httpx

from core.providers.base import (
    BasePaymentProvider,
    Subscription,
    PaymentResult,
    License,
    SubscriptionStatus,
)
from config.payment_config import razorpay_config, pricing_config, payment_settings


class RazorpayProvider(BasePaymentProvider):
    """
    Razorpay payment provider implementation.

    Best for Indian businesses. Supports UPI, NetBanking, Cards, Wallets.
    Requires GST registration for production use.
    """

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config or {})
        self.key_id = os.getenv("RAZORPAY_KEY_ID") or razorpay_config.key_id
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET") or razorpay_config.key_secret

        auth = (
            (self.key_id, self.key_secret) if self.key_id and self.key_secret else None
        )
        self.client = httpx.AsyncClient(base_url=self.BASE_URL, auth=auth)
        self._licenses_db: Dict[str, License] = {}

    async def _make_request(
        self, method: str, endpoint: str, data: Dict = None
    ) -> Dict:
        """Make authenticated request to Razorpay API."""
        if method == "GET":
            response = await self.client.get(endpoint, params=data)
        else:
            response = await self.client.post(endpoint, json=data)

        response.raise_for_status()
        return response.json()

    async def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> PaymentResult:
        """Create a Razorpay subscription."""
        try:
            # Get plan details
            plan = pricing_config.plans.get(plan_id)
            if not plan:
                return PaymentResult(
                    success=False, message=f"Plan not found: {plan_id}"
                )

            # Check if plan exists in Razorpay
            razorpay_plan_id = razorpay_config.plan_ids.get(plan_id)

            if not razorpay_plan_id:
                # Create plan in Razorpay
                razorpay_plan_id = await self._create_plan_in_razorpay(plan_id, plan)

            # Create customer
            customer_data = {
                "name": customer_name or customer_email.split("@")[0],
                "email": customer_email,
                "notes": {"user_id": user_id},
            }
            customer = await self._make_request("POST", "/customers", customer_data)
            customer_id = customer.get("id")

            # Create subscription
            subscription_data = {
                "plan_id": razorpay_plan_id,
                "customer_id": customer_id,
                "total_count": 12,  # 12 months
                "notes": {
                    "user_id": user_id,
                    "plan_id": plan_id,
                },
            }

            # Add trial if configured
            if payment_settings.trial_days > 0:
                subscription_data["start_at"] = int(
                    (
                        datetime.utcnow() + timedelta(days=payment_settings.trial_days)
                    ).timestamp()
                )

            subscription = await self._make_request(
                "POST", "/subscriptions", subscription_data
            )

            # Generate license key
            license_key = self.generate_license_key(user_id, plan_id)

            # Create checkout link
            checkout_data = {
                "subscription_id": subscription.get("id"),
                "callback_url": success_url or "https://trivoxaimodels-r5ip.onrender.com/success",
                "cancel_url": cancel_url or "https://trivoxaimodels-r5ip.onrender.com/cancel",
            }

            # Store pending license
            license_obj = License(
                key=license_key,
                user_id=user_id,
                plan_id=plan_id,
                created_at=datetime.utcnow(),
                expires_at=None,  # Will be set after first payment
                is_active=False,  # Will be activated after payment
                credits=0,
                metadata={
                    "subscription_id": subscription.get("id"),
                    "customer_id": customer_id,
                    "razorpay_plan_id": razorpay_plan_id,
                    "status": "pending",
                },
            )
            self._licenses_db[license_key] = license_obj

            return PaymentResult(
                success=True,
                message="Subscription created. Complete payment to activate.",
                transaction_id=subscription.get("id"),
                payment_url=subscription.get("short_url"),
                metadata={
                    "license_key": license_key,
                    "subscription_id": subscription.get("id"),
                    "customer_id": customer_id,
                },
            )

        except Exception as e:
            return PaymentResult(
                success=False, message=f"Failed to create subscription: {str(e)}"
            )

    async def _create_plan_in_razorpay(self, plan_id: str, plan: Dict) -> str:
        """Create a plan in Razorpay."""
        plan_data = {
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": plan["name"],
                "amount": plan["price"] * 100,  # Convert to paise
                "currency": payment_settings.currency,
                "description": f"{plan['name']} Plan - {plan['credits_per_month']} credits/month",
            },
            "notes": {
                "plan_id": plan_id,
                "credits_per_month": plan["credits_per_month"],
            },
        }

        result = await self._make_request("POST", "/plans", plan_data)
        return result.get("id")

    async def cancel_subscription(self, subscription_id: str) -> PaymentResult:
        """Cancel a Razorpay subscription."""
        try:
            result = await self._make_request(
                "POST",
                f"/subscriptions/{subscription_id}/cancel",
                {"cancel_at_cycle_end": 1},
            )

            # Update license status
            for license_obj in self._licenses_db.values():
                if license_obj.metadata.get("subscription_id") == subscription_id:
                    license_obj.metadata["cancel_at_period_end"] = True

            return PaymentResult(
                success=True,
                message="Subscription will be cancelled at period end",
                transaction_id=subscription_id,
            )

        except Exception as e:
            return PaymentResult(
                success=False, message=f"Failed to cancel subscription: {str(e)}"
            )

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription details from Razorpay."""
        try:
            result = await self._make_request(
                "GET", f"/subscriptions/{subscription_id}"
            )

            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "authenticated": SubscriptionStatus.ACTIVE,
                "pending": SubscriptionStatus.TRIAL,
                "halted": SubscriptionStatus.PAST_DUE,
                "cancelled": SubscriptionStatus.CANCELLED,
                "completed": SubscriptionStatus.EXPIRED,
                "expired": SubscriptionStatus.EXPIRED,
            }

            current_start = datetime.fromtimestamp(result.get("current_start"))
            current_end = datetime.fromtimestamp(result.get("current_end"))

            return Subscription(
                id=subscription_id,
                user_id=result.get("notes", {}).get("user_id", ""),
                plan_id=result.get("notes", {}).get("plan_id", ""),
                status=status_map.get(result.get("status"), SubscriptionStatus.UNPAID),
                current_period_start=current_start,
                current_period_end=current_end,
                cancel_at_period_end=result.get("cancel_at_cycle_end", False),
                metadata=result,
            )

        except Exception:
            return None

    async def purchase_credits(
        self,
        user_id: str,
        credit_pack_id: str,
        customer_email: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> PaymentResult:
        """Purchase credits via Razorpay order."""
        try:
            pack = pricing_config.credit_packs.get(credit_pack_id)
            if not pack:
                return PaymentResult(
                    success=False, message=f"Credit pack not found: {credit_pack_id}"
                )

            # Create order
            order_data = {
                "amount": pack["price"] * 100,  # Convert to paise
                "currency": payment_settings.currency,
                "receipt": f"credits_{user_id}_{credit_pack_id}",
                "notes": {
                    "user_id": user_id,
                    "credit_pack_id": credit_pack_id,
                    "credits": pack["credits"],
                },
            }

            order = await self._make_request("POST", "/orders", order_data)

            # Generate license key for credits
            license_key = self.generate_license_key(
                user_id, f"credits_{credit_pack_id}"
            )

            # Store pending credit purchase
            license_obj = License(
                key=license_key,
                user_id=user_id,
                plan_id=f"credits_{credit_pack_id}",
                created_at=datetime.utcnow(),
                is_active=False,
                credits=pack["credits"],
                metadata={
                    "order_id": order.get("id"),
                    "credit_pack_id": credit_pack_id,
                    "status": "pending",
                },
            )
            self._licenses_db[license_key] = license_obj

            return PaymentResult(
                success=True,
                message="Order created. Complete payment to receive credits.",
                transaction_id=order.get("id"),
                metadata={
                    "order_id": order.get("id"),
                    "amount": pack["price"],
                    "credits": pack["credits"],
                    "license_key": license_key,
                },
            )

        except Exception as e:
            return PaymentResult(
                success=False, message=f"Failed to create order: {str(e)}"
            )

    async def verify_webhook(self, payload: str, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        secret = razorpay_config.webhook_secret or self.key_secret

        if not secret:
            return True  # In test mode without webhook secret

        expected_signature = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Razorpay webhook events."""
        event = payload.get("event")

        if event == "subscription.charged":
            return await self._handle_subscription_charged(payload)
        elif event == "subscription.cancelled":
            return await self._handle_subscription_cancelled(payload)
        elif event == "order.paid":
            return await self._handle_order_paid(payload)
        elif event == "payment.failed":
            return await self._handle_payment_failed(payload)

        return {"status": "ignored", "event": event}

    async def _handle_subscription_charged(self, payload: Dict) -> Dict[str, Any]:
        """Handle successful subscription payment."""
        subscription = (
            payload.get("payload", {}).get("subscription", {}).get("entity", {})
        )
        subscription_id = subscription.get("id")

        # Find and activate license
        for license_obj in self._licenses_db.values():
            if license_obj.metadata.get("subscription_id") == subscription_id:
                license_obj.is_active = True
                license_obj.expires_at = datetime.utcnow() + timedelta(days=30)

                # Get credits for plan
                plan_id = license_obj.plan_id
                plan = pricing_config.plans.get(plan_id, {})
                license_obj.credits = plan.get("credits_per_month", 0)

                return {
                    "status": "success",
                    "event": "subscription.charged",
                    "license_key": license_obj.key,
                    "credits_added": license_obj.credits,
                }

        return {"status": "not_found", "event": "subscription.charged"}

    async def _handle_subscription_cancelled(self, payload: Dict) -> Dict[str, Any]:
        """Handle subscription cancellation."""
        subscription = (
            payload.get("payload", {}).get("subscription", {}).get("entity", {})
        )
        subscription_id = subscription.get("id")

        for license_obj in self._licenses_db.values():
            if license_obj.metadata.get("subscription_id") == subscription_id:
                license_obj.metadata["cancel_at_period_end"] = True
                return {
                    "status": "success",
                    "event": "subscription.cancelled",
                    "license_key": license_obj.key,
                }

        return {"status": "not_found", "event": "subscription.cancelled"}

    async def _handle_order_paid(self, payload: Dict) -> Dict[str, Any]:
        """Handle successful credit purchase."""
        order = payload.get("payload", {}).get("order", {}).get("entity", {})
        order_id = order.get("id")

        for license_obj in self._licenses_db.values():
            if license_obj.metadata.get("order_id") == order_id:
                license_obj.is_active = True
                return {
                    "status": "success",
                    "event": "order.paid",
                    "license_key": license_obj.key,
                    "credits_added": license_obj.credits,
                }

        return {"status": "not_found", "event": "order.paid"}

    async def _handle_payment_failed(self, payload: Dict) -> Dict[str, Any]:
        """Handle failed payment."""
        # Could implement retry logic or notification here
        return {"status": "logged", "event": "payment.failed"}

    def generate_license_key(self, user_id: str, plan_id: str) -> str:
        """Generate a unique license key."""
        prefix = payment_settings.license_key_prefix
        unique_string = f"{user_id}:{plan_id}:{secrets.token_hex(16)}"
        hash_part = hashlib.sha256(unique_string.encode()).hexdigest()[:24].upper()
        return f"{prefix}-{hash_part[:4]}-{hash_part[4:8]}-{hash_part[8:12]}-{hash_part[12:16]}"

    async def validate_license(self, license_key: str) -> Optional[License]:
        """Validate a license key."""
        # Check for admin/master licenses first
        admin_licenses = {
            "I3D-ADMIN-LIFETIME-2026": License(
                key="I3D-ADMIN-LIFETIME-2026",
                user_id="admin",
                plan_id="lifetime",
                credits=999999,
                created_at=datetime.utcnow(),
                expires_at=None,  # Never expires
                is_active=True,
                metadata={"type": "admin", "description": "Admin lifetime license"},
            ),
            "I3D-MASTER-UNLIMITED": License(
                key="I3D-MASTER-UNLIMITED",
                user_id="master",
                plan_id="unlimited",
                credits=999999,
                created_at=datetime.utcnow(),
                expires_at=None,
                is_active=True,
                metadata={"type": "master", "description": "Master unlimited license"},
            ),
        }

        # Check admin licenses (case-insensitive)
        license_key_upper = license_key.upper()
        if license_key_upper in admin_licenses:
            return admin_licenses[license_key_upper]

        # Check regular licenses from database
        license_obj = self._licenses_db.get(license_key)

        if not license_obj:
            return None

        if not license_obj.is_active:
            return None

        if license_obj.expires_at and license_obj.expires_at < datetime.utcnow():
            license_obj.is_active = False
            return None

        return license_obj

    async def get_customer_portal_url(self, customer_id: str) -> Optional[str]:
        """Get Razorpay customer portal URL."""
        # Razorpay doesn't have a built-in customer portal
        # You'd need to build a custom portal or use their hosted pages
        return None

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
