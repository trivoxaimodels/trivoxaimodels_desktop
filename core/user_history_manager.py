"""
User History Manager for Desktop App

Provides functions to get generation history and credit history from Supabase.
"""

from typing import List, Dict, Any, Optional
from core.supabase_client import get_supabase
from core.logger import get_logger

logger = get_logger(__name__)


def get_generation_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user's generation history from database.
    
    Args:
        user_id: The user ID to get history for
        limit: Maximum number of records to return
        
    Returns:
        List of generation records
    """
    sb = get_supabase()
    if not sb:
        logger.warning("Supabase not available - cannot fetch generation history")
        return []
    
    try:
        result = (
            sb.table("user_generations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get generation history: {e}")
        return []


def get_credit_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user's credit transaction history from database.
    
    Args:
        user_id: The user ID to get history for
        limit: Maximum number of records to return
        
    Returns:
        List of credit ledger records
    """
    sb = get_supabase()
    if not sb:
        logger.warning("Supabase not available - cannot fetch credit history")
        return []
    
    try:
        result = (
            sb.table("credit_ledger")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get credit history: {e}")
        return []


def get_purchase_history(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user's purchase/transaction history.
    
    Args:
        user_id: The user ID to get history for
        limit: Maximum number of records to return
        
    Returns:
        List of payment transaction records
    """
    sb = get_supabase()
    if not sb:
        logger.warning("Supabase not available - cannot fetch purchase history")
        return []
    
    try:
        result = (
            sb.table("payment_transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get purchase history: {e}")
        return []


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile information.
    
    Args:
        user_id: The user ID to get profile for
        
    Returns:
        User profile dict or None
    """
    sb = get_supabase()
    if not sb:
        return None
    
    try:
        result = (
            sb.table("web_users")
            .select("*")
            .eq("id", user_id)
            .execute()
        )
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        return None
