"""
Trivox Models Desktop Application - Entry Point
===============================================

Desktop application for 3D model generation from images.
Features:
  - Device fingerprint authentication
  - Google OAuth login
  - GitHub OAuth login
  - All cloud API providers (Tripo3D, Meshy, Neural4D, HItem3D)
  - Local TripoSR inference
  - Multi-angle processing
"""

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.auth_dialog import AuthDialog
from core.session_manager import SessionManager


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(ROOT)
    return os.path.join(base_path, relative_path)


def main():
    """Main entry point for the desktop application."""
    # Force PySide6 to use software OpenGL for QWebEngine compatibility on various drivers
    from PySide6.QtCore import Qt, QCoreApplication
    os.environ["QT_OPENGL"] = "software"
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    
    # Disable Chromium GPU acceleration to fix startup crashes on some machines
    # (Fixes "D3D11 smoke test failed" and EGL context errors)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing"
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Trivox Models")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Trivox Models")
    
    # Set application icon
    icon_path = get_resource_path("assets/logo/logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Load stylesheet
    styles_path = get_resource_path("ui/styles/styles.qss")
    if os.path.exists(styles_path):
        with open(styles_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    # Initialize session manager
    session_manager = SessionManager()
    
    # Initialize payment sync
    from core.payment_config_sync import initialize_payment_sync
    initialize_payment_sync()
    
    # If not authenticated via saved session, try automatic device login 
    if not session_manager.is_authenticated:
        # This will sign in with device fingerprint (the default flow)
        session_manager.login_with_device()
    
    # Only show authentication dialog if we're still not authenticated
    # or if the user needs to switch accounts (handled inside the app)
    if not session_manager.is_authenticated:
        auth_dialog = AuthDialog(session_manager)
        if auth_dialog.exec() != AuthDialog.Accepted:
            sys.exit(0)
    
    # Create and show main window
    main_window = MainWindow(session_manager)
    main_window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"FATAL ERROR during startup: {e}")
        traceback.print_exc()
        # Keep window open if possible
        input("Press Enter to exit...")
