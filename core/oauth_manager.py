"""
OAuth Manager Application

Handles Google for Desktop and GitHub OAuth authentication for desktop app.
Uses Supabase Auth for OAuth - same as web app.

Flow:
1. User clicks OAuth button
2. Desktop opens system browser for OAuth
3. OAuth redirects to localhost callback server
4. Callback server receives auth code
5. Exchanges code for session
6. Syncs user to web_users table
"""

import os
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from core.supabase_client import get_supabase
from core.logger import get_logger

logger = get_logger(__name__)


# OAuth Configuration - Get from environment
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

# Redirect URI for desktop OAuth
OAUTH_REDIRECT_URI = "http://localhost:9876/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    callback_result: Optional[Dict[str, Any]] = None
    server_instance = None
    
    def do_GET(self):
        """Handle OAuth callback GET request"""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        
        # Check for code (success)
        if "code" in query_params:
            code = query_params["code"][0]
            state = query_params.get("state", [""])[0]
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Login Successful</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2 style="color: #10b981;">✅ Login Successful!</h2>
                    <p>You can now close this window and return to the application.</p>
                    <script>setTimeout(function(){ window.close(); }, 2000);</script>
                </body>
                </html>
            """)
            
            # Store result
            OAuthCallbackHandler.callback_result = {
                "success": True,
                "code": code,
                "state": state,
                "provider": self.server.provider
            }
        
        # Check for error (failure)
        elif "error" in query_params:
            error = query_params["error"][0]
            error_desc = query_params.get("error_description", ["Unknown error"])[0]
            
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <head><title>Login Failed</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2 style="color: #ef4444;">❌ Login Failed</h2>
                    <p>Error: {error}</p>
                    <p>{error_desc}</p>
                </body>
                </html>
            """.encode())
            
            OAuthCallbackHandler.callback_result = {
                "success": False,
                "error": error,
                "error_description": error_desc,
                "provider": self.server.provider
            }
        
        # Stop server
        threading.Thread(target=self.server.shutdown, daemon=True).start()
    
    def log_message(self, format, *args):
        """Suppress logging"""
        pass


class OAuthCallbackServer(HTTPServer):
    """Simple HTTP server for OAuth callback"""
    
    def __init__(self, provider: str):
        super().__init__(("localhost", 9876), OAuthCallbackHandler)
        self.provider = provider
        OAuthCallbackHandler.callback_result = None


