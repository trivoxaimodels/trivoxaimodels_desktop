"""
Admin Control Panel Manager for ImageTo3D Pro

Manages cloud model configs, user profiles, and usage tracking via Supabase.
"""

import os
import platform
import socket
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from core.supabase_client import get_supabase_client
from core.logger import get_logger

logger = get_logger(__name__)


class AdminModelManager:
    """
    Manages cloud model configuration.
    Admin can enable/disable models that all users see.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    # ── Model Config CRUD ───────────────────────────────────────

    def get_enabled_models(self) -> List[Dict[str, Any]]:
        """Get all enabled cloud models (for regular users)."""
        try:
            result = (
                self.client.table("cloud_model_config")
                .select("*")
                .eq("is_enabled", True)
                .order("display_order")
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch enabled models: {e}")
            return []

    def get_all_models(self) -> List[Dict[str, Any]]:
        """Get all models including disabled (admin only)."""
        try:
            result = (
                self.client.table("cloud_model_config")
                .select("*")
                .order("display_order")
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch all models: {e}")
            return []

    def toggle_model(self, model_id: str, enabled: bool) -> bool:
        """Enable or disable a cloud model (admin only)."""
        try:
            self.client.table("cloud_model_config").update({
                "is_enabled": enabled,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("model_id", model_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to toggle model {model_id}: {e}")
            return False

    def update_model_config(
        self, model_id: str, config: Dict[str, Any]
    ) -> bool:
        """Update per-model configuration (admin only)."""
        try:
            self.client.table("cloud_model_config").update({
                "config_json": json.dumps(config),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("model_id", model_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update model config: {e}")
            return False

    def set_model_order(self, model_id: str, order: int) -> bool:
        """Set display order for a model."""
        try:
            self.client.table("cloud_model_config").update({
                "display_order": order,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("model_id", model_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to set model order: {e}")
            return False

    # ── API Key Management ───────────────────────────────────────

    def get_model_api_keys(self, model_id: str = None) -> List[Dict[str, Any]]:
        """Get API keys and credits for one or all models."""
        try:
            q = self.client.table("model_api_keys").select("*")
            if model_id:
                q = q.eq("model_id", model_id)
            result = q.order("model_id").execute()
            rows = result.data or []
            # Mask key values: show only last 4 chars
            for row in rows:
                val = row.get("key_value", "")
                if val and len(val) > 4:
                    row["key_value_masked"] = "•" * (len(val) - 4) + val[-4:]
                else:
                    row["key_value_masked"] = val
                row["remaining_credits"] = (row.get("total_credits", 0) or 0) - (row.get("used_credits", 0) or 0)
            return rows
        except Exception as e:
            logger.error(f"Failed to get model API keys: {e}")
            return []

    def save_model_api_key(self, model_id: str, key_name: str,
                           key_value: str = None,
                           total_credits: int = None,
                           trial_credits: int = None) -> bool:
        """Create or update an API key entry for a model."""
        try:
            update_data = {"updated_at": datetime.utcnow().isoformat()}
            if key_value is not None:
                update_data["key_value"] = key_value
            if total_credits is not None:
                update_data["total_credits"] = total_credits
            if trial_credits is not None:
                update_data["trial_credits"] = trial_credits

            # Upsert: try update first, insert if not found
            result = (
                self.client.table("model_api_keys")
                .update(update_data)
                .eq("model_id", model_id)
                .eq("key_name", key_name)
                .execute()
            )
            if not result.data:
                # Row doesn't exist yet, insert
                insert_data = {
                    "model_id": model_id,
                    "key_name": key_name,
                    "key_value": key_value or "",
                    "total_credits": total_credits or 0,
                    "trial_credits": trial_credits if trial_credits is not None else 1,
                    "used_credits": 0,
                    "is_active": True,
                }
                self.client.table("model_api_keys").insert(insert_data).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save API key {key_name} for {model_id}: {e}")
            return False

    def get_model_credits(self, model_id: str) -> Dict[str, Any]:
        """Get aggregated credit info for a model (sum across all its keys)."""
        try:
            result = (
                self.client.table("model_api_keys")
                .select("total_credits, used_credits, trial_credits")
                .eq("model_id", model_id)
                .eq("is_active", True)
                .execute()
            )
            rows = result.data or []
            total = sum(r.get("total_credits", 0) or 0 for r in rows)
            used = sum(r.get("used_credits", 0) or 0 for r in rows)
            trial = max((r.get("trial_credits", 0) or 0 for r in rows), default=0)
            return {
                "model_id": model_id,
                "total_credits": total,
                "used_credits": used,
                "remaining_credits": total - used,
                "trial_credits": trial,
            }
        except Exception as e:
            logger.error(f"Failed to get credits for {model_id}: {e}")
            return {"model_id": model_id, "total_credits": 0, "used_credits": 0,
                    "remaining_credits": 0, "trial_credits": 0}

    def use_model_credit(self, model_id: str) -> bool:
        """Consume one credit from a model. Returns False if no credits left."""
        try:
            # Get the primary key row for this model
            result = (
                self.client.table("model_api_keys")
                .select("id, total_credits, used_credits")
                .eq("model_id", model_id)
                .eq("is_active", True)
                .order("created_at")
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                return False
            row = rows[0]
            total = row.get("total_credits", 0) or 0
            used = row.get("used_credits", 0) or 0
            if used >= total and total > 0:
                return False  # No credits remaining

            self.client.table("model_api_keys").update({
                "used_credits": used + 1,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", row["id"]).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to use credit for {model_id}: {e}")
            return False

    # ── Admin Check ─────────────────────────────────────────────

    def is_admin(self, user_id: str = None) -> bool:
        """Check if current user is admin."""
        try:
            result = (
                self.client.table("app_admins")
                .select("id")
                .eq("app_name", "imageto3d_pro")
                .execute()
            )
            return len(result.data or []) > 0
        except Exception:
            return False


class UserTracker:
    """
    Tracks user information and usage for admin analytics.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    # ── User Profile ────────────────────────────────────────────

    def update_user_profile(
        self,
        device_fingerprint: str = "",
        license_key: str = "",
        license_type: str = "free",
        app_version: str = "",
    ) -> bool:
        """Update or create user profile with device info."""
        try:
            profile = {
                "device_fingerprint": device_fingerprint,
                "machine_name": socket.gethostname(),
                "os_version": f"{platform.system()} {platform.version()}",
                "app_version": app_version,
                "timezone": str(datetime.now().astimezone().tzinfo),
                "license_key": license_key,
                "license_type": license_type,
                "last_active_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Upsert: insert if new, update if exists
            self.client.table("user_profiles").upsert(
                profile, on_conflict="user_id"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update user profile: {e}")
            return False

    # ── Usage Logging ───────────────────────────────────────────

    def log_generation(
        self,
        model_id: str,
        generation_type: str,
        status: str = "started",
        input_type: str = "image",
        output_format: str = "glb",
        quality: str = "standard",
        generation_time_ms: int = 0,
        error_message: str = "",
        device_fingerprint: str = "",
        app_version: str = "",
    ) -> Optional[str]:
        """Log a generation event. Returns log entry ID."""
        try:
            result = self.client.table("usage_logs").insert({
                "model_id": model_id,
                "generation_type": generation_type,
                "input_type": input_type,
                "output_format": output_format,
                "quality": quality,
                "status": status,
                "error_message": error_message,
                "generation_time_ms": generation_time_ms,
                "device_fingerprint": device_fingerprint,
                "app_version": app_version,
            }).execute()
            return result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.error(f"Failed to log generation: {e}")
            return None

    def update_generation_status(
        self, log_id: str, status: str,
        generation_time_ms: int = 0, error_message: str = "",
    ) -> bool:
        """Update a generation log entry status."""
        try:
            update = {"status": status}
            if generation_time_ms:
                update["generation_time_ms"] = generation_time_ms
            if error_message:
                update["error_message"] = error_message

            self.client.table("usage_logs").update(update).eq(
                "id", log_id
            ).execute()

            # Increment user's generation count
            if status == "success":
                self.client.rpc("increment_user_generations", {}).execute()

            return True
        except Exception as e:
            logger.error(f"Failed to update generation status: {e}")
            return False

    # ── Admin Analytics ─────────────────────────────────────────

    def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin dashboard statistics."""
        try:
            result = self.client.rpc("get_admin_stats", {}).execute()
            return result.data or {}
        except Exception as e:
            logger.error(f"Failed to get admin stats: {e}")
            return {}

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all user profiles (admin only)."""
        try:
            result = (
                self.client.table("user_profiles")
                .select("*")
                .order("last_active_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch users: {e}")
            return []

    def get_user_usage(self, user_id: str) -> List[Dict[str, Any]]:
        """Get usage logs for a specific user (admin only)."""
        try:
            result = (
                self.client.table("usage_logs")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(100)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch user usage: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════
# SALES TRACKER — Gumroad Sales Data (Admin Analytics)
# ═══════════════════════════════════════════════════════════════════════

class SalesTracker:
    """
    Tracks Gumroad sales data stored in Supabase.
    Provides admin dashboard views for revenue, sales, and license management.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not self._client:
            self._client = get_supabase_client()
        return self._client

    # Get all sales (paginated, filterable by status and email).
    def get_all_sales(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str = None,
        email: str = None,
    ) -> List[Dict]:
        """Fetch all Gumroad sales from Supabase with optional filters."""
        try:
            result = self.client.rpc("get_all_sales", {
                "p_limit": limit,
                "p_offset": offset,
                "p_status": status,
                "p_email": email,
            }).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to fetch sales: {e}")
            return []

    # Get aggregated sales statistics (revenue, counts, refunds).
    def get_sales_stats(self) -> Dict[str, Any]:
        """Get summary statistics: total revenue, sales count, refund rate, etc."""
        try:
            result = self.client.rpc("get_sales_stats").execute()
            return result.data if result.data else {}
        except Exception as e:
            logger.error(f"Failed to fetch sales stats: {e}")
            return {}

    # Get detail for a single sale by its Gumroad sale_id.
    def get_sale_detail(self, sale_id: str) -> Optional[Dict]:
        """Get full details of a specific sale including raw Gumroad payload."""
        try:
            result = (
                self.client.table("gumroad_sales")
                .select("*")
                .eq("sale_id", sale_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch sale detail: {e}")
            return None

    # Search sales by email or license key.
    def search_sales(
        self, email: str = None, license_key: str = None
    ) -> List[Dict]:
        """Search sales by buyer email or license key."""
        try:
            query = self.client.table("gumroad_sales").select(
                "id, sale_id, product_name, plan_id, license_key, "
                "buyer_email, buyer_name, price, currency, status, "
                "credits_granted, created_at"
            )
            if email:
                query = query.ilike("buyer_email", f"%{email}%")
            if license_key:
                query = query.eq("license_key", license_key)
            result = query.order("created_at", desc=True).limit(50).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to search sales: {e}")
            return []

    # Revoke / deactivate a license (admin action).
    def revoke_license(self, license_key: str, reason: str = "Admin revoked") -> bool:
        """Deactivate a license and mark the associated sale as revoked."""
        try:
            # Deactivate in licenses table
            self.client.table("licenses").update(
                {"status": "revoked"}
            ).eq("license_key", license_key).execute()

            # Mark in gumroad_sales
            self.client.table("gumroad_sales").update(
                {"status": "revoked", "updated_at": datetime.utcnow().isoformat()}
            ).eq("license_key", license_key).execute()

            logger.info(f"License {license_key} revoked: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke license {license_key}: {e}")
            return False

    # Reactivate a previously revoked license (admin action).
    def reactivate_license(self, license_key: str) -> bool:
        """Reactivate a revoked license."""
        try:
            self.client.table("licenses").update(
                {"status": "active"}
            ).eq("license_key", license_key).execute()

            self.client.table("gumroad_sales").update(
                {"status": "active", "updated_at": datetime.utcnow().isoformat()}
            ).eq("license_key", license_key).execute()

            logger.info(f"License {license_key} reactivated")
            return True
        except Exception as e:
            logger.error(f"Failed to reactivate license {license_key}: {e}")
            return False

    # ── Razorpay Sales ──────────────────────────────────────────

    def get_razorpay_sales(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        email: Optional[str] = None,
    ) -> List[Dict]:
        """Fetch all Razorpay sales from Supabase."""
        try:
            query = self.client.table("razorpay_sales").select("*")
            if status:
                query = query.eq("status", status)
            if email:
                query = query.ilike("buyer_email", f"%{email}%")
            result = query.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch Razorpay sales: {e}")
            return []

    def get_razorpay_sale_detail(self, payment_id: str) -> Optional[Dict]:
        """Get full details of a specific Razorpay sale."""
        try:
            result = (
                self.client.table("razorpay_sales")
                .select("*")
                .eq("payment_id", payment_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch Razorpay sale detail: {e}")
            return None

    # ── Storage Tracking ────────────────────────────────────────

    def get_storage_failed_models(self, limit: int = 100) -> List[Dict]:
        """
        Get all models that failed to save to database.
        """
        try:
            result = (
                self.client.table("user_generations")
                .select("*")
                .eq("storage_status", "failed")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get storage failed models: {e}")
            return []

    def get_model_storage_status(self, generation_id: str) -> Optional[Dict]:
        """
        Get storage status for a specific generation.
        """
        try:
            result = (
                self.client.table("user_generations")
                .select("*")
                .eq("id", generation_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get model storage status: {e}")
            return None

    # ── Admin Overview Stats ────────────────────────────────────

    def get_admin_overview_stats(self) -> Dict[str, Any]:
        """
        Get admin overview statistics including:
        - Total users
        - Total generations
        - Generations per user
        - Storage usage estimate
        """
        try:
            # Total users
            users_result = self.client.table("web_users").select("id", count="exact").execute()
            total_users = users_result.count if hasattr(users_result, 'count') else len(users_result.data or [])

            # Total generations
            gens_result = self.client.table("user_generations").select("id", count="exact").execute()
            total_gens = gens_result.count if hasattr(gens_result, 'count') else len(gens_result.data or [])

            # Recent activity (last 7 days)
            from datetime import timedelta
            week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            recent_result = (
                self.client.table("user_generations")
                .select("id", count="exact")
                .gte("created_at", week_ago)
                .execute()
            )
            recent_gens = recent_result.count if hasattr(recent_result, 'count') else len(recent_result.data or [])

            return {
                "total_users": total_users,
                "total_generations": total_gens,
                "recent_generations": recent_gens,
                "avg_gens_per_user": round(total_gens / max(total_users, 1), 1),
            }
        except Exception as e:
            logger.error(f"Failed to get admin overview stats: {e}")
            return {}

    def get_all_user_generations(self, user_id: str) -> List[Dict]:
        """
        Get all generations for a specific user.
        """
        try:
            result = (
                self.client.table("user_generations")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get user generations: {e}")
            return []

    def get_user_summary(self) -> List[Dict]:
        """
        Get summary of all users with their generation counts.
        """
        try:
            # Get all users with credit info
            users = (
                self.client.table("web_users")
                .select("id, username, email, created_at, trial_used, trial_remaining")
                .order("created_at", desc=True)
                .execute()
            )
            if not users.data:
                return []

            result = []
            for user in users.data:
                # Get credit balance
                credits = (
                    self.client.table("user_credits")
                    .select("credits_balance, total_purchased, total_used")
                    .eq("user_id", user["id"])
                    .execute()
                )
                credit_info = credits.data[0] if credits.data else {}

                # Get generation count
                gens = (
                    self.client.table("user_generations")
                    .select("id", count="exact")
                    .eq("user_id", user["id"])
                    .execute()
                )
                gen_count = gens.count if hasattr(gens, 'count') else len(gens.data or [])

                result.append({
                    **user,
                    "credits_balance": credit_info.get("credits_balance", 0),
                    "total_purchased": credit_info.get("total_purchased", 0),
                    "total_used": credit_info.get("total_used", 0),
                    "generation_count": gen_count,
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get user summary: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════
# PAYMENT GATEWAY MANAGER
# ═══════════════════════════════════════════════════════════════════════

class PaymentGatewayManager:
    """
    Manages payment gateway options (Gumroad, Razorpay, etc.).
    Admin can enable/disable gateways via Supabase.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def get_gateways(self) -> List[Dict[str, Any]]:
        """Get all payment gateways and their status."""
        try:
            result = self.client.table("payment_gateways").select("*").execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get payment gateways: {e}")
            return []

    def toggle_gateway(self, gateway_name: str, enabled: bool) -> bool:
        """Enable or disable a payment gateway (admin only)."""
        try:
            self.client.table("payment_gateways").update({
                "is_enabled": enabled,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("gateway_name", gateway_name).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to toggle gateway {gateway_name}: {e}")
            return False

    def get_active_gateway(self) -> Optional[str]:
        """Get the name of currently active payment gateway."""
        try:
            result = (
                self.client.table("payment_gateways")
                .select("gateway_name")
                .eq("is_enabled", True)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]["gateway_name"]
            return None
        except Exception as e:
            logger.error(f"Failed to get active gateway: {e}")
            return None

