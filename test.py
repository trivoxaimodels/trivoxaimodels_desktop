"""
Beautiful Login Page for VoxelCraft Desktop App
A standalone demonstration of a modern login interface
"""

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSpacerItem, QSizePolicy,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor


class LoginWindow(QMainWindow):
    """
    Beautiful login window with modern glassmorphism design.
    Features:
        - Glassmorphism effect
        - Smooth shadows and blur effects
        - Modern typography
        - Professional color scheme
    """
    
    def __init__(self):
        super().__init__()
        self.drag_pos = None
        self._setup_window()
        self._setup_ui()
        
    def _setup_window(self):
        """Setup window properties."""
        self.setWindowTitle("VoxelCraft - Sign In")
        self.setMinimumSize(1200, 700)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        
        # Center window on screen
        screen = QApplication.primaryScreen().availableGeometry()
        window_size = self.frameGeometry()
        window_size.moveCenter(screen.center())
        self.move(window_size.topLeft())
        
    def _setup_ui(self):
        """Setup the main UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left decorative panel with gradient
        left_panel = self._create_gradient_panel()
        main_layout.addWidget(left_panel, stretch=5)
        
        # Right panel - login form
        right_panel = self._create_login_panel()
        main_layout.addWidget(right_panel, stretch=5)
        
    def _create_gradient_panel(self) -> QWidget:
        """Create the left gradient panel with modern design."""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1e1b4b, stop:0.3 #312e81, stop:0.7 #4c1d95, stop:1 #7c3aed);
            }
        """)
        
        # Main layout
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(25)
        
        # App Logo Section
        logo_container = QWidget()
        logo_container.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #6366f1, stop:0.5 #8b5cf6, stop:1 #a855f7);
            border-radius: 20px;
            border: 2px solid rgba(255, 255, 255, 0.2);
        """)
        logo_container.setFixedSize(100, 100)
        
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        logo_label = QLabel("T")
        logo_font = QFont()
        logo_font.setPointSize(50)
        logo_font.setBold(True)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet("color: white;")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_layout.addWidget(logo_label)
        
        # Add shadow to logo
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(99, 102, 241, 200))
        shadow.setOffset(0, 4)
        logo_container.setGraphicsEffect(shadow)
        
        layout.addWidget(logo_container, 0, Qt.AlignCenter)
        
        # App Title
        title = QLabel("VoxelCraft")
        title_font = QFont()
        title_font.setPointSize(48)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white; letter-spacing: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, 0, Qt.AlignCenter)
        
        subtitle = QLabel("Transform Your Images into\nStunning 3D Models")
        subtitle.setFont(QFont("Segoe UI", 18))
        subtitle.setStyleSheet("color: rgba(255,255,255,0.8);")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle, 0, Qt.AlignCenter)
        
        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        
        # Feature highlights with icons
        features_data = [
            ("📷", "Upload multi-angle photos"),
            ("🎨", "AI-powered 3D generation"),
            ("✨", "High-quality mesh output"),
            ("🚀", "Fast processing")
        ]
        
        for icon, text in features_data:
            feature_widget = self._create_feature_item(icon, text)
            layout.addWidget(feature_widget)
        
        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        
        # Version info
        version = QLabel("Version 1.0.0")
        version.setFont(QFont("Segoe UI", 12))
        version.setStyleSheet("color: rgba(255,255,255,0.5);")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version, 0, Qt.AlignCenter)
        
        return panel
        
    def _create_feature_item(self, icon: str, text: str) -> QWidget:
        """Create a feature highlight item."""
        widget = QWidget()
        widget.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 12px;")
        
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(15)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        layout.addWidget(icon_label)
        
        text_label = QLabel(text)
        text_label.setFont(QFont("Segoe UI", 16))
        text_label.setStyleSheet("color: white;")
        layout.addWidget(text_label)
        
        layout.addStretch()
        
        return widget
        
    def _create_login_panel(self) -> QWidget:
        """Create the right login panel with glassmorphism."""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(60, 50, 60, 50)
        layout.setSpacing(20)
        
        # Header with close button
        header_layout = QHBoxLayout()
        
        header_layout.addStretch()
        
        # Minimize button
        minimize_btn = QPushButton("─")
        minimize_btn.setFixedSize(36, 36)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #64748b;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                color: #334155;
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(minimize_btn)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #fee2e2;
                color: #ef4444;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background: #fecaca;
                color: #dc2626;
            }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        # Welcome section
        welcome = QLabel("Welcome Back")
        welcome_font = QFont()
        welcome_font.setPointSize(42)
        welcome_font.setBold(True)
        welcome.setFont(welcome_font)
        welcome.setStyleSheet("color: #1e293b;")
        layout.addWidget(welcome)
        
        subtitle = QLabel("Sign in to access your 3D models")
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setStyleSheet("color: #64748b; margin-bottom: 30px;")
        layout.addWidget(subtitle)
        
        # Device Login Card
        device_card = self._create_device_login_card()
        layout.addWidget(device_card)
        
        # Divider with "or"
        divider_layout = QHBoxLayout()
        divider_layout.setSpacing(15)
        
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Plain)
        line1.setFixedHeight(1)
        line1.setStyleSheet("background: #e2e8f0;")
        
        or_label = QLabel("or continue with")
        or_label.setFont(QFont("Segoe UI", 13))
        or_label.setStyleSheet("color: #94a3b8;")
        
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Plain)
        line2.setFixedHeight(1)
        line2.setStyleSheet("background: #e2e8f0;")
        
        divider_layout.addWidget(line1)
        divider_layout.addWidget(or_label)
        divider_layout.addWidget(line2)
        
        layout.addLayout(divider_layout)
        
        # OAuth Buttons
        oauth_layout = QVBoxLayout()
        oauth_layout.setSpacing(12)
        
        # Google Button
        google_btn = self._create_oauth_button("Continue with Google", "#4285f4")
        google_btn.clicked.connect(self._on_google_login)
        oauth_layout.addWidget(google_btn)
        
        # GitHub Button
        github_btn = self._create_oauth_button("Continue with GitHub", "#24292e")
        github_btn.clicked.connect(self._on_github_login)
        oauth_layout.addWidget(github_btn)
        
        layout.addLayout(oauth_layout)
        
        # Spacer
        layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        
        # Footer
        footer = QLabel("By continuing, you agree to our Terms of Service\nand Privacy Policy")
        footer.setFont(QFont("Segoe UI", 12))
        footer.setStyleSheet("color: #94a3b8;")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)
        
        return panel
        
    def _create_device_login_card(self) -> QFrame:
        """Create the device login card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
            }
        """)
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 0.08))
        shadow.setOffset(0, 3)
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(18)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Header with icon
        header_layout = QHBoxLayout()
        
        icon_label = QLabel("💻")
        icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        header_layout.addWidget(icon_label)
        
        header = QLabel("Device Login")
        header.setFont(QFont("Segoe UI", 20, QFont.Bold))
        header.setStyleSheet("color: #1e293b;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Device ID
        device_id_layout = QHBoxLayout()
        
        id_label = QLabel("Device ID:")
        id_label.setFont(QFont("Segoe UI", 13))
        id_label.setStyleSheet("color: #64748b;")
        device_id_layout.addWidget(id_label)
        
        device_id = QLabel("TRIVOX-8X7Y2-K9M3N")
        device_id.setFont(QFont("Consolas", 13))
        device_id.setStyleSheet("color: #334155; background: #f8fafc; padding: 5px 10px; border-radius: 6px;")
        device_id_layout.addWidget(device_id)
        
        device_id_layout.addStretch()
        
        layout.addLayout(device_id_layout)
        
        # Login Button
        login_btn = QPushButton("Sign In with This Device")
        login_btn.setMinimumHeight(55)
        login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #6366f1, stop:1 #8b5cf6);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #4f46e5, stop:1 #7c3aed);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #4338ca, stop:1 #6d28d9);
            }
        """)
        login_btn.clicked.connect(self._on_device_login)
        
        # Add shadow to button
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(15)
        btn_shadow.setColor(QColor(99, 102, 241, 100))
        btn_shadow.setOffset(0, 3)
        login_btn.setGraphicsEffect(btn_shadow)
        
        layout.addWidget(login_btn)
        
        # Info
        info = QLabel("✨ First time? Your device will be registered automatically with 1 free trial.")
        info.setFont(QFont("Segoe UI", 12))
        info.setStyleSheet("color: #64748b; background: #f8fafc; padding: 10px; border-radius: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        return card
        
    def _create_oauth_button(self, text: str, color: str) -> QPushButton:
        """Create a styled OAuth button."""
        btn = QPushButton(f"  {text}")
        btn.setMinimumHeight(55)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                text-align: left;
                padding-left: 20px;
            }}
            QPushButton:hover {{
                background: {color};
                opacity: 0.9;
            }}
            QPushButton:pressed {{
                background: {color};
                opacity: 0.8;
            }}
        """)
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 0.15))
        shadow.setOffset(0, 2)
        btn.setGraphicsEffect(shadow)
        
        return btn
        
    def _on_device_login(self):
        """Handle device login."""
        print("Device login clicked")
        
    def _on_google_login(self):
        """Handle Google OAuth login."""
        print("Google login clicked")
        
    def _on_github_login(self):
        """Handle GitHub OAuth login."""
        print("GitHub login clicked")
        
    def mousePressEvent(self, event):
        """Handle window drag."""
        if event.button() == Qt.LeftButton and event.position().y() < 50:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle window movement."""
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        """Release drag on mouse up."""
        self.drag_pos = None


def main():
    """Main function to run the login window."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show login window
    login_window = LoginWindow()
    login_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
