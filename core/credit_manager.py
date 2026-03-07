"""
Credit Manager — Automated Credit System for Trivox AI Models

Handles:
- User registration with trial credits
- Credit balance checking
- Credit deduction on generation
- Credit addition on purchase (from any payment platform)
- Full audit trail in credit_ledger
- Master API key retrieval (never exposed to users)

All operations use Supabase tables:
- web_users, user_credits, credit_ledger, payment_transactions, user_generations
"""

import os
import hashlib
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from core.supabase_client import get_supabase
from core.logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# Credit costs per operation (matches payment_config.py)
# ═══════════════════════════════════════════════════════════════
CREDIT_COSTS = {
    "local": 0,  # Local processing is FREE
    "512": 15,
    "1024": 20,
    "1536": 50,
    "1536pro": 70,
}

# Credit packs (plan_id -> credits)
# gumroad_id: the Gumroad product permalink (the short code after gumroad.com/l/)
# ⚠️  Create each product on Gumroad and paste its permalink here.
CREDIT_PACKS = {
    "credits_micro": {
        "credits": 40, "price": 99, "name": "Micro Pack (40 Credits)",
        "gumroad_id": "sijpb", "razorpay_id": "pl_PzGv7X6z3X6z3X",
    },
    "credits_small": {
        "credits": 100, "price": 199, "name": "Small Pack (100 Credits)",
        "gumroad_id": "ershej", "razorpay_id": "pl_PzGv7X6z3X6z3y",
    },
    "credits_medium": {
        "credits": 500, "price": 799, "name": "Medium Pack (500 Credits)",
        "gumroad_id": "kaiasd", "razorpay_id": "pl_PzGv7X6z3X6z3z",
    },
    "credits_large": {
        "credits": 2000, "price": 2499, "name": "Large Pack (2000 Credits)",
        "gumroad_id": "ruhge", "razorpay_id": "pl_PzGv7X6z3X6z40",
    },
    # Subscription monthly credit grants
    "starter_monthly": {
        "credits": 100, "price": 499, "name": "Starter Plan (100 Credits/mo)",
        "gumroad_id": "xeeeml", "razorpay_id": "plan_starter",
    },
    "pro_monthly": {
        "credits": 300, "price": 999, "name": "Pro Plan (300 Credits/mo)",
        "gumroad_id": "", "razorpay_id": "plan_pro",
    },
    "enterprise_monthly": {
        "credits": 2000, "price": 4999, "name": "Enterprise Plan (2000 Credits/mo)",
        "gumroad_id": "", "razorpay_id": "plan_enterprise",
    },
}