class OAuthManager:
    """
    OAuth Manager for desktop app.
    
    Handles OAuth flow for Google and GitHub.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._supabase = None
        self._callback_server: Optional[OAuthCallbackServer] = None
    
    def _get_supabase(self):
        """Get Supabase client"""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase
    
    def get_google_auth_url(self, state: str = "") -> str:
        """Get Google OAuth authorization URL"""
        if not GOOGLE_CLIENT_ID:
            logger.warning("Google OAuth not configured - missing GOOGLE_CLIENT_ID")
            return ""
        
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    
    def get_github_auth_url(self, state: str = "") -> str:
        """Get GitHub OAuth authorization URL"""
        if not GITHUB_CLIENT_ID:
            logger.warning("GitHub OAuth not configured - missing GITHUB_CLIENT_ID")
            return ""
        
        params = {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "scope": "user:email",
            "allow_signup": "true",
        }
        if state:
            params["state"] = state
        
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    
    def _start_callback_server(self, provider: str) -> OAuthCallbackServer:
        """Start the OAuth callback server"""
        self._callback_server = OAuthCallbackServer(provider)
        
        # Run server in background thread
        thread = threading.Thread(target=self._callback_server.serve_forever, daemon=True)
        thread.start()
        
        return self._callback_server
    
    def _wait_for_callback(self, timeout: int = 120) -> Optional[Dict[str, Any]]:
        """Wait for OAuth callback"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if OAuthCallbackHandler.callback_result is not None:
                result = OAuthCallbackHandler.callback_result
                OAuthCallbackHandler.callback_result = None
                return result
            time.sleep(0.5)
        
        return None
    
    def login_with_google(self) -> Dict[str, Any]:
        """
        Initiate Google OAuth login.
        
        Opens system browser for user to authenticate.
        Returns the result after OAuth flow completes.
        """
        if not GOOGLE_CLIENT_ID:
            return {
                "success": False,
                "error": "Google OAuth not configured",
                "error_description": "Please contact support for login assistance."
            }
        
        # Start callback server
        self._start_callback_server("google")
        
        # Get auth URL
        auth_url = self.get_google_auth_url()
        if not auth_url:
            return {
                "success": False,
                "error": "OAuth configuration error",
                "error_description": "Unable to initialize Google login."
            }
        
        # Open browser
        import webbrowser
        webbrowser.open(auth_url)
        
        # Wait for callback
        logger.info("Waiting for Google OAuth callback...")
        result = self._wait_for_callback()
        
        if not result:
            return {
                "success": False,
                "error": "timeout",
                "error_description": "Login timed out. Please try again."
            }
        
        if not result.get("success"):
            return result
        
        # Exchange code for session
        return self._exchange_code(result["code"], "google")
    
    def login_with_github(self) -> Dict[str, Any]:
        """
        Initiate GitHub OAuth login.
        
        Opens system browser for user to authenticate.
        Returns the result after OAuth flow completes.
        """
        if not GITHUB_CLIENT_ID:
            return {
                "success": False,
                "error": "GitHub OAuth not configured",
                "error_description": "Please contact support for login assistance."
            }
        
        # Start callback server
        self._start_callback_server("github")
        
        # Get auth URL
        auth_url = self.get_github_auth_url()
        if not auth_url:
            return {
                "success": False,
                "error": "OAuth configuration error",
                "error_description": "Unable to initialize GitHub login."
            }
        
        # Open browser
        import webbrowser
        webbrowser.open(auth_url)
        
        # Wait for callback
        logger.info("Waiting for GitHub OAuth callback...")
        result = self._wait_for_callback()
        
        if not result:
            return {
                "success": False,
                "error": "timeout",
                "error_description": "Login timed out. Please try again."
            }
        
        if not result.get("success"):
            return result
        
        # Exchange code for session
        return self._exchange_code(result["code"], "github")
    
    def _exchange_code(self, code: str, provider: str) -> Dict[str, Any]:
        """
        Exchange OAuth code for session.
        
        This calls the web API to:
        1. Exchange code for Supabase session
        2. Sync user to web_users table
        """
        try:
            client = self._get_supabase()
            if not client:
                return {
                    "success": False,
                    "error": "database_error",
                    "error_description": "Cannot connect to server."
                }
            
            # Exchange code for session using Supabase
            if provider == "google":
                response = client.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {
                        "redirect_to": OAUTH_REDIRECT_URI,
                    }
                })
            else:
                response = client.auth.sign_in_with_oauth({
                    "provider": "github",
                    "options": {
                        "redirect_to": OAUTH_REDIRECT_URI,
                    }
                })
            
            # Get user session
            session = client.auth.get_session()
            if not session:
                return {
                    "success": False,
                    "error": "session_error",
                    "error_description": "Failed to create session."
                }
            
            # Get user info
            user = session.user
            email = user.email
            user_id = user.id
            
            # Sync to web_users table (same as web app)
            return self._sync_oauth_user(user_id, email, provider)
            
        except Exception as e:
            logger.error(f"OAuth code exchange failed: {e}")
            return {
                "success": False,
                "error": "exchange_failed",
                "error_description": str(e)
            }
    
    def _sync_oauth_user(self, uid: str, email: str, provider: str) -> Dict[str, Any]:
        """
        Sync OAuth user to web_users table.
        
        Same logic as web app's /api/oauth-sync endpoint.
        """
        try:
            client = self._get_supabase()
            if not client:
                return {
                    "success": False,
                    "error": "database_error",
                    "error_description": "Cannot connect to server."
                }
            
            # Generate username and password (same as web app)
            username = email.split('@')[0].replace('.', '_') + "_" + uid[:5]
            password = uid + "_oauth_P@ssw0rd!"
            
            # Try to find existing user
            existing = client.table("web_users").select("id").eq("username", username).execute()
            
            if existing.data:
                # User exists, return success
                user_id = existing.data[0]["id"]
            else:
                # Create new user
                import uuid
                # Check if username exists, if so add suffix
                try:
                    result = client.table("web_users").insert({
                        "username": username,
                        "password_hash": self._hash_password(password),
                        "email": email,
                        "oauth_provider": provider,
                        "trial_remaining": 1,
                        "trial_used": 0,
                    }).execute()
                    
                    if not result.data:
                        return {
                            "success": False,
                            "error": "create_failed",
                            "error_description": "Failed to create user account."
                        }
                    
                    user_id = result.data[0]["id"]
                    
                except Exception as insert_error:
                    # Username might already exist, try with suffix
                    username = username + "_" + str(uuid.uuid4())[:4]
                    result = client.table("web_users").insert({
                        "username": username,
                        "password_hash": self._hash_password(password),
                        "email": email,
                        "oauth_provider": provider,
                        "trial_remaining": 1,
                        "trial_used": 0,
                    }).execute()
                    
                    if not result.data:
                        return {
                            "success": False,
                            "error": "create_failed",
                            "error_description": "Failed to create user account."
                        }
                    
                    user_id = result.data[0]["id"]
            
            # Initialize credits if not exists
            credits_check = client.table("user_credits").select("id").eq("user_id", user_id).execute()
            if not credits_check.data:
                client.table("user_credits").insert({
                    "user_id": user_id,
                    "credits_balance": 0,
                    "total_purchased": 0,
                    "total_used": 0,
                }).execute()
            
            # Register device for this user
            from core.device_fingerprint import get_device_fingerprint
            from core.server_auth import register_device_server
            
            device_fp = get_device_fingerprint()
            device_result = register_device_server(
                fingerprint=device_fp,
                password_hash=self._hash_password(password),
                machine_name="Desktop",
                platform_info="Desktop",
                app_version="1.0.0"
            )
            
            return {
                "success": True,
                "user_id": user_id,
                "username": username,
                "email": email,
                "oauth_provider": provider,
                "device_registered": device_result.get("success", False),
            }
            
        except Exception as e:
            logger.error(f"OAuth user sync failed: {e}")
            return {
                "success": False,
                "error": "sync_failed",
                "error_description": str(e)
            }
    
    def _hash_password(self, password: str) -> str:
        """Hash password with SHA256"""
        import hashlib
        salt = "voxeloauth_salt_2026"
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


# Singleton instance
oauth_manager = OAuthManager()


def get_oauth_manager() -> OAuthManager:
    """Get OAuth manager singleton"""
    return oauth_manager
