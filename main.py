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

# Force software OpenGL for Qt WebEngine compatibility on various drivers and VMs
os.environ["QT_OPENGL"] = "software"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --disable-gpu-compositing --disable-gpu-sandbox --use-gl=swiftshader --enable-webgl=0 --ignore-gpu-blocklist --no-sandbox"
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

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


def register_uri_scheme():
    """Register voxelcraft:// URI scheme in Windows Registry to allow web app deep-linking."""
    if sys.platform != 'win32':
        return
        
    try:
        import winreg
        key_path = r"Software\Classes\voxelcraft"
        
        # Open or create the voxelcraft classes key
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:VoxelCraft Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            
            with winreg.CreateKey(key, r"shell\open\command") as cmd_key:
                if getattr(sys, 'frozen', False):
                    # PyInstaller bundle
                    app_path = f'"{sys.executable}"'
                else:
                    # Dev script
                    app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                    
                # The browser will pass the URI as the first argument
                winreg.SetValue(cmd_key, "", winreg.REG_SZ, f'{app_path} "%1"')
                
    except Exception as e:
        print(f"Could not register URI scheme: {e}")


def main():
    """Main entry point for the desktop application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Voxel Craft")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Voxel Craft")
    
    # Establish single instance mechanism
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    app_id = "VoxelCraftApp_SingleInstance"
    
    socket = QLocalSocket()
    socket.connectToServer(app_id)
    if socket.waitForConnected(500):
        # A previous instance is already running
        msg = "URI:" + (" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "activate")
        socket.write(msg.encode("utf-8"))
        socket.waitForBytesWritten(500)
        sys.exit(0)
    
    # We are the primary instance
    server = QLocalServer()
    QLocalServer.removeServer(app_id)
    server.listen(app_id)
    
    def on_new_connection():
        conn = server.nextPendingConnection()
        if conn.waitForReadyRead(500):
            msg = conn.readAll().data().decode("utf-8")
            if hasattr(app, 'main_window') and app.main_window:
                # Force window to foreground
                mw = app.main_window
                mw.setWindowState(mw.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
                mw.raise_()
                mw.activateWindow()
    
    server.newConnection.connect(on_new_connection)
    
    # Set application icon
    icon_path = get_resource_path("assets/logo/logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    # Register URI deep linking scheme
    register_uri_scheme()
    
    # Load stylesheet
    styles_path = get_resource_path("ui/styles/styles.qss")
    if os.path.exists(styles_path):
        with open(styles_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    # Initialize session manager
    print("DEBUG: Initializing session manager...", flush=True)
    session_manager = SessionManager()
    print("DEBUG: Session manager initialized", flush=True)
    
    # Initialize payment sync
    print("DEBUG: Initializing payment sync...", flush=True)
    from core.payment_config_sync import initialize_payment_sync
    initialize_payment_sync()
    print("DEBUG: Payment sync initialized", flush=True)
    
    # If not authenticated via saved session, try automatic device login 
    print("DEBUG: Checking authentication...", flush=True)
    if not session_manager.is_authenticated:
        print("DEBUG: Not authenticated, attempting device login...", flush=True)
        # This will sign in with device fingerprint (the default flow)
        session_manager.login_with_device()
    print("DEBUG: Authentication check complete", flush=True)
    
    # Only show authentication dialog if we're still not authenticated
    # or if the user needs to switch accounts (handled inside the app)
    if not session_manager.is_authenticated:
        print("DEBUG: Showing auth dialog...", flush=True)
        auth_dialog = AuthDialog(session_manager)
        if auth_dialog.exec() != AuthDialog.Accepted:
            sys.exit(0)
    print("DEBUG: Auth dialog complete", flush=True)
    
    # Create and show main window
    print("DEBUG: Creating main window...", flush=True)
    try:
        main_window = MainWindow(session_manager)
        app.main_window = main_window
        main_window.show()
    except Exception as e:
        import traceback
        print(f"ERROR creating main window: {e}", flush=True)
        traceback.print_exc()
        # Try to show error in a simple dialog
        from PySide6.QtWidgets import QMessageBox
        error_dialog = QMessageBox()
        error_dialog.setWindowTitle("Error")
        error_dialog.setText(f"Failed to create main window: {e}\n\nThe app may not work properly in this environment.")
        error_dialog.exec()
    print("DEBUG: Main window shown", flush=True)
    
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