# ═══════════════════════════════════════════════════════════════
def add_credits(
    user_id: str,
    amount: int,
    source: str = "system",
    description: str = "Credits added",
    reference_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add credits to a user's account.

    This function is used by payment handlers to increment a user's credit balance.
    It updates the user_credits table and creates a ledger entry for audit purposes.

    Args:
        user_id: The user ID to add credits to.
        amount: The number of credits to add (must be positive).
        source: The source of the credit addition (e.g., "razorpay_purchase").
        description: A short description of why credits are being added.
        reference_id: Optional transaction or payment reference ID.

    Returns:
        Dict with success flag, credits added, and new balance.
    """
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    try:
        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}

        # Get or create user credit record
        credits_data = (
            sb.table("user_credits").select("*").eq("user_id", user_id).execute()
        )
        if credits_data.data:
            current = credits_data.data[0]
            new_balance = current["credits_balance"] + amount
            sb.table("user_credits").update(
                {
                    "credits_balance": new_balance,
                    "total_purchased": current["total_purchased"] + amount,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("user_id", user_id).execute()
        else:
            new_balance = amount
            sb.table("user_credits").insert(
                {
                    "user_id": user_id,
                    "credits_balance": new_balance,
                    "total_purchased": amount,
                    "total_used": 0,
                }
            ).execute()

        # Log the credit addition in the ledger
        sb.table("credit_ledger").insert(
            {
                "user_id": user_id,
                "amount": amount,
                "type": "credit_addition",
                "description": description,
                "reference_id": reference_id,
                "balance_after": new_balance,
            }
        ).execute()

        return {"success": True, "credits_added": amount, "new_balance": new_balance}

    except Exception as e:
        logger.error(f"Failed to add credits for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


DEFAULT_TRIAL_CREDITS = 1  # 1 free generation for new users


def _hash_password(password: str) -> str:
    """Hash password with SHA256 + salt."""
    salt = "imageto3d_pro_salt_2026"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════
# USER REGISTRATION
# ═══════════════════════════════════════════════════════════════

def register_user(username: str, password: str, email: Optional[str] = None, ip_address: Optional[str] = None, device_fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """
    Register a new web user with trial credits.
    Returns {"success": bool, "user_id": str, "error": str, "device_blocked": bool}
    """
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available", "device_blocked": False}

    try:
        # Check if username exists
        existing = sb.table("web_users").select("id").eq("username", username).execute()
        if existing.data:
            return {"success": False, "error": "Username already exists", "device_blocked": False}

        # Check if device fingerprint has already been used for a trial
        if device_fingerprint:
            device_check = sb.table("device_trials").select("id").eq("device_fingerprint", device_fingerprint).execute()
            if device_check.data:
                # Device has already used a trial - create user but with NO trial credits
                user_data = {
                    "username": username,
                    "password_hash": _hash_password(password),
                    "email": email,
                    "ip_address": ip_address,
                    "device_fingerprint": device_fingerprint,
                    "trial_remaining": 0,  # NO trial for this device
                    "trial_used": 0,
                }
                result = sb.table("web_users").insert(user_data).execute()
                if not result.data:
                    return {"success": False, "error": "Failed to create user", "device_blocked": False}

                user_id = result.data[0]["id"]

                # Initialize credit balance (0 credits)
                sb.table("user_credits").insert({
                    "user_id": user_id,
                    "credits_balance": 0,
                    "total_purchased": 0,
                    "total_used": 0,
                }).execute()

                return {
                    "success": True, 
                    "user_id": user_id, 
                    "device_blocked": True,
                    "message": "This device has already used a free trial. Please purchase credits to continue."
                }

        # Create user with trial (device not seen before or no fingerprint)
        user_data = {
            "username": username,
            "password_hash": _hash_password(password),
            "email": email,
            "ip_address": ip_address,
            "device_fingerprint": device_fingerprint,
            "trial_remaining": DEFAULT_TRIAL_CREDITS,
            "trial_used": 0,
        }
        result = sb.table("web_users").insert(user_data).execute()
        if not result.data:
            return {"success": False, "error": "Failed to create user", "device_blocked": False}

        user_id = result.data[0]["id"]

        # Record device fingerprint as having used trial
        if device_fingerprint:
            sb.table("device_trials").insert({
                "device_fingerprint": device_fingerprint,
                "ip_address": ip_address,
                "user_id": user_id,
                "username": username,
            }).execute()

        # Initialize credit balance
        sb.table("user_credits").insert({
            "user_id": user_id,
            "credits_balance": 0,
            "total_purchased": 0,
            "total_used": 0,
        }).execute()

        # Log trial grant in ledger
        sb.table("credit_ledger").insert({
            "user_id": user_id,
            "amount": 0,
            "type": "trial",
            "description": f"Account created with {DEFAULT_TRIAL_CREDITS} free trial generation(s)",
            "balance_after": 0,
        }).execute()

        return {"success": True, "user_id": user_id, "device_blocked": False}

    except Exception as e:
        return {"success": False, "error": str(e), "device_blocked": False}


def verify_user_login(username: str, password: str) -> Dict[str, Any]:
    """
    Verify user credentials.
    Returns {"success": bool, "user_id": str, "is_admin": bool, "error": str}
    """
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    try:
        result = sb.table("web_users").select("*").eq("username", username).execute()
        if not result.data:
            return {"success": False, "error": "Invalid credentials"}

        user = result.data[0]
        if user["password_hash"] != _hash_password(password):
            return {"success": False, "error": "Invalid credentials"}

        return {
            "success": True,
            "user_id": user["id"],
            "username": user["username"],
            "is_admin": user.get("is_admin", False),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# CREDIT BALANCE & CHECKING
# ═══════════════════════════════════════════════════════════════

def get_user_balance(user_id: str, device_fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """
    Get user's full credit status.
    Returns trial info + credit balance + cost preview.
    """
    sb = get_supabase()
    if not sb:
        return {"error": "Database not available"}

    try:
        # Get user trial info
        user = sb.table("web_users").select("trial_remaining, trial_used").eq("id", user_id).execute()
        trial_remaining = user.data[0]["trial_remaining"] if user.data else 0
        trial_used = user.data[0]["trial_used"] if user.data else 0

        # ALSO check device trial if fingerprint provided
        if device_fingerprint:
            # Check registered_devices table (desktop)
            try:
                device = sb.table("registered_devices").select("trial_used").eq("device_fingerprint", device_fingerprint).execute()
                if device.data and device.data[0].get("trial_used", 0) > 0:
                    trial_used = max(trial_used, 1)
            except Exception:
                pass
            
            # Check device_trials table (web)
            try:
                device_check = sb.table("device_trials").select("id").eq("device_fingerprint", device_fingerprint).execute()
                if device_check.data:
                    trial_used = max(trial_used, 1)
            except Exception:
                pass

        # Get credit balance
        credits = sb.table("user_credits").select("*").eq("user_id", user_id).execute()
        balance = credits.data[0]["credits_balance"] if credits.data else 0
        total_purchased = credits.data[0]["total_purchased"] if credits.data else 0
        total_used = credits.data[0]["total_used"] if credits.data else 0

        return {
            "user_id": user_id,
            "trial_remaining": trial_remaining,
            "trial_used": trial_used,
            "credits_balance": balance,
            "total_purchased": total_purchased,
            "total_used": total_used,
            "costs": CREDIT_COSTS,
        }

    except Exception as e:
        return {"error": str(e)}


def can_generate(
    user_id: str,
    resolution: str = "1024",
    is_trial: bool = False,
    device_fingerprint: Optional[str] = None,
) -> Tuple[bool, str, int]:
    """
    Check if user can generate at the given resolution.
    Returns (can_generate, reason, credits_to_deduct).

    For trial (first generation): Uses cloud API highest resolution, but FREE.
    For subsequent: Deducts from user's credit balance.
    """
    sb = get_supabase()
    if not sb:
        return False, "Database not available", 0

    try:
        import uuid
        try:
            uuid.UUID(str(user_id))
        except ValueError:
            return True, "local_bypass", 0

        # Get user info including trial_used
        user = (
            sb.table("web_users")
            .select("trial_used, trial_remaining")
            .eq("id", user_id)
            .execute()
        )
        trial_used = user.data[0].get("trial_used", 0) if user.data else 0
        trial_remaining = user.data[0].get("trial_remaining", 0) if user.data else 0

        # ALSO check device trial if fingerprint provided
        if device_fingerprint:
            try:
                device = (
                    sb.table("registered_devices")
                    .select("trial_used")
                    .eq("device_fingerprint", device_fingerprint)
                    .execute()
                )
                if device.data and device.data[0].get("trial_used", 0) > 0:
                    trial_used = max(trial_used, 1)
            except Exception:
                pass

            # Also check device_trials table (web app tracking)
            try:
                device_check = sb.table("device_trials").select("id").eq("device_fingerprint", device_fingerprint).execute()
                if device_check.data:
                    trial_used = max(trial_used, 1)
            except Exception:
                pass

        # TRIAL: First generation is FREE (but uses cloud API highest resolution)
        if is_trial and trial_used == 0:
            return True, "trial_free", 0

        # If user has trial remaining (web app style), use that
        if trial_remaining > 0 and not is_trial:
            return True, "trial", 0

        # If it was requested as trial but device/user already used it
        if is_trial and trial_used > 0:
            pass  # Fall through to credit check

        # Check credit balance for non-trial generations
        cost = CREDIT_COSTS.get(resolution, 20)
        credits_res = (
            sb.table("user_credits")
            .select("credits_balance")
            .eq("user_id", user_id)
            .execute()
        )
        balance = credits_res.data[0]["credits_balance"] if credits_res.data else 0

        if balance >= cost:
            return True, "credits", cost
        else:
            return False, f"Insufficient credits. Need {cost}, have {balance}.", cost

    except Exception as e:
        return False, str(e), 0


# ═══════════════════════════════════════════════════════════════
# CREDIT DEDUCTION (on generation)
# ═══════════════════════════════════════════════════════════════

def deduct_credits(
    user_id: str,
    resolution: str,
    model_id: str,
    input_type: str = "image",
    output_format: str = "glb",
    is_trial: bool = False,
    device_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deduct credits for a generation. Handles trial (free first generation) or paid credits.
    For trial: First generation is FREE (showcase quality), then user must buy credits.
    For subsequent: Deducts from user's credit balance.
    Returns {"success": bool, "generation_id": str, "credits_deducted": int, "balance_after": int}
    """
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    try:
        import uuid
        try:
            uuid.UUID(str(user_id))
        except ValueError:
            return {
                "success": True,
                "generation_id": None,
                "credits_deducted": 0,
                "balance_after": 0,
                "source": "local_bypass",
            }

        # Check if can generate
        allowed, reason, cost = can_generate(
            user_id, resolution, is_trial, device_fingerprint
        )
        if not allowed:
            return {"success": False, "error": reason}

        # TRIAL FREE: First generation is FREE (showcase quality)
        if reason == "trial_free":
            # Mark trial as used in web_users
            sb.table("web_users").update(
                {"trial_used": 1, "trial_remaining": 0}
            ).eq("id", user_id).execute()

            # Mark trial as used in registered_devices if fingerprint provided
            if device_fingerprint:
                try:
                    sb.table("registered_devices").update(
                        {"trial_used": 1, "trial_remaining": 0}
                    ).eq("device_fingerprint", device_fingerprint).execute()
                except Exception:
                    pass
                # Also record in device_trials table
                try:
                    sb.table("device_trials").insert({
                        "device_fingerprint": device_fingerprint,
                        "user_id": user_id,
                    }).execute()
                except Exception:
                    pass

            # Log generation (0 credits deducted)
            gen_result = sb.table("user_generations").insert({
                "user_id": user_id,
                "model_id": model_id,
                "resolution": resolution,
                "credits_deducted": 0,
                "input_type": input_type,
                "output_format": output_format,
                "status": "started",
            }).execute()

            gen_id = gen_result.data[0]["id"] if gen_result.data else None

            # Ledger entry for trial
            sb.table("credit_ledger").insert({
                "user_id": user_id,
                "amount": 0,
                "type": "trial_free",
                "description": f"First generation FREE (trial) - {resolution}px ({model_id})",
                "reference_id": gen_id,
                "balance_after": 0,
            }).execute()

            return {
                "success": True,
                "generation_id": gen_id,
                "credits_deducted": 0,
                "balance_after": 0,
                "source": "trial_free",
            }

        elif reason == "trial":
            # Use trial (web app style) - trial only covers 1 credit worth
            trial_value = 1

            if cost > trial_value:
                credits_data = sb.table("user_credits").select("credits_balance").eq("user_id", user_id).execute()
                balance = credits_data.data[0]["credits_balance"] if credits_data.data else 0
                additional_needed = cost - trial_value

                if balance < additional_needed:
                    return {
                        "success": False,
                        "error": f"Trial only covers {trial_value} credit. {resolution} requires {cost} credits. You need {additional_needed} more credits."
                    }

                new_balance = balance - additional_needed
                sb.table("user_credits").update({
                    "credits_balance": new_balance,
                    "total_used": additional_needed,
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("user_id", user_id).execute()
            else:
                new_balance = 0
                additional_needed = 0

            # Use trial
            sb.table("web_users").update({
                "trial_remaining": 0,
                "trial_used": 1,
            }).eq("id", user_id).execute()

            gen_result = sb.table("user_generations").insert({
                "user_id": user_id,
                "model_id": model_id,
                "resolution": resolution,
                "credits_deducted": additional_needed,
                "input_type": input_type,
                "output_format": output_format,
                "status": "started",
            }).execute()

            gen_id = gen_result.data[0]["id"] if gen_result.data else None

            sb.table("credit_ledger").insert({
                "user_id": user_id,
                "amount": -additional_needed,
                "type": "trial_usage",
                "description": f"Trial + {additional_needed} credits for {resolution}px ({model_id})",
                "reference_id": gen_id,
                "balance_after": new_balance,
            }).execute()

            return {
                "success": True,
                "generation_id": gen_id,
                "credits_deducted": additional_needed,
                "balance_after": new_balance,
                "source": "trial",
            }

        else:
            # Deduct from credits
            credits_data = sb.table("user_credits").select("*").eq("user_id", user_id).execute()
            if not credits_data.data:
                return {"success": False, "error": "No credit record found"}

            current = credits_data.data[0]
            new_balance = current["credits_balance"] - cost

            sb.table("user_credits").update({
                "credits_balance": new_balance,
                "total_used": current["total_used"] + cost,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("user_id", user_id).execute()

            gen_result = sb.table("user_generations").insert({
                "user_id": user_id,
                "model_id": model_id,
                "resolution": resolution,
                "credits_deducted": cost,
                "input_type": input_type,
                "output_format": output_format,
                "status": "started",
            }).execute()

            gen_id = gen_result.data[0]["id"] if gen_result.data else None

            sb.table("credit_ledger").insert({
                "user_id": user_id,
                "amount": -cost,
                "type": "usage",
                "description": f"Generated {resolution}px model ({model_id})",
                "reference_id": gen_id,
                "balance_after": new_balance,
            }).execute()

            return {
                "success": True,
                "generation_id": gen_id,
                "credits_deducted": cost,
                "balance_after": new_balance,
                "source": "credits",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def mark_generation_complete(generation_id: str, success: bool,
                             time_ms: Optional[int] = None, error: Optional[str] = None):
    """Mark a generation as completed or failed. Refunds trial and credits if failed."""
    sb = get_supabase()
    if not sb or not generation_id:
        return

    try:
        # Check current status, avoid double refund
        gen_data = sb.table("user_generations").select("status, user_id, credits_deducted").eq("id", generation_id).execute()
        if gen_data.data:
            current_status = gen_data.data[0]["status"]
            user_id = gen_data.data[0]["user_id"]
            credits_deducted = gen_data.data[0]["credits_deducted"] or 0
            
            # If failing and it was started, we refund
            if not success and current_status == "started":
                # Check credit_ledger to see if trial was used
                ledger_data = sb.table("credit_ledger").select("*").eq("reference_id", generation_id).execute()
                trial_used = False
                total_credits_refunded = 0
                
                if ledger_data.data:
                    for entry in ledger_data.data:
                        # Sometimes trial_usage may have 0 amount, we just check the type
                        if entry["type"] == "trial_usage":
                            trial_used = True
                        if entry["amount"] < 0: # Usage negative
                            total_credits_refunded += abs(entry["amount"])
                            
                # Fallback if ledger was not created properly but credits were deducted
                if not ledger_data.data and credits_deducted > 0:
                    total_credits_refunded = credits_deducted
                
                # Refund trial if it was used
                if trial_used:
                    user_data = sb.table("web_users").select("trial_remaining, trial_used").eq("id", user_id).execute()
                    if user_data.data:
                        # Refund trial: increment remaining, decrement used
                        sb.table("web_users").update({
                            "trial_remaining": user_data.data[0]["trial_remaining"] + 1,
                            "trial_used": max(0, user_data.data[0]["trial_used"] - 1),
                        }).eq("id", user_id).execute()
                        
                # Refund credits if any were deducted
                if total_credits_refunded > 0:
                    credits_data = sb.table("user_credits").select("credits_balance").eq("user_id", user_id).execute()
                    if credits_data.data:
                        current_balance = credits_data.data[0]["credits_balance"]
                        new_balance = current_balance + total_credits_refunded
                        
                        sb.table("user_credits").update({
                            "credits_balance": new_balance,
                            "updated_at": datetime.utcnow().isoformat(),
                        }).eq("user_id", user_id).execute()
                        
                        # Add refund ledger entry
                        sb.table("credit_ledger").insert({
                            "user_id": user_id,
                            "amount": total_credits_refunded,
                            "type": "refund",
                            "description": "Refund for failed generation",
                            "reference_id": generation_id,
                            "balance_after": new_balance,
                        }).execute()

        update: Dict[str, Any] = {"status": "completed" if success else "failed"}
        if time_ms:
            update["generation_time_ms"] = time_ms
        if error:
            update["error_message"] = error
        sb.table("user_generations").update(update).eq("id", generation_id).execute()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# CREDIT ADDITION (on purchase — automated via webhooks)
# ═══════════════════════════════════════════════════════════════

def add_credits_from_purchase(
    user_id: str,
    platform: str,
    platform_transaction_id: str,
    plan_id: str,
    amount_paid: float,
    currency: str = "INR",
    buyer_email: Optional[str] = None,
    buyer_name: Optional[str] = None,
    platform_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Add credits to user account after a purchase from any platform.
    This is called by webhook handlers (Gumroad, Razorpay, Stripe, etc.)
    
    Returns {"success": bool, "credits_added": int, "new_balance": int}
    """
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    # Look up credits for this plan
    pack = CREDIT_PACKS.get(plan_id)
    if not pack:
        return {"success": False, "error": f"Unknown plan: {plan_id}"}

    credits_to_add = pack["credits"]

    try:
        # 1. Record payment transaction
        sb.table("payment_transactions").insert({
            "user_id": user_id,
            "platform": platform,
            "platform_transaction_id": platform_transaction_id,
            "product_name": pack["name"],
            "plan_id": plan_id,
            "amount_paid": amount_paid,
            "currency": currency,
            "credits_purchased": credits_to_add,
            "status": "completed",
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "platform_payload": platform_payload or {},
            "paid_at": datetime.utcnow().isoformat(),
        }).execute()

        # 2. Update user credit balance
        credits_data = sb.table("user_credits").select("*").eq("user_id", user_id).execute()
        if credits_data.data:
            current = credits_data.data[0]
            new_balance = current["credits_balance"] + credits_to_add
            sb.table("user_credits").update({
                "credits_balance": new_balance,
                "total_purchased": current["total_purchased"] + credits_to_add,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("user_id", user_id).execute()
        else:
            new_balance = credits_to_add
            sb.table("user_credits").insert({
                "user_id": user_id,
                "credits_balance": new_balance,
                "total_purchased": credits_to_add,
                "total_used": 0,
            }).execute()

        # 3. Ledger entry
        sb.table("credit_ledger").insert({
            "user_id": user_id,
            "amount": credits_to_add,
            "type": "purchase",
            "description": f"{pack['name']} via {platform} (₹{amount_paid})",
            "balance_after": new_balance,
        }).execute()

        return {
            "success": True,
            "credits_added": credits_to_add,
            "new_balance": new_balance,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def admin_grant_credits(user_id: str, credits: int, reason: str = "Admin grant") -> Dict[str, Any]:
    """Admin manually grants credits to a user."""
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    try:
        credits_data = sb.table("user_credits").select("*").eq("user_id", user_id).execute()
        if credits_data.data:
            current = credits_data.data[0]
            new_balance = current["credits_balance"] + credits
            sb.table("user_credits").update({
                "credits_balance": new_balance,
                "total_purchased": current["total_purchased"] + credits,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("user_id", user_id).execute()
        else:
            new_balance = credits
            sb.table("user_credits").insert({
                "user_id": user_id,
                "credits_balance": new_balance,
                "total_purchased": credits,
                "total_used": 0,
            }).execute()

        sb.table("credit_ledger").insert({
            "user_id": user_id,
            "amount": credits,
            "type": "admin_grant",
            "description": reason,
            "balance_after": new_balance,
        }).execute()

        return {"success": True, "credits_added": credits, "new_balance": new_balance}

    except Exception as e:
        return {"success": False, "error": str(e)}


def process_refund(platform_transaction_id: str) -> Dict[str, Any]:
    """Process a refund — deduct credits that were previously granted."""
    sb = get_supabase()
    if not sb:
        return {"success": False, "error": "Database not available"}

    try:
        # Find original transaction
        txn = sb.table("payment_transactions").select("*").eq(
            "platform_transaction_id", platform_transaction_id
        ).execute()

        if not txn.data:
            return {"success": False, "error": "Transaction not found"}

        original = txn.data[0]
        user_id = original["user_id"]
        credits_to_remove = original["credits_purchased"]

        # Update transaction status
        sb.table("payment_transactions").update({
            "status": "refunded"
        }).eq("platform_transaction_id", platform_transaction_id).execute()

        # Deduct credits
        credits_data = sb.table("user_credits").select("*").eq("user_id", user_id).execute()
        if credits_data.data:
            current = credits_data.data[0]
            new_balance = max(0, current["credits_balance"] - credits_to_remove)
            sb.table("user_credits").update({
                "credits_balance": new_balance,
                "total_purchased": max(0, current["total_purchased"] - credits_to_remove),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("user_id", user_id).execute()

            sb.table("credit_ledger").insert({
                "user_id": user_id,
                "amount": -credits_to_remove,
                "type": "refund",
                "description": f"Refund for {original['product_name']} via {original['platform']}",
                "balance_after": new_balance,
            }).execute()

            return {"success": True, "credits_removed": credits_to_remove, "new_balance": new_balance}

        return {"success": False, "error": "User credits not found"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# MASTER API KEY (server-side only — never exposed to users)
# ═══════════════════════════════════════════════════════════════

def get_master_api_key(provider: str = "hitem3d") -> Optional[str]:
    """
    Retrieve admin's master API key from Supabase model_api_keys.
    This key is NEVER sent to the frontend.
    """
    sb = get_supabase()
    if not sb:
        return None

    try:
        result = sb.table("model_api_keys").select("key_name, key_value").eq(
            "model_id", provider
        ).eq("is_active", True).execute()

        if not result.data:
            return None

        # For hitem3d, combine client_id:client_secret
        keys = {row["key_name"]: row["key_value"] for row in result.data}

        if "access_token" in keys and keys["access_token"]:
            return keys["access_token"]
        elif "HITEM3D_CLIENT_ID" in keys and "HITEM3D_CLIENT_SECRET" in keys:
            return f"{keys['HITEM3D_CLIENT_ID']}:{keys['HITEM3D_CLIENT_SECRET']}"
        elif "client_id" in keys and "client_secret" in keys:
            return f"{keys['client_id']}:{keys['client_secret']}"

        # Return first available key
        for v in keys.values():
            if v:
                return v

        return None

    except Exception:
        return None


async def get_available_text_to_3d_provider() -> Optional[Dict[str, Any]]:
    """
    Find the best available provider for text-to-3D generation.
    Checks providers in priority order: Tripo3D, Meshy AI, Neural4D.
    Returns the first provider that has both API key configured and available credits.
    
    Returns:
        Dict with 'provider', 'api_key', 'balance' or None if no provider available
    """
    import asyncio
    
    # Text-to-3D capable providers in priority order
    providers = [
        {"id": "tripo3d", "name": "Tripo3D", "env_key": "TRIPO_API_KEY"},
        {"id": "meshy_ai", "name": "Meshy AI", "env_key": "MESHY_API_KEY"},
        {"id": "neural4d", "name": "Neural4D", "env_key": "NEURAL4D_API_TOKEN"},
    ]
    
    for provider in providers:
        provider_id = provider["id"]
        
        # Try to get API key from Supabase first, then environment
        api_key = get_master_api_key(provider_id)
        if not api_key:
            api_key = os.getenv(provider["env_key"]) or os.getenv("API_KEY")
        
        if not api_key:
            continue
        
        # Check credits/balance for this provider
        try:
            balance = None
            
            if provider_id == "tripo3d":
                from core.tripo3d_client import Tripo3DClient
                client = Tripo3DClient(api_key=api_key)
                balance_result = await client.get_balance()
                if balance_result and hasattr(balance_result, "remaining_credits"):
                    balance = float(balance_result.remaining_credits)
                elif balance_result and hasattr(balance_result, "total_credits"):
                    balance = float(balance_result.total_credits)
            
            elif provider_id == "meshy_ai":
                from core.meshy_ai_client import MeshyAIClient
                client = MeshyAIClient(api_key=api_key)
                # Meshy AI doesn't have a direct balance endpoint, assume available if key works
                # We'll validate by making a test request or assume valid
                balance = 1  # Meshy AI uses per-request pricing, assume available
            
            elif provider_id == "neural4d":
                from core.neural4d_client import Neural4DClient
                client = Neural4DClient(api_token=api_key)
                balance_result = await client.get_balance()
                if balance_result and isinstance(balance_result, dict):
                    balance = balance_result.get("remaining_points", 0)
            
            # If we have an API key and positive balance, use this provider
            if balance is None or balance > 0:
                return {
                    "provider": provider_id,
                    "api_key": api_key,
                    "balance": balance,
                    "name": provider["name"]
                }
        
        except Exception as e:
            print(f"[credit_manager] Failed to check {provider_id}: {e}")
            continue
    
    return None


def get_text_to_3d_provider_api_key(provider: str) -> Optional[str]:
    """
    Get API key for a specific text-to-3D provider.
    Checks Supabase first, then environment variables.
    """
    # Try Supabase first
    api_key = get_master_api_key(provider)
    if api_key:
        return api_key
    
    # Try environment variables
    env_map = {
        "tripo3d": ["TRIPO_API_KEY", "TRIPO3D_API_KEY", "API_KEY"],
        "meshy_ai": ["MESHY_API_KEY", "API_KEY"],
        "neural4d": ["NEURAL4D_API_TOKEN", "NEURAL4D_API_KEY", "API_KEY"],
    }
    
    for env_var in env_map.get(provider, []):
        key = os.getenv(env_var)
        if key:
            return key
    
    return None


def get_user_purchase_history(user_id: str) -> list:
    """Get full purchase history for a user."""
    sb = get_supabase()
    if not sb:
        return []

    try:
        result = sb.table("payment_transactions").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).execute()
        return result.data or []
    except Exception:
        return []


def get_user_credit_history(user_id: str, limit: int = 50) -> list:
    """Get credit ledger history for a user."""
    sb = get_supabase()
    if not sb:
        return []

    try:
        result = sb.table("credit_ledger").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception:
        return []


def get_all_transactions(platform: Optional[str] = None, limit: int = 100) -> list:
    """Admin: Get all transactions, optionally filtered by platform."""
    sb = get_supabase()
    if not sb:
        return []

    try:
        query = sb.table("payment_transactions").select("*")
        if platform:
            query = query.eq("platform", platform)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception:
        return []
