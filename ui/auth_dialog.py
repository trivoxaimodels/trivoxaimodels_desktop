"""
Authentication Dialog for VoxelCraft Desktop

Provides login options:
  - Device fingerprint login
  - Google OAuth
  - GitHub OAuth

Theme matches the VoxelCraft UI design (fordesktopapp.png):
  - Deep dark navy background (#0a0e1a)
  - Card surfaces (#111827 / #1a2332)
  - Cyan/teal accent (#00b4d8 / #0ea5e9)
  - Clean modern typography
  - Rounded corners, subtle glow effects
"""

import webbrowser
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

import sys
import os

# Add parent directory to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.session_manager import SessionManager
from core.supabase_client import auth


import http.server
import socketserver
import threading
from urllib.parse import parse_qs


class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        if self.path.startswith("/auth/callback"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = """
            <html>
            <head><title>Authentication Successful</title>
            <style>
                body { background-color: #0c1222; color: #e2e8f0; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { background-color: #111c2e; padding: 40px; border-radius: 12px; text-align: center; border: 1px solid #1e3050; }
                h1 { color: #0ea5e9; }
            </style>
            </head>
            <body>
            <div class="card" id="msg">
                <h1>Completing login...</h1>
                <p>Please wait while we securely log you in.</p>
            </div>
            <script>
            var params = new URLSearchParams(window.location.search);
            var code = params.get('code');
            if(code) {
                fetch('/auth/token', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'code=' + encodeURIComponent(code)
                }).then(() => {
                    document.getElementById('msg').innerHTML = "<h1>Login Successful! ✅</h1><p>You can close this window and return to the VoxelCraft app.</p>";
                }).catch(e => {
                    document.getElementById('msg').innerHTML = "<h1>Error ❌</h1><p>Failed to send token to the app.</p>";
                });
            } else {
                document.getElementById('msg').innerHTML = "<h1>Action Required</h1><p>No code found in the URL. If you expected to login, please try again.</p>";
            }
            </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/auth/token":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            data = parse_qs(post_data)

            code = data.get("code", [None])[0]

            if code:
                try:
                    from core.supabase_client import get_supabase

                    client = get_supabase()
                    redirect_uri = getattr(
                        self.server,
                        "redirect_uri",
                        f"http://127.0.0.1:43210/auth/callback",
                    )
                    code_verifier = getattr(self.server, "code_verifier", None)

                    result = client.auth.exchange_code_for_session(
                        {
                            "auth_code": code,
                            "redirect_to": redirect_uri,
                            "code_verifier": code_verifier,
                        }
                    )
                    self.server.oauth_tokens = {
                        "access_token": [result.session.access_token],
                        "refresh_token": [result.session.refresh_token],
                    }
                except Exception as e:
                    self.wfile.write(f"Error exchanging code: {e}".encode("utf-8"))
                    return

            self.send_response(200)
            self.end_headers()
            threading.Thread(target=self.server.shutdown).start()


class OAuthCallbackThread(QThread):
    """Thread to handle OAuth callback."""

    callback_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        provider: str,
        oauth_url: str,
        port: int = 43210,
        code_verifier: str = None,
    ):
        super().__init__()
        self.provider = provider
        self.oauth_url = oauth_url
        self.port = port
        self.code_verifier = code_verifier
        self.server = None

    def run(self):
        """Start local server, open browser, and wait for callback."""
        try:
            socketserver.TCPServer.allow_reuse_address = True
            try:
                self.server = socketserver.TCPServer(
                    ("127.0.0.1", self.port), OAuthCallbackHandler
                )
            except OSError:
                self.error_occurred.emit(
                    f"Port {self.port} is already in use. Cannot start OAuth callback server."
                )
                return

            self.server.oauth_tokens = None
            self.server.redirect_uri = f"http://127.0.0.1:{self.port}/auth/callback"
            self.server.code_verifier = self.code_verifier

            # Open browser for OAuth
            webbrowser.open(self.oauth_url)

            # This blocks until shutdown is called in do_POST
            self.server.serve_forever()

            if self.server.oauth_tokens:
                self.callback_received.emit(self.server.oauth_tokens)
            else:
                self.error_occurred.emit("Authentication was cancelled or failed.")

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.server:
                self.server.server_close()

    def stop(self):
        """Stop the thread."""
        if self.server:
            threading.Thread(target=self.server.shutdown).start()


class AuthDialog(QDialog):
    """
    Authentication dialog with multiple login options.

    Features:
      - Device fingerprint login
      - Google OAuth login
      - GitHub OAuth login

    Styled to match the VoxelCraft UI theme from fordesktopapp.png:
      - Deep dark navy/space background
      - Cyan/blue accent colors
      - Modern card-based layout with subtle glow
      - Clean typography
    """

    # ── colour palette (matching fordesktopapp.png) ──────────────
    BG_DARKEST = "#060b18"  # dialog / window background
    BG_DARK = "#0c1222"  # main card background
    BG_CARD = "#111c2e"  # inner card / device frame
    BORDER = "#1e3050"  # subtle borders
    BORDER_HOVER = "#2a4a70"  # border on hover
    ACCENT = "#0ea5e9"  # primary cyan/blue accent
    ACCENT_HOVER = "#38bdf8"  # lighter accent on hover
    ACCENT_PRESS = "#0284c7"  # darker accent on press
    TEXT_PRIMARY = "#e2e8f0"  # main text
    TEXT_SECONDARY = "#94a3b8"  # muted text
    TEXT_MUTED = "#64748b"  # very muted text
    DANGER = "#ef4444"  # error / danger
    SUCCESS = "#22c55e"  # success green
    GOOGLE_BG = "#4285f4"  # Google brand blue
    GOOGLE_HOVER = "#3367d6"
    GOOGLE_PRESS = "#2a56c6"
    GITHUB_BG = "#1a1e24"  # GitHub dark
    GITHUB_HOVER = "#24292e"
    GITHUB_PRESS = "#111111"

    def __init__(self, session_manager: SessionManager, parent=None):
        super().__init__(parent)
        self.session_manager = session_manager
        self.oauth_thread: Optional[OAuthCallbackThread] = None

        self.setWindowTitle("VoxelCraft - Sign In")
        self.setFixedSize(520, 620)
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag_pos = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI with theme matching fordesktopapp.png."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)

        # ── main card container ──────────────────────────────────
        self.container = QFrame()
        self.container.setObjectName("authMainCard")

        # subtle cyan glow shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(14, 165, 233, 45))
        shadow.setOffset(0, 6)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setSpacing(18)
        layout.setContentsMargins(36, 28, 36, 28)

        # ── close button row ─────────────────────────────────────
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("authCloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        # ── title ────────────────────────────────────────────────
        title = QLabel("Welcome to VoxelCraft")
        title.setObjectName("authTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("3D Model Generation from Images")
        subtitle.setObjectName("authSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # spacer
        layout.addSpacerItem(
            QSpacerItem(20, 12, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )

        # ── device login card ────────────────────────────────────
        device_frame = self._create_device_login_frame()
        layout.addWidget(device_frame)

        # ── divider ──────────────────────────────────────────────
        divider_row = QHBoxLayout()
        divider_row.setSpacing(12)
        left_line = QFrame()
        left_line.setFrameShape(QFrame.HLine)
        left_line.setObjectName("authDividerLine")
        divider_row.addWidget(left_line)

        divider_label = QLabel("or sign in with")
        divider_label.setObjectName("authDividerText")
        divider_label.setAlignment(Qt.AlignCenter)
        divider_row.addWidget(divider_label)

        right_line = QFrame()
        right_line.setFrameShape(QFrame.HLine)
        right_line.setObjectName("authDividerLine")
        divider_row.addWidget(right_line)
        layout.addLayout(divider_row)

        # ── OAuth buttons ────────────────────────────────────────
        oauth_layout = QVBoxLayout()
        oauth_layout.setSpacing(10)

        self.google_btn = QPushButton("  Sign in with Google")
        self.google_btn.setObjectName("authGoogleBtn")
        self.google_btn.setMinimumHeight(46)
        self.google_btn.setCursor(Qt.PointingHandCursor)
        self.google_btn.clicked.connect(self._on_google_login)
        oauth_layout.addWidget(self.google_btn)

        self.github_btn = QPushButton("  Sign in with GitHub")
        self.github_btn.setObjectName("authGithubBtn")
        self.github_btn.setMinimumHeight(46)
        self.github_btn.setCursor(Qt.PointingHandCursor)
        self.github_btn.clicked.connect(self._on_github_login)
        oauth_layout.addWidget(self.github_btn)

        layout.addLayout(oauth_layout)

        # spacer
        layout.addSpacerItem(
            QSpacerItem(20, 12, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # ── footer ───────────────────────────────────────────────
        footer = QLabel("By signing in, you agree to our Terms of Service")
        footer.setObjectName("authFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        outer_layout.addWidget(self.container)

        # ── apply stylesheet ─────────────────────────────────────
        self._apply_styles()

    def _create_device_login_frame(self) -> QFrame:
        """Create the device login card."""
        frame = QFrame()
        frame.setObjectName("authDeviceCard")

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 18, 20, 18)

        header = QLabel("Device Login")
        header.setObjectName("authDeviceHeader")
        layout.addWidget(header)

        device_id_label = QLabel(
            f"Device ID: {self.session_manager.device_fingerprint_short}"
        )
        device_id_label.setObjectName("authDeviceId")
        layout.addWidget(device_id_label)

        self.device_login_btn = QPushButton("Login with this device")
        self.device_login_btn.setObjectName("authDeviceLoginBtn")
        self.device_login_btn.setMinimumHeight(42)
        self.device_login_btn.setCursor(Qt.PointingHandCursor)
        self.device_login_btn.clicked.connect(self._on_device_login)
        layout.addWidget(self.device_login_btn)

        info = QLabel("First time? This device will be registered automatically.")
        info.setObjectName("authDeviceInfo")
        info.setWordWrap(True)
        layout.addWidget(info)

        return frame

    # ── stylesheet ───────────────────────────────────────────────
    def _apply_styles(self):
        """Apply the VoxelCraft theme stylesheet."""
        self.setStyleSheet(f"""
            /* ── main card ─────────────────────────────────── */
            #authMainCard {{
                background-color: {self.BG_DARK};
                border: 1px solid {self.BORDER};
                border-radius: 16px;
            }}
            
            /* ── close button ──────────────────────────────── */
            #authCloseBtn {{
                background-color: transparent;
                color: {self.TEXT_MUTED};
                border: none;
                border-radius: 15px;
                font-size: 15px;
                font-weight: bold;
            }}
            #authCloseBtn:hover {{
                background-color: {self.BG_CARD};
                color: {self.DANGER};
            }}
            
            /* ── title / subtitle ──────────────────────────── */
            #authTitle {{
                color: {self.TEXT_PRIMARY};
                font-size: 22px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
            #authSubtitle {{
                color: {self.TEXT_SECONDARY};
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            
            /* ── divider ───────────────────────────────────── */
            #authDividerLine {{
                background-color: {self.BORDER};
                max-height: 1px;
                border: none;
            }}
            #authDividerText {{
                color: {self.TEXT_MUTED};
                font-size: 12px;
                background: transparent;
                border: none;
            }}
            
            /* ── device login card ─────────────────────────── */
            #authDeviceCard {{
                background-color: {self.BG_CARD};
                border: 1px solid {self.BORDER};
                border-radius: 12px;
            }}
            #authDeviceHeader {{
                font-size: 16px;
                font-weight: bold;
                color: {self.TEXT_PRIMARY};
                background: transparent;
                border: none;
            }}
            #authDeviceId {{
                color: {self.TEXT_SECONDARY};
                font-size: 13px;
                background: transparent;
                border: none;
            }}
            #authDeviceLoginBtn {{
                background-color: {self.ACCENT};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }}
            #authDeviceLoginBtn:hover {{
                background-color: {self.ACCENT_HOVER};
            }}
            #authDeviceLoginBtn:pressed {{
                background-color: {self.ACCENT_PRESS};
            }}
            #authDeviceLoginBtn:disabled {{
                background-color: {self.BORDER};
                color: {self.TEXT_MUTED};
            }}
            #authDeviceInfo {{
                color: {self.TEXT_MUTED};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
            
            /* ── Google button ─────────────────────────────── */
            #authGoogleBtn {{
                background-color: {self.GOOGLE_BG};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }}
            #authGoogleBtn:hover {{
                background-color: {self.GOOGLE_HOVER};
            }}
            #authGoogleBtn:pressed {{
                background-color: {self.GOOGLE_PRESS};
            }}
            #authGoogleBtn:disabled {{
                background-color: {self.BORDER};
                color: {self.TEXT_MUTED};
            }}
            
            /* ── GitHub button ─────────────────────────────── */
            #authGithubBtn {{
                background-color: {self.GITHUB_BG};
                color: #ffffff;
                border: 1px solid {self.BORDER};
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }}
            #authGithubBtn:hover {{
                background-color: {self.GITHUB_HOVER};
                border: 1px solid {self.BORDER_HOVER};
            }}
            #authGithubBtn:pressed {{
                background-color: {self.GITHUB_PRESS};
            }}
            #authGithubBtn:disabled {{
                background-color: {self.BORDER};
                color: {self.TEXT_MUTED};
            }}
            
            /* ── footer ────────────────────────────────────── */
            #authFooter {{
                color: {self.TEXT_MUTED};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)

    # ── event handlers ───────────────────────────────────────────
    def _on_device_login(self):
        """Handle device login button click."""
        self.device_login_btn.setEnabled(False)
        self.device_login_btn.setText("Logging in...")

        try:
            result = self.session_manager.login_with_device()

            if result.get("success"):
                QMessageBox.information(
                    self,
                    "Success",
                    f"Logged in successfully!\n\n"
                    f"Credits: {result.get('credits', 0)}\n"
                    f"Trial remaining: {result.get('trial_remaining', 0)}",
                )
                self.accept()
            elif result.get("needs_registration"):
                reply = QMessageBox.question(
                    self,
                    "Register Device",
                    "This device is not registered. Would you like to register it?\n\n"
                    f"You have {result.get('trial_remaining', 1)} free trial generation(s).",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )

                if reply == QMessageBox.Yes:
                    reg_result = self.session_manager.register_device(None)

                    if reg_result.get("success"):
                        QMessageBox.information(
                            self,
                            "Success",
                            "Device registered successfully!\n\n"
                            f"You have {self.session_manager.trial_remaining} free trial.",
                        )
                        self.accept()
                    else:
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Registration failed: {reg_result.get('error', reg_result.get('message', 'Unknown error'))}",
                        )
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Login failed: {result.get('error', result.get('message', 'Unknown error'))}",
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        finally:
            self.device_login_btn.setEnabled(True)
            self.device_login_btn.setText("Login with this device")

    def _on_google_login(self):
        """Handle Google OAuth login."""
        # Check if device is already registered
        from core import server_auth
        from core.supabase_client import get_supabase

        device_status = server_auth.check_device_server(
            self.session_manager.device_fingerprint
        )

        device_registered = device_status.get("registered", False)

        # Get trial_used from registered_devices table if available
        device_trial_used = 0
        if device_registered:
            try:
                sb = get_supabase()
                device_record = (
                    sb.table("registered_devices")
                    .select("trial_used")
                    .eq("device_fingerprint", self.session_manager.device_fingerprint)
                    .execute()
                )
                if device_record.data:
                    device_trial_used = device_record.data[0].get("trial_used", 0)
            except Exception as e:
                print(f"Error getting device trial info: {e}")
                device_trial_used = device_status.get("trial_used", 0)

        # Check if this device already used trial
        if device_registered and device_trial_used > 0:
            reply = QMessageBox.question(
                self,
                "Device Already Used Trial",
                "This device has already used its free trial with device registration.\n\n"
                f"Trial used: {device_trial_used}\n\n"
                "You can still sign in with Google to link your account, but you will NOT get another free trial.\n\n"
                "Do you want to continue with Google sign in?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
        elif device_registered:
            reply = QMessageBox.question(
                self,
                "Device Already Registered",
                "This device is already registered with device login.\n\n"
                "You can sign in with Google to link your account.\n\n"
                "Do you want to continue with Google sign in?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.No:
                return

        self._start_oauth("google")

    def _on_github_login(self):
        """Handle GitHub OAuth login."""
        # Check if device is already registered
        from core import server_auth
        from core.supabase_client import get_supabase

        device_status = server_auth.check_device_server(
            self.session_manager.device_fingerprint
        )

        device_registered = device_status.get("registered", False)

        # Get trial_used from registered_devices table if available
        device_trial_used = 0
        if device_registered:
            try:
                sb = get_supabase()
                device_record = (
                    sb.table("registered_devices")
                    .select("trial_used")
                    .eq("device_fingerprint", self.session_manager.device_fingerprint)
                    .execute()
                )
                if device_record.data:
                    device_trial_used = device_record.data[0].get("trial_used", 0)
            except Exception as e:
                print(f"Error getting device trial info: {e}")
                device_trial_used = device_status.get("trial_used", 0)

        # Check if this device already used trial
        if device_registered and device_trial_used > 0:
            reply = QMessageBox.question(
                self,
                "Device Already Used Trial",
                "This device has already used its free trial with device registration.\n\n"
                f"Trial used: {device_trial_used}\n\n"
                "You can still sign in with GitHub to link your account, but you will NOT get another free trial.\n\n"
                "Do you want to continue with GitHub sign in?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
        elif device_registered:
            reply = QMessageBox.question(
                self,
                "Device Already Registered",
                "This device is already registered with device login.\n\n"
                "You can sign in with GitHub to link your account.\n\n"
                "Do you want to continue with GitHub sign in?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.No:
                return

        self._start_oauth("github")

    def _start_oauth(self, provider: str):
        """Start OAuth flow for the given provider."""
        self.google_btn.setEnabled(False)
        self.github_btn.setEnabled(False)

        callback_port = 43210
        redirect_uri = f"http://127.0.0.1:{callback_port}/auth/callback"

        try:
            from core.supabase_client import get_supabase

            client = get_supabase()
            if not client:
                raise Exception("Could not initialize Supabase client")

            # Get OAuth URL directly to pass the redirect_to parameter
            res = client.auth.sign_in_with_oauth(
                {"provider": provider, "options": {"redirect_to": redirect_uri}}
            )

            # Get the code_verifier from the client's storage for PKCE
            code_verifier = client.auth._storage.get_item(
                f"{client.auth._storage_key}-code-verifier"
            )

            if res and hasattr(res, "url"):
                QMessageBox.information(
                    self,
                    "Complete Sign In",
                    f"A browser window will open for {provider.capitalize()} sign in.\n\n"
                    "Please complete the authentication in your browser.\n\n"
                    f"IMPORTANT: You MUST whitelist this exact URL in your Supabase Dashboard -> Authentication -> URL Configuration -> Redirect URLs:\n\n{redirect_uri}",
                )

                # Start callback server thread
                self.oauth_thread = OAuthCallbackThread(
                    provider, res.url, port=callback_port, code_verifier=code_verifier
                )
                self.oauth_thread.callback_received.connect(self._on_oauth_success)
                self.oauth_thread.error_occurred.connect(self._on_oauth_error)
                self.oauth_thread.start()
            else:
                raise Exception("Failed to get OAuth URL from Supabase.")

        except Exception as e:
            self._on_oauth_error(f"OAuth initiation error: {str(e)}")

    def _on_oauth_success(self, tokens: dict):
        """Handle successfully received OAuth tokens."""
        from core.supabase_client import get_supabase
        from core import server_auth

        client = get_supabase()

        try:
            access_token = tokens.get("access_token", [None])[0]
            refresh_token = tokens.get("refresh_token", [None])[0]

            if access_token and refresh_token:
                # Set session in Supabase client
                client.auth.set_session(access_token, refresh_token)

                user = client.auth.get_user()
                if user and user.user:
                    user_id = str(user.user.id)
                    email = user.user.email
                    username = email.split("@")[0] if email else "oauth_user"

                    # Make sure the user exists in our web_users and user_credits tables
                    try:
                        from core import credit_manager
                        from core.supabase_client import get_supabase

                        sb = get_supabase()

                        # Check if device already used trial
                        device_trial_used = 0
                        device_record = (
                            sb.table("registered_devices")
                            .select("trial_used")
                            .eq(
                                "device_fingerprint",
                                self.session_manager.device_fingerprint,
                            )
                            .execute()
                        )
                        if device_record.data:
                            device_trial_used = device_record.data[0].get(
                                "trial_used", 0
                            )

                        # If device already used trial, don't give new trial
                        new_user_trial = 0 if device_trial_used > 0 else 1

                        # Check if user exists in web_users
                        existing_user = (
                            sb.table("web_users")
                            .select("id")
                            .eq("id", user_id)
                            .execute()
                        )

                        if not existing_user.data:
                            # Create user in web_users - trial depends on device usage
                            user_data = {
                                "id": user_id,
                                "username": username,
                                "email": email,
                                "trial_remaining": new_user_trial,
                                "trial_used": 0,
                                "password_hash": None # Explicitly set to None for OAuth users
                            }
                            
                            try:
                                sb.table("web_users").insert(user_data).execute()
                            except Exception as sync_err:
                                # If it fails because ID already exists (race condition or previous partial sync)
                                # we try to continue. 
                                if "already exists" not in str(sync_err).lower():
                                    raise sync_err

                        # Check if user exists in user_credits
                        existing_credits = (
                            sb.table("user_credits")
                            .select("id")
                            .eq("user_id", user_id)
                            .execute()
                        )

                        if not existing_credits.data:
                            # Initialize credit balance for user
                            sb.table("user_credits").insert(
                                {
                                    "user_id": user_id,
                                    "credits_balance": 0,
                                    "total_purchased": 0,
                                    "total_used": 0,
                                }
                            ).execute()

                        # Get the balance after ensuring user exists
                        balance_info = credit_manager.get_user_balance(
                            user_id, self.session_manager.device_fingerprint
                        )
                    except Exception as e:
                        print(f"Error syncing OAuth user: {e}")
                        # Don't just set default, if it's a DB error we should probably tell the user
                        # However, for now we keep the fallback but log it properly
                        balance_info = {
                            "trial_remaining": new_user_trial,
                            "trial_used": 0,
                            "credits_balance": 0,
                        }
                        
                        # Re-raise if it's a fatal constraint error we haven't fixed
                        if "violates not-null constraint" in str(e):
                            raise e

                    # Login successful! Now set the SessionManager session
                    from core.session_manager import UserSession

                    # Try linking device
                    try:
                        server_auth.register_device_server(
                            self.session_manager.device_fingerprint,
                            "",
                            f"Desktop App ({self.session_manager.device_fingerprint_short})",
                        )
                    except Exception as ex:
                        print(f"Failed to link device after oauth: {ex}")

                    # NEW: Explicitly link this user to the device in the database if not already
                    try:
                        from core.supabase_client import get_supabase as get_sb_client
                        sb_cl = get_sb_client()
                        if sb_cl:
                            sb_cl.table("registered_devices").update({
                                "user_id": user_id,
                                "is_registered": True
                            }).eq("device_fingerprint", self.session_manager.device_fingerprint).execute()
                            print(f"Successfully linked device {self.session_manager.device_fingerprint_short} to user {user_id}")
                    except Exception as le:
                        print(f"Failed to explicitly link device: {le}")

                    # Login successful! Now set the SessionManager session
                    from core.session_manager import UserSession
                    
                    provider = "oauth"
                    if hasattr(self, 'oauth_thread') and self.oauth_thread:
                        provider = self.oauth_thread.provider
                    
                    self.session_manager._session = UserSession(
                        user_id=user_id,
                        username=username,
                        email=email,
                        device_fingerprint=self.session_manager.device_fingerprint,
                        credits_balance=balance_info.get("credits_balance", 0),
                        trial_remaining=balance_info.get("trial_remaining", 0),
                        trial_used=balance_info.get("trial_used", 0),
                        is_authenticated=True,
                        auth_method=provider
                    )
                    
                    # Save session for persistence (Auto Sign-in)
                    self.session_manager.save_session()
                    
                    self.session_manager._notify_session_change()

                    QMessageBox.information(
                        self,
                        "Success",
                        f"Successfully logged in as {email}!\n\nCredits: {balance_info.get('credits_balance', 0)}",
                    )
                    self.accept()
                else:
                    self._on_oauth_error("Failed to retrieve user data from session.")
            else:
                self._on_oauth_error("Tokens not found in the callback.")
        except Exception as e:
            self._on_oauth_error(f"Error establishing session: {str(e)}")
        finally:
            self.google_btn.setEnabled(True)
            self.github_btn.setEnabled(True)

    def _on_oauth_error(self, error: str):
        """Handle OAuth error."""
        QMessageBox.critical(self, "OAuth Error", error)
        self.google_btn.setEnabled(True)
        self.github_btn.setEnabled(True)

    # ── window dragging ──────────────────────────────────────────
    def mousePressEvent(self, event):
        """Enable window dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle window dragging."""
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Reset drag position."""
        self._drag_pos = None

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.oauth_thread and self.oauth_thread.isRunning():
            self.oauth_thread.stop()
            self.oauth_thread.wait()
        super().closeEvent(event)
