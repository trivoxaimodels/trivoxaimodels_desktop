"""
Profile Dialog for Desktop App

Shows user profile information, credits, trial balance, and allows logout.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QWidget, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from typing import Optional
import os

from core.session_manager import get_session_manager
from core.user_history_manager import get_user_profile
from core.logger import get_logger

logger = get_logger(__name__)


class ProfileDialog(QDialog):
    """Dialog showing user profile information."""
    
    # Signal emitted when user logs out
    logout_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile - Voxel Craft")
        self.setMinimumSize(450, 500)
        self._session_manager = get_session_manager()
        
        if not self._session_manager or not self._session_manager.is_authenticated():
            QMessageBox.warning(self, "Not Logged In", "Please log in to view profile.")
            self.reject()
            return
        
        self._init_ui()
        self._load_profile()
    
    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("👤 Your Profile")
        header.setStyleSheet("font-size: 20px; font-weight: bold; padding: 15px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Profile Card
        self.profile_card = QFrame()
        self.profile_card.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.profile_card.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin: 10px;
            }
        """)
        
        card_layout = QVBoxLayout(self.profile_card)
        
        # Avatar/Initial
        self.avatar_label = QLabel()
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                color: white;
                background-color: #6c5ce7;
                border-radius: 50px;
                min-width: 100px;
                min-height: 100px;
                padding: 20px;
            }
        """)
        card_layout.addWidget(self.avatar_label, alignment=Qt.AlignCenter)
        
        # Username
        self.username_label = QLabel()
        self.username_label.setAlignment(Qt.AlignCenter)
        self.username_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #2d3436;")
        card_layout.addWidget(self.username_label)
        
        # Email
        self.email_label = QLabel()
        self.email_label.setAlignment(Qt.AlignCenter)
        self.email_label.setStyleSheet("font-size: 14px; color: #636e72;")
        card_layout.addWidget(self.email_label)
        
        # Auth method badge
        self.auth_method_label = QLabel()
        self.auth_method_label.setAlignment(Qt.AlignCenter)
        self.auth_method_label.setStyleSheet("""
            QLabel {
                background-color: #00b894;
                color: white;
                padding: 5px 15px;
                border-radius: 15px;
                font-size: 12px;
                margin-top: 5px;
            }
        """)
        card_layout.addWidget(self.auth_method_label, alignment=Qt.AlignCenter)
        
        layout.addWidget(self.profile_card)
        
        # Credits Section
        credits_frame = QFrame()
        credits_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        credits_frame.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border: 1px solid #dfe6e9;
                border-radius: 10px;
                padding: 15px;
                margin: 10px;
            }
        """)
        
        credits_layout = QGridLayout(credits_frame)
        
        # Credits balance
        credits_title = QLabel("💎 Credits Balance")
        credits_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        credits_layout.addWidget(credits_title, 0, 0)
        
        self.credits_label = QLabel()
        self.credits_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #6c5ce7;")
        self.credits_label.setAlignment(Qt.AlignRight)
        credits_layout.addWidget(self.credits_label, 0, 1)
        
        # Trial balance
        trial_title = QLabel("🎁 Trial Remaining")
        trial_title.setStyleSheet("font-size: 14px; color: #636e72;")
        credits_layout.addWidget(trial_title, 1, 0)
        
        self.trial_label = QLabel()
        self.trial_label.setStyleSheet("font-size: 16px; color: #00b894;")
        self.trial_label.setAlignment(Qt.AlignRight)
        credits_layout.addWidget(self.trial_label, 1, 1)
        
        # Trial used
        used_title = QLabel("Trial Used")
        used_title.setStyleSheet("font-size: 14px; color: #636e72;")
        credits_layout.addWidget(used_title, 2, 0)
        
        self.trial_used_label = QLabel()
        self.trial_used_label.setStyleSheet("font-size: 16px; color: #d63031;")
        self.trial_used_label.setAlignment(Qt.AlignRight)
        credits_layout.addWidget(self.trial_used_label, 2, 1)
        
        layout.addWidget(credits_frame)
        
        # Stats Section
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border: 1px solid #dfe6e9;
                border-radius: 10px;
                padding: 15px;
                margin: 10px;
            }
        """)
        
        stats_layout = QGridLayout(stats_frame)
        
        # Member since
        member_title = QLabel("📅 Member Since")
        member_title.setStyleSheet("font-size: 14px; color: #636e72;")
        stats_layout.addWidget(member_title, 0, 0)
        
        self.member_since_label = QLabel()
        self.member_since_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        stats_layout.addWidget(self.member_since_label, 0, 1)
        
        # User ID
        id_title = QLabel("🆔 User ID")
        id_title.setStyleSheet("font-size: 14px; color: #636e72;")
        stats_layout.addWidget(id_title, 1, 0)
        
        self.user_id_label = QLabel()
        self.user_id_label.setStyleSheet("font-size: 12px; font-family: monospace;")
        self.user_id_label.setWordWrap(True)
        stats_layout.addWidget(self.user_id_label, 1, 1)
        
        layout.addWidget(stats_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_profile)
        btn_layout.addWidget(refresh_btn)
        
        btn_layout.addStretch()
        
        # Logout button
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #d63031;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e17055;
            }
        """)
        logout_btn.clicked.connect(self._handle_logout)
        btn_layout.addWidget(logout_btn)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_profile(self):
        """Load profile data from session and database."""
        session = self._session_manager.get_session()
        if not session:
            return
        
        # Username
        username = session.username or session.email.split('@')[0] if session.email else "User"
        self.username_label.setText(username)
        
        # Avatar initial
        initial = username[0].upper() if username else "U"
        self.avatar_label.setText(initial)
        
        # Email
        email = session.email or "Not provided"
        self.email_label.setText(email)
        
        # Auth method
        auth_method = session.auth_method or "unknown"
        if auth_method == "device":
            auth_display = "Device Login"
        elif auth_method == "password":
            auth_display = "Password Login"
        elif auth_method == "google":
            auth_display = "Google OAuth"
        elif auth_method == "github":
            auth_display = "GitHub OAuth"
        else:
            auth_display = auth_method.title()
        self.auth_method_label.setText(f"✓ {auth_display}")
        
        # Credits
        credits = session.credits_balance or 0
        self.credits_label.setText(str(credits))
        
        # Trial
        trial = session.trial_remaining or 0
        self.trial_label.setText(str(trial))
        
        trial_used = session.trial_used or 0
        self.trial_used_label.setText(str(trial_used))
        
        # User ID
        user_id = session.user_id or "N/A"
        self.user_id_label.setText(user_id[:18] + "..." if len(user_id) > 18 else user_id)
        
        # Member since - try to get from database
        try:
            profile = get_user_profile(user_id)
            if profile:
                created_at = profile.get("created_at", "")
                if created_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        self.member_since_label.setText(dt.strftime("%B %d, %Y"))
                    except:
                        self.member_since_label.setText("N/A")
                else:
                    self.member_since_label.setText("N/A")
            else:
                self.member_since_label.setText("N/A")
        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            self.member_since_label.setText("N/A")
    
    def _handle_logout(self):
        """Handle logout button click."""
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("User requested logout from profile dialog")
            self.logout_requested.emit()
            self.accept()
            # Trigger logout in session manager
            if self._session_manager:
                self._session_manager.logout()


def show_profile_dialog(parent=None):
    """Show the profile dialog."""
    dialog = ProfileDialog(parent)
    dialog.exec()
