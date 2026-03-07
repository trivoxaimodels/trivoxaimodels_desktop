"""
Main Window for Image → 3D Pro Desktop Application

UI Design matches the specification in UI_DESIGN_SPECIFICATION.md
- Dark theme with sidebar layout
- All backend functionality preserved from existing core modules
"""

import os
import sys
import platform
import psutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGroupBox,
    QComboBox,
    QProgressBar,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QStackedWidget,
    QSizePolicy,
    QSpacerItem,
    QGridLayout,
    QScrollArea,
    QCheckBox,
    QDialog,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QSettings, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import (
    QPixmap,
    QFont,
    QDragEnterEvent,
    QDropEvent,
    QColor,
    QFocusEvent,
)

# Add parent directory to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.session_manager import SessionManager
from core.unified_pipeline import run_pipeline_async, get_available_models
from core.credit_manager import (
    get_user_balance,
    can_generate,
    deduct_credits,
    mark_generation_complete,
    CREDIT_COSTS,
)


class CompletionDialog(QDialog):
    """
    Beautiful completion modal shown after 3D model generation.
    Matches the web app's design with format cards, Open/Save buttons.
    """

    def __init__(self, parent, result: dict, is_trial: bool = False):
        super().__init__(parent)
        self.result = result
        self.is_trial = is_trial
        self.setWindowTitle("Generation Complete")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(640)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self):
        # Outer layout for shadow margin
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        # Main container with rounded corners
        container = QFrame()
        container.setObjectName("completionContainer")
        container.setStyleSheet("""
            #completionContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f172a, stop:1 #0c1222);
                border: 1px solid #334155;
                border-radius: 16px;
            }
        """)

        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setXOffset(0)
        shadow.setYOffset(12)
        shadow.setColor(QColor(0, 0, 0, 180))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setSpacing(0)
        layout.setContentsMargins(32, 32, 32, 32)

        # ── Celebration Emoji ──
        emoji = QLabel("🎉")
        emoji.setAlignment(Qt.AlignCenter)
        emoji.setStyleSheet(
            "font-size: 52px; background: transparent; margin-bottom: 8px;"
        )
        layout.addWidget(emoji)

        # ── Title ──
        if self.is_trial:
            title = QLabel("First Generation Complete!")
        else:
            title = QLabel("Model Generated Successfully!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: #f8fafc;
            background: transparent;
            margin-bottom: 4px;
        """)
        layout.addWidget(title)

        # ── Subtitle ──
        if self.is_trial:
            subtitle_text = (
                "Your first 3D model is FREE! Select a format below to open or save it."
            )
        else:
            subtitle_text = (
                "Your 3D model is ready. Select a format below to open or download it."
            )
        subtitle = QLabel(subtitle_text)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #94a3b8;
            background: transparent;
            margin-bottom: 20px;
            line-height: 1.5;
        """)
        layout.addWidget(subtitle)

        # ── Format Cards Grid ──
        format_defs = [
            ("obj", "OBJ", "🧊", "#3b82f6"),
            ("glb", "GLB", "🌐", "#10b981"),
            ("stl", "STL", "🏗️", "#f59e0b"),
            ("fbx", "FBX", "📐", "#8b5cf6"),
            ("usdz", "USDZ", "📱", "#ec4899"),
        ]

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        has_formats = False
        for fmt_key, fmt_label, fmt_icon, fmt_color in format_defs:
            if self.result.get(fmt_key):
                has_formats = True
                card = self._create_format_card(
                    fmt_key, fmt_label, fmt_icon, fmt_color, self.result[fmt_key]
                )
                cards_layout.addWidget(card)

        if has_formats:
            layout.addLayout(cards_layout)
        else:
            no_files = QLabel("No output files generated.")
            no_files.setAlignment(Qt.AlignCenter)
            no_files.setStyleSheet(
                "color: #64748b; font-size: 13px; background: transparent; margin: 16px 0;"
            )
            layout.addWidget(no_files)

        # ── Spacer ──
        layout.addSpacing(24)

        # ── Trial upsell text ──
        if self.is_trial:
            upsell = QLabel("💎 Buy credits to generate more models!")
            upsell.setAlignment(Qt.AlignCenter)
            upsell.setStyleSheet("""
                font-size: 13px;
                color: #60a5fa;
                background: transparent;
                margin-bottom: 16px;
                font-weight: 600;
            """)
            layout.addWidget(upsell)

        # ── Action Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setAlignment(Qt.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                border: 1px solid #334155;
                background: #1e293b;
                color: #e2e8f0;
                font-size: 15px;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #334155;
                border-color: #475569;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        buy_btn = None
        if self.is_trial:
            buy_btn = QPushButton("💳 Buy Credits")
            buy_btn.setStyleSheet("""
                QPushButton {
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: 600;
                    border: none;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #22c55e, stop:1 #16a34a);
                    color: white;
                    font-size: 15px;
                    min-width: 130px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #16a34a, stop:1 #15803d);
                }
            """)
            buy_btn.setCursor(Qt.PointingHandCursor)
            buy_btn.clicked.connect(self._on_buy_credits)
            btn_layout.addWidget(buy_btn)

        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _create_format_card(self, fmt_key, fmt_label, fmt_icon, fmt_color, file_path):
        """Create a single format card with icon, label, file name, Open and Save buttons."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 0px;
            }}
            QFrame:hover {{
                border-color: {fmt_color};
                background: #1e293b;
            }}
        """)
        card.setMinimumWidth(120)
        card.setMaximumWidth(160)

        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 14, 12, 14)

        # Icon
        icon_lbl = QLabel(fmt_icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")
        layout.addWidget(icon_lbl)

        # Format label
        name_lbl = QLabel(fmt_label)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(f"""
            font-weight: 700;
            color: {fmt_color};
            font-size: 15px;
            background: transparent;
        """)
        layout.addWidget(name_lbl)

        # Filename
        filename = Path(file_path).name if file_path else "—"
        file_lbl = QLabel(filename)
        file_lbl.setAlignment(Qt.AlignCenter)
        file_lbl.setStyleSheet(
            "font-size: 10px; color: #64748b; background: transparent;"
        )
        file_lbl.setToolTip(filename)
        file_lbl.setMaximumWidth(140)
        layout.addWidget(file_lbl)

        layout.addSpacing(4)

        # Open button
        open_btn = QPushButton("👁️ Open")
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: #334155;
                border: 1px solid #475569;
                color: white;
                padding: 7px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {fmt_color};
                border-color: {fmt_color};
            }}
        """)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda: self._open_file(file_path))
        layout.addWidget(open_btn)

        # Save button
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #334155;
                color: #94a3b8;
                padding: 7px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #60a5fa;
                color: #e2e8f0;
            }
        """)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(lambda: self._save_file(file_path, fmt_label))
        layout.addWidget(save_btn)

        return card

    def _open_file(self, file_path):
        """Open file with system default application."""
        import subprocess

        try:
            if os.name == "nt":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path])
            else:
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")

    def _save_file(self, source_path, fmt_label):
        """Save file to user-chosen location."""
        import shutil

        default_name = Path(source_path).name
        ext = Path(source_path).suffix
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {fmt_label}",
            default_name,
            f"{fmt_label} Files (*{ext});;All Files (*)",
        )
        if file_path:
            try:
                shutil.copy2(source_path, file_path)
                QMessageBox.information(
                    self, "Saved", f"File saved successfully to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not save file: {e}")

    def _on_buy_credits(self):
        """Open buy credits dialog."""
        self.accept()
        parent = self.parent()
        if hasattr(parent, "_on_buy_credits"):
            parent._on_buy_credits()


class GenerationWorker(QThread):
    """Worker thread for 3D model generation."""

    progress = Signal(int)
    status = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        input_data: str,  # image_path or prompt
        model: str,  # "local" or "cloud"
        resolution: str,  # e.g., "1024", "1536", "1536pro"
        api_model: str = None,
        output_formats: list = None,
        quality: str = "standard",
        mode: str = "image",  # "image" or "text"
        negative_prompt: str = "",
    ):
        super().__init__()
        self.input_data = input_data
        self.model = model
        self.resolution = resolution
        self.api_model = api_model
        self.output_formats = output_formats or ["obj", "stl", "glb"]
        self.quality = quality
        self.mode = mode
        self.negative_prompt = negative_prompt
        self._is_running = True

    def run(self):
        try:
            from core.unified_pipeline import run_pipeline_async
            from config.settings import get_output_dir

            self.status.emit("Initializing...")

            # Determine if using API or local
            use_api = self.model == "cloud"

            # Get output directory
            output_dir = str(get_output_dir())

            # Progress callback to route pipeline progress to UI signals
            def progress_callback(stage, pct, msg):
                self.progress.emit(int(pct))
                self.status.emit(msg)

            self.progress.emit(5)
            if self.mode == "text":
                self.status.emit("Starting text-to-3D...")
            else:
                self.status.emit("Processing image...")

            # Run the pipeline
            if self.mode == "text":
                from core.unified_pipeline import run_text_pipeline_async

                result = asyncio.run(
                    run_text_pipeline_async(
                        self.input_data,
                        negative_prompt=self.negative_prompt,
                        api_model=self.api_model,
                        api_resolution=self.resolution,
                        api_format=",".join(self.output_formats),
                        output_dir=output_dir,
                        progress_callback=progress_callback,
                    )
                )
            elif use_api:
                result = asyncio.run(
                    run_pipeline_async(
                        self.input_data,
                        use_api=True,
                        api_model=self.api_model,
                        api_resolution=self.resolution,
                        api_format=",".join(self.output_formats),
                        output_dir=output_dir,
                        quality="standard",
                        progress_callback=progress_callback,
                    )
                )
            else:
                result = asyncio.run(
                    run_pipeline_async(
                        self.input_data,
                        use_api=False,
                        output_dir=output_dir,
                        quality=self.quality,
                        progress_callback=progress_callback,
                    )
                )

            # CHECK FOR ERRORS in result
            if result.get("error") or result.get("error_message"):
                error_msg = result.get("error") or result.get("error_message")
                self.error.emit(f"Generation failed: {error_msg}")
                return

            # Verify output files actually exist
            if not any(result.get(fmt) for fmt in ["obj", "stl", "glb"]):
                self.error.emit(
                    "Generation produced no output files. Check system requirements (open3d, torch)."
                )
                return

            self.progress.emit(100)
            self.status.emit("Complete!")
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False


class MainWindow(QMainWindow):
    """
    Main application window for Image → 3D Pro.

    Layout:
    - Left sidebar (280px): Logo, Device info, System info, Log Out, Quit
    - Main content: Source, Processing, Preview, Progress, Actions, Outputs, Activity Log
    """

    def __init__(self, session_manager: SessionManager):
        super().__init__()

        self.session_manager = session_manager
        self.selected_file: Optional[str] = None
        self.output_dir = Path.home() / "TrivoxModels" / "outputs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.worker: Optional[GenerationWorker] = None
        self.start_time: Optional[datetime] = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)

        # Current generation parameters
        self._current_model: str = "local"
        self._current_quality: str = "standard"

        self.setWindowTitle("Image → 3D Pro")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self._setup_ui()
        self._setup_connections()
        self._load_stylesheet()

        # Refresh credit balance after UI is setup
        self._refresh_credit_balance()

        # Force trial settings after window is shown
        QTimer.singleShot(100, self._enforce_trial_settings)

    def focusInEvent(self, event: QFocusEvent):
        """Refresh credits when window gains focus."""
        super().focusInEvent(event)
        # Refresh credits from database when window gains focus
        self._refresh_credit_balance()
        self._refresh_cloud_credit_display()

    def _setup_ui(self):
        """Setup the main window UI with sidebar + content layout."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout: Sidebar + Content
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left Sidebar (280px fixed)
        self.sidebar = self._create_sidebar()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setObjectName("sidebar")
        main_layout.addWidget(self.sidebar)

        # Main Content Area
        self.content_area = self._create_content_area()
        self.content_area.setObjectName("contentArea")
        main_layout.addWidget(self.content_area, 1)

    def _create_sidebar(self) -> QWidget:
        """Create the left sidebar with logo, device info, system info, and actions."""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        # Logo Section
        logo_widget = self._create_logo_section()
        layout.addWidget(logo_widget)

        # DEVICE Card
        device_card = self._create_device_card()
        layout.addWidget(device_card)

        # CREDIT Card
        self.credit_card = self._create_credit_card()
        layout.addWidget(self.credit_card)

        # SYSTEM Card
        system_card = self._create_system_card()
        layout.addWidget(system_card)

        # Spacer
        layout.addStretch(1)

        # Action Buttons
        actions_widget = self._create_sidebar_actions()
        layout.addWidget(actions_widget)

        return sidebar

    def _create_logo_section(self) -> QWidget:
        """Create the logo and title section."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        # Logo and Title
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        brain_icon = QLabel("🧠")
        brain_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(brain_icon)

        title_text = QLabel("Image → 3D Pro")
        title_text.setStyleSheet("font-size: 18px; font-weight: bold; color: #e2e8f0;")
        title_layout.addWidget(title_text)
        title_layout.addStretch()

        layout.addLayout(title_layout)

        # Version
        version = QLabel("v2.1.0")
        version.setStyleSheet("font-size: 11px; color: #64748b; padding-left: 32px;")
        layout.addWidget(version)

        return widget

    def _create_device_card(self) -> QGroupBox:
        """Create the DEVICE info card."""
        group = QGroupBox("🔒 DEVICE")
        group.setObjectName("infoCard")

        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 20, 16, 16)

        # Get device info
        device_id = self.session_manager.device_fingerprint_short
        hostname = platform.node()

        # ID
        id_label = QLabel("ID:")
        id_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        id_value = QLabel(device_id)
        id_value.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 600;")
        id_value.setAlignment(Qt.AlignRight)
        layout.addWidget(id_label, 0, 0)
        layout.addWidget(id_value, 0, 1)

        # Host
        host_label = QLabel("Host:")
        host_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        host_value = QLabel(hostname)
        host_value.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        host_value.setAlignment(Qt.AlignRight)
        layout.addWidget(host_label, 1, 0)
        layout.addWidget(host_value, 1, 1)

        # Status
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        status_value = QLabel("✓ Secured")
        status_value.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: 600;")
        status_value.setAlignment(Qt.AlignRight)
        layout.addWidget(status_label, 2, 0)
        layout.addWidget(status_value, 2, 1)

        return group

    def _create_credit_card(self) -> QGroupBox:
        """Create the CREDIT balance card."""
        group = QGroupBox("💰 CREDITS")
        group.setObjectName("infoCard")

        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 20, 16, 16)

        # Trial row
        trial_label = QLabel("Trial:")
        trial_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.trial_value = QLabel("-")
        self.trial_value.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self.trial_value.setAlignment(Qt.AlignRight)
        layout.addWidget(trial_label, 0, 0)
        layout.addWidget(self.trial_value, 0, 1)

        # Credits row
        credits_label = QLabel("Balance:")
        credits_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.credits_value = QLabel("-")
        self.credits_value.setStyleSheet(
            "color: #4ade80; font-size: 14px; font-weight: 600;"
        )
        self.credits_value.setAlignment(Qt.AlignRight)
        layout.addWidget(credits_label, 1, 0)
        layout.addWidget(self.credits_value, 1, 1)

        # Used row
        used_label = QLabel("Used:")
        used_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.used_value = QLabel("-")
        self.used_value.setStyleSheet("color: #f87171; font-size: 12px;")
        self.used_value.setAlignment(Qt.AlignRight)
        layout.addWidget(used_label, 2, 0)
        layout.addWidget(self.used_value, 2, 1)

        # Refresh button
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_credit_balance)
        layout.addWidget(refresh_btn, 3, 0, 1, 2)

        # Buy Credits button
        buy_btn = QPushButton("💳 Buy Credits")
        buy_btn.setObjectName("primaryButton")
        buy_btn.setCursor(Qt.PointingHandCursor)
        buy_btn.clicked.connect(self._on_buy_credits)
        layout.addWidget(buy_btn, 4, 0, 1, 2)

        return group

    def _create_system_card(self) -> QGroupBox:
        """Create the SYSTEM info card."""
        group = QGroupBox("⚙️ SYSTEM")
        group.setObjectName("infoCard")

        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 20, 16, 16)

        # Get system info
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024**3)
        ram_total = ram.total / (1024**3)
        cpu_count = os.cpu_count()
        platform_name = f"{platform.system()} {platform.release()}"

        # RAM
        ram_label = QLabel("RAM:")
        ram_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        ram_value = QLabel(f"{ram_used:.2f} / {ram_total:.2f} GB")
        ram_value.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        ram_value.setAlignment(Qt.AlignRight)
        layout.addWidget(ram_label, 0, 0)
        layout.addWidget(ram_value, 0, 1)

        # CPU
        cpu_label = QLabel("CPU:")
        cpu_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        cpu_value = QLabel(str(cpu_count))
        cpu_value.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        cpu_value.setAlignment(Qt.AlignRight)
        layout.addWidget(cpu_label, 1, 0)
        layout.addWidget(cpu_value, 1, 1)

        # Platform
        platform_label = QLabel("Platform:")
        platform_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        platform_value = QLabel(platform_name)
        platform_value.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        platform_value.setAlignment(Qt.AlignRight)
        layout.addWidget(platform_label, 2, 0)
        layout.addWidget(platform_value, 2, 1)

        # Mode
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        mode_value = QLabel("Local")
        mode_value.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: 600;")
        mode_value.setAlignment(Qt.AlignRight)
        layout.addWidget(mode_label, 3, 0)
        layout.addWidget(mode_value, 3, 1)

        return group

    def _create_sidebar_actions(self) -> QWidget:
        """Create History, Profile, Log Out and Quit buttons."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # History Button
        self.history_btn = QPushButton("📊 History")
        self.history_btn.setObjectName("secondaryButton")
        self.history_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.history_btn)

        # Profile Button
        self.profile_btn = QPushButton("👤 Profile")
        self.profile_btn.setObjectName("secondaryButton")
        self.profile_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.profile_btn)

        # Log Out Button
        self.logout_btn = QPushButton("🔒 Log Out")
        self.logout_btn.setObjectName("secondaryButton")
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.logout_btn)

        # Quit Button
        self.quit_btn = QPushButton("✕ Quit")
        self.quit_btn.setObjectName("dangerButton")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.quit_btn)

        return widget

    def _create_content_area(self) -> QWidget:
        """Create the main content area with all sections."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("contentScroll")

        content = QWidget()
        content.setObjectName("contentWidget")
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Top Row: SOURCE + PROCESSING
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # SOURCE Section
        source_section = self._create_source_section()
        top_row.addWidget(source_section, 1)

        # PROCESSING Section
        processing_section = self._create_processing_section()
        top_row.addWidget(processing_section, 1)

        layout.addLayout(top_row)

        # Middle Row: PREVIEW + PROGRESS
        middle_row = QHBoxLayout()
        middle_row.setSpacing(20)

        # PREVIEW Section
        preview_section = self._create_preview_section()
        middle_row.addWidget(preview_section, 3)

        # PROGRESS Section
        progress_section = self._create_progress_section()
        middle_row.addWidget(progress_section, 2)

        layout.addLayout(middle_row)

        # Action Buttons
        actions_section = self._create_action_buttons()
        layout.addWidget(actions_section)

        # OUTPUTS Section
        outputs_section = self._create_outputs_section()
        layout.addWidget(outputs_section)

        # Activity log is now inside PROGRESS section

        scroll.setWidget(content)
        return scroll

    def _create_source_section(self) -> QGroupBox:
        """Create the SOURCE section with Image/Text tabs and file selection."""
        group = QGroupBox("📁 SOURCE")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        # Tab Switcher
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(8)

        self.image_tab = QPushButton("🖼️ Image")
        self.image_tab.setCheckable(True)
        self.image_tab.setChecked(True)
        self.image_tab.setObjectName("tabButtonActive")

        self.text_tab = QPushButton("🔤 Text")
        self.text_tab.setCheckable(True)
        self.text_tab.setObjectName("tabButtonInactive")

        tab_layout.addWidget(self.image_tab)
        tab_layout.addWidget(self.text_tab)
        tab_layout.addStretch()

        layout.addLayout(tab_layout)

        # File Selection
        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select image file...")
        self.file_input.setObjectName("fileInput")
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input, 1)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setObjectName("primaryButton")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        file_layout.addWidget(self.browse_btn)

        layout.addLayout(file_layout)

        # Text Selection (Prompt)
        self.text_container = QWidget()
        self.text_container.setVisible(False)
        text_layout = QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText(
            "Describe the 3D model...\ne.g., 'a red sports car' or 'a medieval castle'"
        )
        self.prompt_input.setObjectName("promptInput")
        self.prompt_input.setMaximumHeight(80)
        text_layout.addWidget(self.prompt_input)

        self.negative_prompt = QLineEdit()
        self.negative_prompt.setPlaceholderText("Negative prompt (optional)")
        self.negative_prompt.setObjectName("fileInput")  # Reuse styling
        text_layout.addWidget(self.negative_prompt)

        layout.addWidget(self.text_container)
        layout.addStretch()

        return group

    def _create_processing_section(self) -> QGroupBox:
        """Create the PROCESSING section with method selection and quality."""
        group = QGroupBox("⚙️ PROCESSING")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        # Method Label
        method_label = QLabel("Method")
        method_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        layout.addWidget(method_label)

        # Method Selection Cards
        method_layout = QHBoxLayout()
        method_layout.setSpacing(12)

        # Local Processing Card
        self.local_card = QFrame()
        self.local_card.setObjectName("methodCardSelected")
        self.local_card.setCursor(Qt.PointingHandCursor)
        local_layout = QVBoxLayout(self.local_card)
        local_layout.setSpacing(4)
        local_layout.setContentsMargins(12, 12, 12, 12)

        local_radio = QRadioButton("💻 Local Processing")
        local_radio.setChecked(True)
        local_radio.setStyleSheet("""
            QRadioButton {
                color: #e2e8f0;
                font-weight: 600;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #f97316;
                background-color: transparent;
            }
            QRadioButton::indicator:checked {
                background-color: #f97316;
                border: 2px solid #f97316;
            }
            QRadioButton::indicator:checked::after {
                width: 6px;
                height: 6px;
                border-radius: 3px;
                background-color: white;
            }
        """)
        local_desc = QLabel("Geometry only")
        local_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")

        local_layout.addWidget(local_radio)
        local_layout.addWidget(local_desc)

        # Cloud API Card
        self.cloud_card = QFrame()
        self.cloud_card.setObjectName("methodCard")
        self.cloud_card.setCursor(Qt.PointingHandCursor)
        cloud_layout = QVBoxLayout(self.cloud_card)
        cloud_layout.setSpacing(4)
        cloud_layout.setContentsMargins(12, 12, 12, 12)

        cloud_radio = QRadioButton("☁️ Cloud API")
        cloud_radio.setStyleSheet("""
            QRadioButton {
                color: #94a3b8;
                font-weight: 600;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #64748b;
                background-color: transparent;
            }
            QRadioButton::indicator:checked {
                background-color: #f97316;
                border: 2px solid #f97316;
            }
            QRadioButton::indicator:checked::after {
                width: 6px;
                height: 6px;
                border-radius: 3px;
                background-color: white;
            }
        """)
        cloud_desc = QLabel("Geometry + Texture")
        cloud_desc.setStyleSheet("color: #64748b; font-size: 11px;")

        cloud_layout.addWidget(cloud_radio)
        cloud_layout.addWidget(cloud_desc)

        # Radio button group
        self.method_group = QButtonGroup()
        self.method_group.addButton(local_radio, 0)
        self.method_group.addButton(cloud_radio, 1)

        method_layout.addWidget(self.local_card, 1)
        method_layout.addWidget(self.cloud_card, 1)

        layout.addLayout(method_layout)

        # ── Cloud API Options Container (shown/hidden based on method) ──
        self.cloud_options_widget = QWidget()
        cloud_opts_layout = QVBoxLayout(self.cloud_options_widget)
        cloud_opts_layout.setSpacing(12)
        cloud_opts_layout.setContentsMargins(0, 0, 0, 0)

        # ── Row 1: Credit Balance + Cost Preview ──
        credit_row = QHBoxLayout()
        credit_row.setSpacing(12)

        # Credit Balance Box
        credit_box = QFrame()
        credit_box.setStyleSheet("""
            QFrame {
                background-color: rgba(21, 128, 61, 0.15);
                border-left: 3px solid #22c55e;
                border-radius: 4px;
                padding: 8px 12px;
            }
        """)
        credit_box_layout = QVBoxLayout(credit_box)
        credit_box_layout.setSpacing(4)
        credit_box_layout.setContentsMargins(10, 8, 10, 8)

        credit_header_layout = QHBoxLayout()
        credit_header_label = QLabel("💰 Your Credits")
        credit_header_label.setStyleSheet(
            "color: #94a3b8; font-size: 12px; font-weight: 600; background: transparent;"
        )
        credit_header_layout.addWidget(credit_header_label)
        credit_header_layout.addStretch()

        self.cloud_buy_btn = QPushButton("Buy Credits")
        self.cloud_buy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.cloud_buy_btn.setCursor(Qt.PointingHandCursor)
        self.cloud_buy_btn.clicked.connect(self._on_buy_credits)
        credit_header_layout.addWidget(self.cloud_buy_btn)
        credit_box_layout.addLayout(credit_header_layout)

        self.cloud_credit_value = QLabel("Loading...")
        self.cloud_credit_value.setStyleSheet(
            "color: #a7f3d0; font-size: 16px; font-weight: 700; background: transparent;"
        )
        credit_box_layout.addWidget(self.cloud_credit_value)

        credit_row.addWidget(credit_box, 2)

        # Cost Preview Box
        cost_box = QFrame()
        cost_box.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.6);
                border-left: 3px solid rgba(148, 163, 184, 0.6);
                border-radius: 4px;
                padding: 8px 12px;
            }
        """)
        cost_box_layout = QVBoxLayout(cost_box)
        cost_box_layout.setSpacing(4)
        cost_box_layout.setContentsMargins(10, 8, 10, 8)

        cost_label = QLabel("⚡ This Generation")
        cost_label.setStyleSheet(
            "color: #94a3b8; font-size: 12px; font-weight: 600; background: transparent;"
        )
        cost_box_layout.addWidget(cost_label)

        self.cloud_cost_value = QLabel("Select resolution to see cost")
        self.cloud_cost_value.setStyleSheet(
            "color: #cbd5e1; font-size: 12px; font-weight: 500; background: transparent;"
        )
        self.cloud_cost_value.setWordWrap(True)
        cost_box_layout.addWidget(self.cloud_cost_value)

        credit_row.addWidget(cost_box, 1)

        cloud_opts_layout.addLayout(credit_row)

        # ── Row 2: Model, Resolution, Format dropdowns ──
        config_row = QHBoxLayout()
        config_row.setSpacing(12)

        # Model
        model_container = QVBoxLayout()
        model_label = QLabel("Model")
        model_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        model_container.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setObjectName("modelCombo")
        self.cloud_models = [
            ("hitem3dv1.5", "Standard v1.5"),
            ("hitem3dv2.0", "Standard v2.0"),
            ("scene-portraitv1.5", "Portrait v1.5"),
            ("scene-portraitv2.0", "Portrait v2.0"),
            ("scene-portraitv2.1", "Portrait v2.1"),
        ]
        for model_id, model_name in self.cloud_models:
            self.model_combo.addItem(model_name, model_id)
        model_container.addWidget(self.model_combo)
        config_row.addLayout(model_container, 1)

        # Resolution
        res_container = QVBoxLayout()
        resolution_label = QLabel("Resolution")
        resolution_label.setStyleSheet(
            "color: #94a3b8; font-size: 13px; font-weight: 600;"
        )
        res_container.addWidget(resolution_label)

        self.resolution_combo = QComboBox()
        self.resolution_combo.setObjectName("resolutionCombo")
        self.model_resolutions = {
            "hitem3dv1.5": ["512", "1024", "1536", "1536pro"],
            "hitem3dv2.0": ["1536", "1536pro"],
            "scene-portraitv1.5": ["1536"],
            "scene-portraitv2.0": ["1536pro"],
            "scene-portraitv2.1": ["1536pro"],
        }
        for res in self.model_resolutions["hitem3dv1.5"]:
            display = "1536³ Pro" if res == "1536pro" else f"{res}³"
            self.resolution_combo.addItem(display, res)
        res_container.addWidget(self.resolution_combo)
        config_row.addLayout(res_container, 1)

        # Format
        fmt_container = QVBoxLayout()
        format_label = QLabel("Format")
        format_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 600;")
        fmt_container.addWidget(format_label)

        self.format_combo = QComboBox()
        self.format_combo.setObjectName("formatCombo")
        for fmt_val, fmt_name in [
            ("obj", "OBJ"),
            ("glb", "GLB"),
            ("stl", "STL"),
            ("fbx", "FBX"),
            ("usdz", "USDZ"),
        ]:
            self.format_combo.addItem(fmt_name, fmt_val)
        fmt_container.addWidget(self.format_combo)
        config_row.addLayout(fmt_container, 1)

        cloud_opts_layout.addLayout(config_row)

        # ── Model Info Text ──
        self.model_descriptions = {
            "hitem3dv1.5": "Standard v1.5: General purpose 3D generation. Recommended: 1024³",
            "hitem3dv2.0": "Standard v2.0: Enhanced quality model. Recommended: 1536³",
            "scene-portraitv1.5": "Portrait v1.5: Specialized portrait model. Recommended: 1536³",
            "scene-portraitv2.0": "Portrait v2.0: Enhanced portrait model. Recommended: 1536³ Pro",
            "scene-portraitv2.1": "Portrait v2.1: Best quality portrait. Recommended: 1536³ Pro",
        }
        self.model_info_label = QLabel(self.model_descriptions.get("hitem3dv1.5", ""))
        self.model_info_label.setStyleSheet("""
            color: #93c5fd;
            font-size: 11px;
            padding: 6px 10px;
            background: rgba(59, 130, 246, 0.1);
            border-left: 3px solid #3b82f6;
            border-radius: 4px;
        """)
        self.model_info_label.setWordWrap(True)
        cloud_opts_layout.addWidget(self.model_info_label)

        layout.addWidget(self.cloud_options_widget)

        # Initially hide cloud options (Local is selected by default)
        self.cloud_options_widget.setVisible(False)

        layout.addStretch()

        return group

    def _create_preview_section(self) -> QGroupBox:
        """Create the PREVIEW section with image drop area."""
        group = QGroupBox("🖼️ PREVIEW")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        # Preview Area
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        self.preview_frame.setMinimumHeight(250)
        self.preview_frame.setAcceptDrops(True)

        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setAlignment(Qt.AlignCenter)

        self.preview_label = QLabel("No image selected")
        self.preview_label.setStyleSheet("color: #64748b; font-size: 14px;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.preview_label)

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background-color: transparent;")
        self.image_preview.setMaximumSize(400, 300)
        self.image_preview.setScaledContents(True)
        self.image_preview.hide()
        preview_layout.addWidget(self.image_preview)

        layout.addWidget(self.preview_frame, 1)

        return group

    def _create_progress_section(self) -> QGroupBox:
        """Create the PROGRESS section with progress bar, status, and activity log."""
        group = QGroupBox("📊 PROGRESS & LOG")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumHeight(24)
        layout.addWidget(self.progress_bar)

        # Status with Stage Name
        status_layout = QHBoxLayout()

        self.status_icon = QLabel("⏳")
        self.status_icon.setStyleSheet("font-size: 16px;")
        status_layout.addWidget(self.status_icon)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label, 1)

        layout.addLayout(status_layout)

        # Time Labels
        time_layout = QHBoxLayout()

        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setStyleSheet("color: #64748b; font-size: 11px;")
        time_layout.addWidget(self.elapsed_label)

        time_layout.addStretch()

        self.eta_label = QLabel("ETA: --:--")
        self.eta_label.setStyleSheet("color: #64748b; font-size: 11px;")
        time_layout.addWidget(self.eta_label)

        layout.addLayout(time_layout)

        # Activity Log (inside progress section)
        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("activityLog")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Activity will appear here...")
        self.log_text.setMinimumHeight(150)
        layout.addWidget(self.log_text)

        layout.addStretch()

        return group

    def _create_action_buttons(self) -> QWidget:
        """Create the action buttons (Reset, Open Folder, Generate)."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        # Reset Button
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setMinimumWidth(120)
        layout.addWidget(self.reset_btn)

        layout.addSpacing(40)

        # Generate Button
        self.generate_btn = QPushButton("🚀 Generate 3D Model")
        self.generate_btn.setObjectName("generateButton")
        self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.setEnabled(False)
        self.generate_btn.setMinimumWidth(200)
        self.generate_btn.setMinimumHeight(44)
        layout.addWidget(self.generate_btn)

        return widget

    def _create_outputs_section(self) -> QGroupBox:
        """Create the OUTPUTS section with an embedded 3D viewer."""
        group = QGroupBox("📦 OUTPUT MODEL")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 20, 16, 16)

        # 3D Viewer Area
        from PySide6.QtWebEngineCore import QWebEngineSettings

        self.model_viewer = QWebEngineView()
        self.model_viewer.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls, True
        )
        self.model_viewer.setObjectName("modelViewer")
        self.model_viewer.setMinimumHeight(400)

        # Initial empty logic
        self.model_viewer.setHtml("""
        <html><body style="background:#0f172a; color:#64748b; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100%; margin:0;">
        <div style="text-align:center;">Generate a 3D model to view it here</div>
        </body></html>
        """)

        layout.addWidget(self.model_viewer, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_save_obj = QPushButton("⬇️ Download OBJ")
        self.btn_save_obj.setObjectName("primaryButton")
        self.btn_save_obj.clicked.connect(lambda: self._on_save_output("OBJ"))
        self.btn_save_obj.setEnabled(False)
        self.btn_save_obj.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.btn_save_obj)

        self.btn_save_stl = QPushButton("⬇️ Download STL")
        self.btn_save_stl.setObjectName("primaryButton")
        self.btn_save_stl.clicked.connect(lambda: self._on_save_output("STL"))
        self.btn_save_stl.setEnabled(False)
        self.btn_save_stl.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.btn_save_stl)

        self.btn_save_glb = QPushButton("⬇️ Download GLB")
        self.btn_save_glb.setObjectName("primaryButton")
        self.btn_save_glb.clicked.connect(lambda: self._on_save_output("GLB"))
        self.btn_save_glb.setEnabled(False)
        self.btn_save_glb.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.btn_save_glb)

        layout.addLayout(btn_layout)

        return group

    def _create_activity_log_section(self) -> QGroupBox:
        """Create the ACTIVITY LOG section."""
        group = QGroupBox("📋 ACTIVITY LOG")
        group.setObjectName("sectionCard")

        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 20, 16, 16)

        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("activityLog")
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Activity will appear here...")
        self.log_text.setMinimumHeight(120)
        layout.addWidget(self.log_text)

        return group

    def _setup_connections(self):
        """Setup signal connections."""
        # Tab switching
        self.image_tab.clicked.connect(lambda: self._switch_tab("image"))
        self.text_tab.clicked.connect(lambda: self._switch_tab("text"))

        # File selection
        self.browse_btn.clicked.connect(self._on_browse)
        self.preview_frame.dragEnterEvent = self._on_drag_enter
        self.preview_frame.dropEvent = self._on_drop
        self.preview_frame.mousePressEvent = lambda e: self._on_browse()

        # Method selection
        self.method_group.buttonClicked.connect(self._on_method_changed)

        # Card clicks should also toggle the radio AND trigger method change
        def _click_local(e):
            self.method_group.button(0).setChecked(True)
            self._on_method_changed(self.method_group.button(0))

        def _click_cloud(e):
            self.method_group.button(1).setChecked(True)
            self._on_method_changed(self.method_group.button(1))

        self.local_card.mousePressEvent = _click_local
        self.cloud_card.mousePressEvent = _click_cloud

        # Model selection - update resolutions when model changes
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

        # Resolution change - update cost preview
        self.resolution_combo.currentIndexChanged.connect(self._update_cost_preview)

        # Action buttons
        self.reset_btn.clicked.connect(self._on_reset)
        self.generate_btn.clicked.connect(self._on_generate)
        self.history_btn.clicked.connect(self._on_show_history)
        self.profile_btn.clicked.connect(self._on_show_profile)
        self.logout_btn.clicked.connect(self._on_logout)
        self.quit_btn.clicked.connect(self.close)

        # Text input - enable generate button when text is entered
        self.prompt_input.textChanged.connect(self._on_prompt_text_changed)

    def _load_stylesheet(self):
        """Load the application stylesheet."""
        stylesheet = """
        /* Global */
        QWidget {
            background-color: #0a0e1a;
            color: #e2e8f0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            font-size: 13px;
        }
        
        /* Sidebar */
        #sidebar {
            background-color: #0d1320;
            border-right: 1px solid #1e3a5f;
        }
        
        /* Content Area */
        #contentArea {
            background-color: #0a0e1a;
        }
        
        #contentWidget {
            background-color: #0a0e1a;
        }
        
        /* Info Cards (DEVICE, SYSTEM) */
        #infoCard {
            background-color: #111827;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
            margin-top: 14px;
            padding-top: 10px;
            font-weight: bold;
            color: #e2e8f0;
        }
        
        #infoCard::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #60a5fa;
        }
        
        /* Section Cards */
        #sectionCard {
            background-color: #111827;
            border: 1px solid #1e3a5f;
            border-radius: 10px;
            margin-top: 14px;
            padding-top: 10px;
            font-weight: bold;
            color: #e2e8f0;
        }
        
        #sectionCard::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #60a5fa;
        }
        
        /* Tab Buttons */
        #tabButtonActive {
            background-color: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        #tabButtonActive:hover {
            background-color: #2563eb;
        }
        
        #tabButtonInactive {
            background-color: #1a2332;
            color: #94a3b8;
            border: 1px solid #1e3a5f;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        #tabButtonInactive:hover {
            background-color: #162032;
            color: #e2e8f0;
        }
        
        /* File Input */
        #fileInput {
            background-color: #1a2332;
            color: #e2e8f0;
            border: 1px solid #1e3a5f;
            border-radius: 6px;
            padding: 10px 14px;
        }
        
        #fileInput:focus {
            border-color: #3b82f6;
        }

        /* Prompt Input */
        #promptInput {
            background-color: #1a2332;
            color: #e2e8f0;
            border: 1px solid #1e3a5f;
            border-radius: 6px;
            padding: 10px 14px;
        }

        #promptInput:focus {
            border-color: #3b82f6;
        }
        
        /* Method Cards */
        #methodCard {
            background-color: #0d1320;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }
        
        #methodCard:hover {
            border-color: #2d4a6f;
        }
        
        #methodCardSelected {
            background-color: rgba(59, 130, 246, 0.1);
            border: 2px solid #3b82f6;
            border-radius: 8px;
        }
        
        /* Quality Combo */
        #qualityCombo {
            background-color: #1a2332;
            color: #e2e8f0;
            border: 1px solid #1e3a5f;
            border-radius: 6px;
            padding: 10px 14px;
        }
        
        #qualityCombo::drop-down {
            border: none;
            width: 30px;
        }
        
        #qualityCombo QAbstractItemView {
            background-color: #1a2332;
            color: #e2e8f0;
            selection-background-color: #3b82f6;
            border: 1px solid #1e3a5f;
        }
        
        /* Preview Frame */
        #previewFrame {
            background-color: #151d2a;
            border: 2px dashed #1e3a5f;
            border-radius: 12px;
        }
        
        #previewFrame:hover {
            border-color: #2d4a6f;
        }
        
        /* Progress Bar */
        #progressBar {
            background-color: #1a2332;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }
        
        #progressBar::chunk {
            background-color: #3b82f6;
            border-radius: 6px;
        }
        
        /* Output Card */
        #outputCard {
            background-color: #1a2332;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
        }
        
        /* Activity Log */
        #activityLog {
            background-color: #0d1320;
            color: #94a3b8;
            border: 1px solid #1e3a5f;
            border-radius: 8px;
            padding: 10px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 12px;
        }
        
        /* Buttons */
        #primaryButton {
            background-color: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        #primaryButton:hover {
            background-color: #2563eb;
        }
        
        #primaryButton:disabled {
            background-color: #1e3a5f;
            color: #64748b;
        }
        
        #secondaryButton {
            background-color: #374151;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        #secondaryButton:hover {
            background-color: #4b5563;
        }
        
        #dangerButton {
            background-color: #ef4444;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        #dangerButton:hover {
            background-color: #dc2626;
        }
        
        #generateButton {
            background-color: #22c55e;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: bold;
        }
        
        #generateButton:hover {
            background-color: #16a34a;
        }
        
        #generateButton:disabled {
            background-color: #1e3a5f;
            color: #64748b;
        }
        
        #smallPrimaryButton {
            background-color: #3b82f6;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }
        
        #smallPrimaryButton:hover {
            background-color: #2563eb;
        }
        
        #smallSecondaryButton {
            background-color: #374151;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }
        
        #smallSecondaryButton:hover {
            background-color: #4b5563;
        }
        
        /* Scroll Area */
        #contentScroll {
            background-color: transparent;
            border: none;
        }
        
        #contentScroll QScrollBar:vertical {
            background-color: #0d1320;
            width: 10px;
            border-radius: 5px;
        }
        
        #contentScroll QScrollBar::handle:vertical {
            background-color: #1e3a5f;
            border-radius: 5px;
            min-height: 30px;
        }
        
        #contentScroll QScrollBar::handle:vertical:hover {
            background-color: #2d4a6f;
        }
        """
        self.setStyleSheet(stylesheet)

    def _switch_tab(self, tab: str):
        """Switch between Image and Text tabs."""
        if tab == "image":
            self.image_tab.setObjectName("tabButtonActive")
            self.image_tab.setChecked(True)
            self.text_tab.setObjectName("tabButtonInactive")
            self.text_tab.setChecked(False)
            # Toggle UI visibility - show file input, hide text input
            self.file_input.setVisible(True)
            self.browse_btn.setVisible(True)
            if hasattr(self, "text_container"):
                self.text_container.setVisible(False)
            # Switch back to previous method selection
            self._add_log("🔄 Mode: Image-to-3D")
        else:
            self.text_tab.setObjectName("tabButtonActive")
            self.text_tab.setChecked(True)
            self.image_tab.setObjectName("tabButtonInactive")
            self.image_tab.setChecked(False)
            # Toggle UI visibility - hide file input, show text input
            self.file_input.setVisible(False)
            self.browse_btn.setVisible(False)
            if hasattr(self, "text_container"):
                self.text_container.setVisible(True)
            # Text mode requires Cloud API - switch to cloud automatically
            if self.method_group.checkedId() == 0:  # If local is selected
                self.method_group.button(1).setChecked(True)
                self._on_method_changed(self.method_group.button(1))
            # Enable generate button if there's already text
            prompt = self.prompt_input.toPlainText().strip()
            self.generate_btn.setEnabled(bool(prompt))
            self._add_log("🔄 Mode: Text-to-3D (Cloud API only)")
        self._load_stylesheet()

    def _on_method_changed(self, button):
        """Handle method selection change — show/hide cloud options."""
        is_cloud = button == self.method_group.button(1)
        if is_cloud:
            self.cloud_card.setObjectName("methodCardSelected")
            self.local_card.setObjectName("methodCard")
            self.cloud_options_widget.setVisible(True)
            # Defer network call so UI renders first (prevents crash/freeze)
            QTimer.singleShot(50, self._safe_refresh_cloud_credit_display)
        else:
            self.local_card.setObjectName("methodCardSelected")
            self.cloud_card.setObjectName("methodCard")
            self.cloud_options_widget.setVisible(False)
        self._load_stylesheet()

    def _on_model_changed(self, index):
        """Handle model selection change - update available resolutions and info."""
        model_id = self.model_combo.currentData()  # Get the model ID
        resolutions = self.model_resolutions.get(model_id, ["1024", "1536", "1536pro"])

        # Save current selection if still available
        current_res = self.resolution_combo.currentData()

        # Update resolutions
        self.resolution_combo.blockSignals(True)
        self.resolution_combo.clear()
        for res in resolutions:
            display = "1536³ Pro" if res == "1536pro" else f"{res}³"
            self.resolution_combo.addItem(display, res)

        # Try to restore previous selection or default to highest
        if current_res in resolutions:
            idx = resolutions.index(current_res)
            self.resolution_combo.setCurrentIndex(idx)
        else:
            self.resolution_combo.setCurrentIndex(len(resolutions) - 1)  # Highest res
        self.resolution_combo.blockSignals(False)

        # Update model info text
        if hasattr(self, "model_info_label") and hasattr(self, "model_descriptions"):
            desc = self.model_descriptions.get(model_id, "")
            self.model_info_label.setText(desc)

        # Update cost preview
        self._update_cost_preview()

    def _update_cost_preview(self):
        """Update the cost preview box based on current resolution and credit balance."""
        if not hasattr(self, "cloud_cost_value"):
            return

        res = self.resolution_combo.currentData() or "1024"
        cost = CREDIT_COSTS.get(res, 20)

        # Get cached credit info
        trial_remaining = getattr(self, "_cached_trial_remaining", 0)
        credits_balance = getattr(self, "_cached_credits_balance", 0)

        if trial_remaining > 0:
            self.cloud_cost_value.setText("FREE (trial) — 0 credits")
            self.cloud_cost_value.setStyleSheet(
                "color: #a7f3d0; font-size: 12px; font-weight: 600; background: transparent;"
            )
            # Update cost box border to green
            self.cloud_cost_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(21, 128, 61, 0.15);
                    border-left: 3px solid #22c55e;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
        elif credits_balance >= cost:
            remaining = credits_balance - cost
            self.cloud_cost_value.setText(
                f"Cost: {cost} credits → {remaining} left after"
            )
            self.cloud_cost_value.setStyleSheet(
                "color: #a7f3d0; font-size: 12px; font-weight: 600; background: transparent;"
            )
            self.cloud_cost_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(21, 128, 61, 0.15);
                    border-left: 3px solid #22c55e;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
        else:
            self.cloud_cost_value.setText(
                f"Need {cost} credits, have {credits_balance} ❌"
            )
            self.cloud_cost_value.setStyleSheet(
                "color: #fecdd3; font-size: 12px; font-weight: 600; background: transparent;"
            )
            self.cloud_cost_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(127, 29, 29, 0.2);
                    border-left: 3px solid #ef4444;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)

    def _safe_refresh_cloud_credit_display(self):
        """Safe wrapper that catches all errors to prevent crashes."""
        try:
            self._refresh_cloud_credit_display()
        except Exception as e:
            print(f"[MainWindow] Cloud credit display refresh error: {e}")
            # Set defaults on error
            if hasattr(self, "cloud_credit_value"):
                self.cloud_credit_value.setText("Unable to load")
            self._cached_trial_remaining = 0
            self._cached_credits_balance = 0
            try:
                self._update_cost_preview()
            except Exception:
                pass

    def _refresh_cloud_credit_display(self):
        """Refresh the inline credit display in the cloud options section."""
        from core.credit_manager import get_user_balance

        if not hasattr(self, "cloud_credit_value"):
            return

        user_id = self.session_manager.user_id
        if not user_id or not self.session_manager.is_authenticated:
            self.cloud_credit_value.setText("Not logged in")
            self._cached_trial_remaining = 0
            self._cached_credits_balance = 0
            self._update_cost_preview()
            return

        try:
            balance_info = get_user_balance(
                user_id, self.session_manager.device_fingerprint
            )
        except Exception as e:
            print(f"[MainWindow] get_user_balance error: {e}")
            self.cloud_credit_value.setText("Connection error")
            self._cached_trial_remaining = 0
            self._cached_credits_balance = 0
            self._update_cost_preview()
            return

        if "error" in balance_info:
            self.cloud_credit_value.setText("Error loading")
            self._cached_trial_remaining = 0
            self._cached_credits_balance = 0
            self._update_cost_preview()
            return

        trial = balance_info.get("trial_remaining", 0)
        credits = balance_info.get("credits_balance", 0)

        # Cache for cost preview
        self._cached_trial_remaining = trial
        self._cached_credits_balance = credits

        if trial > 0:
            self.cloud_credit_value.setText(f"🎁 Trial: {trial} free generation(s)")
            self.cloud_credit_value.setStyleSheet(
                "color: #a7f3d0; font-size: 16px; font-weight: 700; background: transparent;"
            )
            self.cloud_credit_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(21, 128, 61, 0.15);
                    border-left: 3px solid #22c55e;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
        elif credits > 0:
            self.cloud_credit_value.setText(f"{credits} credits")
            self.cloud_credit_value.setStyleSheet(
                "color: #a7f3d0; font-size: 16px; font-weight: 700; background: transparent;"
            )
            self.cloud_credit_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(21, 128, 61, 0.15);
                    border-left: 3px solid #22c55e;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)
        else:
            self.cloud_credit_value.setText("0 credits")
            self.cloud_credit_value.setStyleSheet(
                "color: #fecdd3; font-size: 16px; font-weight: 700; background: transparent;"
            )
            self.cloud_credit_value.parentWidget().setStyleSheet("""
                QFrame {
                    background-color: rgba(127, 29, 29, 0.2);
                    border-left: 3px solid #ef4444;
                    border-radius: 4px;
                    padding: 8px 12px;
                }
            """)

        self._update_cost_preview()

    def _on_drag_enter(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _on_drop(self, event: QDropEvent):
        """Handle drop event."""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                self._load_image(file_path)

    def _on_browse(self):
        """Handle browse button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if file_path:
            self._load_image(file_path)

    def _load_image(self, file_path: str):
        """Load an image file."""
        self.selected_file = file_path

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.preview_label.hide()
            self.image_preview.setPixmap(
                pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.image_preview.show()
            self.file_input.setText(Path(file_path).name)
            self.generate_btn.setEnabled(True)
            self._add_log(f"Image loaded: {Path(file_path).name}")

    def _on_prompt_text_changed(self):
        """Enable/disable generate button based on text input."""
        if self.text_tab.isChecked():
            prompt = self.prompt_input.toPlainText().strip()
            self.generate_btn.setEnabled(bool(prompt))

    def _on_reset(self):
        """Handle reset button click."""
        self.selected_file = None
        self.file_input.clear()
        self.prompt_input.clear()
        self.negative_prompt.clear()
        self.image_preview.clear()
        self.image_preview.hide()
        self.preview_label.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.status_icon.setText("⏳")
        self.elapsed_label.setText("Elapsed: --:--")
        self.eta_label.setText("ETA: --:--")
        self.generate_btn.setEnabled(False)
        self._add_log("🔄 Reset")

    def _enforce_trial_settings(self):
        """Force Cloud API + Best Model + Highest Resolution during trial period."""
        from core.credit_manager import get_user_balance

        user_id = self.session_manager.user_id
        if not user_id:
            return

        try:
            balance_info = get_user_balance(
                user_id, self.session_manager.device_fingerprint
            )
        except Exception as e:
            print(f"[MainWindow] _enforce_trial_settings error: {e}")
            return
        if "error" in balance_info:
            return

        trial_used = balance_info.get("trial_used", 0)
        credits = balance_info.get("credits_balance", 0)

        # Force Cloud API + Best Model + Highest Resolution during trial
        if trial_used == 0 and credits == 0:
            # User is in trial period - force cloud API and best model
            self.method_group.button(1).setChecked(True)  # Cloud API

            # Set to Best Quality (best model)
            self.model_combo.setCurrentText("Portrait v2.1")

            # Set to highest resolution (1536pro)
            for i in range(self.resolution_combo.count()):
                if self.resolution_combo.itemData(i) == "1536pro":
                    self.resolution_combo.setCurrentIndex(i)
                    break

            # Show cloud options and disable switching during trial
            self.cloud_options_widget.setVisible(True)
            self.method_group.setExclusive(False)
            self.method_group.button(0).setEnabled(False)  # Disable Local
            self.method_group.setExclusive(True)
            self.model_combo.setEnabled(False)
            self.resolution_combo.setEnabled(False)
            self._add_log("🎯 Trial: Cloud API + Best Quality + 1536³ Pro enforced")
            # Refresh cloud credit display (deferred & safe)
            QTimer.singleShot(100, self._safe_refresh_cloud_credit_display)

    def _refresh_credit_balance(self):
        """Refresh the credit balance display."""
        from core.credit_manager import get_user_balance

        user_id = self.session_manager.user_id
        if not user_id:
            self.trial_value.setText("-")
            self.credits_value.setText("-")
            self.used_value.setText("-")
            return

        # Check if session is authenticated
        if not self.session_manager.is_authenticated:
            self.trial_value.setText("-")
            self.credits_value.setText("-")
            self.used_value.setText("-")
            return

        try:
            balance_info = get_user_balance(
                user_id, self.session_manager.device_fingerprint
            )
        except Exception as e:
            print(f"[MainWindow] _refresh_credit_balance error: {e}")
            self.trial_value.setText("Error")
            self.credits_value.setText("Error")
            self.used_value.setText("Error")
            return

        if "error" in balance_info:
            self.trial_value.setText("Error")
            self.credits_value.setText("Error")
            self.used_value.setText("Error")
            return

        # Update display
        trial = balance_info.get("trial_remaining", 0)
        trial_used = balance_info.get("trial_used", 0)
        credits = balance_info.get("credits_balance", 0)
        used = balance_info.get("total_used", 0)

        self.trial_value.setText(f"{trial}")

        # Force Cloud API + Best Model + Highest Resolution during trial period
        if trial_used == 0 and credits == 0:
            # User is in trial period - force cloud API and best model
            self.method_group.button(1).setChecked(True)  # Cloud API
            self.model_combo.setCurrentText("Portrait v2.1")
            for i in range(self.resolution_combo.count()):
                if self.resolution_combo.itemData(i) == "1536pro":
                    self.resolution_combo.setCurrentIndex(i)
                    break
            # Show cloud options and disable switching during trial
            self.cloud_options_widget.setVisible(True)
            self.method_group.setExclusive(False)
            self.method_group.button(0).setEnabled(False)  # Disable Local
            self.method_group.setExclusive(True)
            self.model_combo.setEnabled(False)
            self.resolution_combo.setEnabled(False)
        else:
            # Not in trial - enable all options
            self.method_group.button(0).setEnabled(True)
            self.model_combo.setEnabled(True)
            self.resolution_combo.setEnabled(True)
        if credits > 0:
            self.credits_value.setText(f"{credits}")
            self.credits_value.setStyleSheet(
                "color: #4ade80; font-size: 14px; font-weight: 600;"
            )
        else:
            self.credits_value.setText(f"{credits}")
            self.credits_value.setStyleSheet(
                "color: #f87171; font-size: 14px; font-weight: 600;"
            )
        self.used_value.setText(f"{used}")

        # Also refresh cloud credit display if visible (deferred & safe)
        if (
            hasattr(self, "cloud_options_widget")
            and self.cloud_options_widget.isVisible()
        ):
            QTimer.singleShot(50, self._safe_refresh_cloud_credit_display)

    def _on_buy_credits(self):
        """Open credit purchase dialog."""
        from ui.credit_purchase_dialog import CreditPurchaseDialog

        # Get current balance
        user_id = self.session_manager.user_id
        if not user_id:
            QMessageBox.warning(
                self, "Not Logged In", "Please login first to purchase credits."
            )
            return

        # Show loading cursor while dialog loads
        self.setCursor(Qt.WaitCursor)
        try:
            # Use cached credits if available, to avoid blocking call
            cached_balance = getattr(self, "_cached_credits_balance", 0)
            current_credits = (
                cached_balance
                if cached_balance
                else getattr(self.session_manager, "credits", 0)
            )
            dialog = CreditPurchaseDialog(self, current_credits)
        except Exception as e:
            print(f"[MainWindow] Buy credits dialog error: {e}")
            self.setCursor(Qt.ArrowCursor)
            QMessageBox.warning(
                self, "Error", f"Could not open credit purchase dialog: {e}"
            )
            return
        finally:
            self.setCursor(Qt.ArrowCursor)

        dialog.exec()

    def _check_credit_update(self):
        """Poll Supabase for credit balance updates after purchase."""
        self._poll_count += 1
        try:
            balance_info = get_user_balance(
                self.session_manager.user_id, self.session_manager.device_fingerprint
            )
            new_balance = balance_info.get("credits_balance", 0)
            if new_balance > self._poll_initial_balance:
                self._credit_poll_timer.stop()
                added = new_balance - self._poll_initial_balance
                self._refresh_credit_balance()
                QMessageBox.information(
                    self,
                    "Purchase Complete",
                    f"✅ Credits added: {added}\nNew balance: {new_balance}",
                )
                self._add_log(
                    f"💰 Credits purchased: +{added} (balance: {new_balance})"
                )
                return
        except Exception:
            pass

        if self._poll_count > 60:  # 5 minute timeout
            self._credit_poll_timer.stop()
            self._add_log(
                "⏰ Credit polling timed out. Click Refresh to check manually."
            )

    def _on_generate(self):
        """Handle generate button click for both Image and Text modes."""
        is_text_mode = self.text_tab.isChecked()

        # Validation
        if is_text_mode:
            prompt = self.prompt_input.toPlainText().strip()
            if not prompt:
                QMessageBox.warning(
                    self, "Warning", "Please enter a description for the 3D model."
                )
                return
            input_data = prompt
            negative_prompt = self.negative_prompt.text().strip()
            input_type = "text"
        else:
            if not self.selected_file:
                QMessageBox.warning(self, "Warning", "Please select an image first.")
                return
            input_data = str(self.selected_file)
            negative_prompt = ""
            input_type = "image"

        # Get settings
        model_type = "local" if self.method_group.checkedId() == 0 else "cloud"

        # Text mode ALWAYS uses cloud
        if is_text_mode and model_type == "local":
            self.method_group.button(1).setChecked(True)
            self._on_method_changed(self.method_group.button(1))
            model_type = "cloud"

        # Get model and resolution from combos
        api_model = self.model_combo.currentData()
        api_resolution = self.resolution_combo.currentData()

        # Local processing (image only) is FREE
        if model_type == "local" and not is_text_mode:
            self._start_local_generation("standard")
            return

        # Credit check and deduction for Cloud
        from core.credit_manager import get_user_balance

        balance_info = get_user_balance(
            self.session_manager.user_id, self.session_manager.device_fingerprint
        )
        trial_used = balance_info.get("trial_used", 0)
        is_trial = trial_used == 0

        # For trial, force best settings
        if is_trial:
            api_model = "scene-portraitv2.1" if not is_text_mode else "tripo3d"
            api_resolution = "1536pro" if not is_text_mode else "1024"
            if not is_text_mode:
                self.model_combo.setCurrentText("Portrait v2.1")
            self._add_log(f"🎯 Trial: Best Quality - FREE first generation!")

        allowed, reason, cost = can_generate(
            self.session_manager.user_id,
            api_resolution,
            is_trial,
            device_fingerprint=self.session_manager.device_fingerprint,
        )
        if not allowed:
            reply = QMessageBox.question(
                self,
                "Insufficient Credits",
                f"{reason}\n\nBuy more?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._on_buy_credits()
            return

        # Deduct credits
        selected_format = (
            self.format_combo.currentData() if hasattr(self, "format_combo") else "glb"
        )
        deduction = deduct_credits(
            self.session_manager.user_id,
            api_resolution,
            api_model,
            input_type=input_type,
            output_format=selected_format,
            is_trial=is_trial,
            device_fingerprint=self.session_manager.device_fingerprint,
        )

        if not deduction.get("success"):
            QMessageBox.warning(
                self, "Credit Error", f"Deduction failed: {deduction.get('error')}"
            )
            return

        # Generation Setup
        self._current_model = model_type
        self._current_quality = api_resolution
        self._current_api_model = api_model
        self._current_generation_id = deduction.get("generation_id")
        self._current_credits_deducted = deduction.get("credits_deducted", 0)
        self._is_trial_generation = is_trial

        self._add_log(
            f"💰 Credits deducted: {self._current_credits_deducted} (source: {deduction.get('source')})"
        )

        # Start Worker
        self.generate_btn.setEnabled(False)
        self.btn_save_obj.setEnabled(False)
        self.btn_save_stl.setEnabled(False)
        self.btn_save_glb.setEnabled(False)

        self.status_label.setText("Initializing...")
        self.status_icon.setText("⏳")
        self.progress_bar.setValue(0)
        self.start_time = datetime.now()
        self.timer.start(1000)

        output_formats = ["obj", "stl", "glb"]
        if hasattr(self, "format_combo"):
            fmt = self.format_combo.currentData()
            if fmt and fmt not in output_formats:
                output_formats.append(fmt)

        self.worker = GenerationWorker(
            input_data,
            model_type,
            api_resolution,
            api_model,
            output_formats,
            mode=input_type,
            negative_prompt=negative_prompt,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_generation_complete)
        self.worker.error.connect(self._on_generation_error)
        self.worker.start()

        msg = f"🚀 Starting {input_type.upper()}-to-3D at {api_resolution}"
        if not is_text_mode:
            msg += f": {Path(self.selected_file).name}"
        self._add_log(msg)

    def _start_local_generation(self, quality: str):
        """Start local processing (FREE - no credits needed)."""

        # Check if user wants to see the CPU warning modal
        settings = QSettings("TrivoxModels", "TrivoxAIModels")
        dont_show_again = settings.value("dont_show_cpu_warning", False, type=bool)

        if not dont_show_again:
            # Show CPU warning modal
            msg = QMessageBox(self)
            msg.setWindowTitle("Local Processing Notice")
            msg.setIcon(QMessageBox.Information)
            msg.setText(
                "<b>ℹ️ You're using Local Processing (CPU)</b><br><br>"
                "This mode runs on your computer's processor, which is slower than GPU.<br><br>"
                "<b>💡 For better results:</b><br>"
                "• Use a computer with a powerful GPU for faster processing<br>"
                "• Or use our <b>Cloud API</b> for:<br>"
                "  - High-quality 3D models<br>"
                "  - Faster processing (seconds vs minutes)<br>"
                "  - Professional GPU rendering<br><br>"
                "Local processing is <b>FREE</b>, while Cloud API uses credits."
            )

            # Add checkbox for "don't show again"
            dont_show_checkbox = QCheckBox("Don't show this message again")
            msg.setCheckBox(dont_show_checkbox)

            # Add buttons
            msg.addButton("Continue (Local)", QMessageBox.AcceptRole)
            msg.addButton("Use Cloud API", QMessageBox.ActionRole)
            msg.setDefaultButton(QMessageBox.Ok)

            # Show modal
            clicked_button = msg.exec_()

            # Check if user wants to stop showing this
            if dont_show_checkbox.isChecked():
                settings.setValue("dont_show_cpu_warning", True)

            # If user clicked "Use Cloud API", switch to cloud mode
            if clicked_button == 1:  # Use Cloud API button
                self.method_group.button(1).setChecked(True)  # Switch to Cloud
                self._on_generate()  # Start cloud generation instead
                return

        self._add_log("🚀 Starting LOCAL 3D generation (FREE - no credits required)")

        # Disable Open/Save buttons during generation
        self.btn_save_obj.setEnabled(False)
        self.btn_save_stl.setEnabled(False)
        self.btn_save_glb.setEnabled(False)

        # Start generation
        self.generate_btn.setEnabled(False)
        self.status_label.setText("Initializing local processing...")
        self.status_icon.setText("⏳")
        self.progress_bar.setValue(0)

        self.start_time = datetime.now()
        self.timer.start(1000)

        # Store generation parameters
        self._current_model = "local"
        self._current_quality = "standard"
        self._current_api_model = "local"
        self._current_generation_id = None  # No generation ID for local
        self._current_credits_deducted = 0

        # Ensure selected_file is not None
        self.worker = GenerationWorker(
            str(self.selected_file),
            "local",
            "1024",  # Resolution doesn't matter for local
            "local",  # api_model doesn't matter for local
            ["obj", "stl", "glb"],
            quality,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_generation_complete)
        self.worker.error.connect(self._on_generation_error)
        self.worker.start()

        self._add_log(
            f"🚀 Starting local 3D generation: {Path(self.selected_file).name}"
        )

    def _on_progress(self, value: int):
        """Handle progress update."""
        # Clamp value between 0-100
        value = max(0, min(100, value))
        self.progress_bar.setValue(value)

    def _on_status(self, status: str):
        """Handle status update with progress mapping."""
        # Map status messages to progress stages
        status_lower = status.lower()

        # Update progress bar based on stage
        if "initializing" in status_lower:
            self.progress_bar.setValue(5)
        elif "processing image" in status_lower:
            self.progress_bar.setValue(10)
        elif "submit" in status_lower:
            self.progress_bar.setValue(15)
        elif "processing on cloud" in status_lower or "waiting" in status_lower:
            # Extract time from status if available
            self.progress_bar.setValue(40)
        elif "generating" in status_lower or "model" in status_lower:
            self.progress_bar.setValue(70)
        elif "preparing download" in status_lower:
            self.progress_bar.setValue(85)
        elif "downloading" in status_lower:
            self.progress_bar.setValue(95)
        elif "converting" in status_lower:
            self.progress_bar.setValue(98)
        elif "complete" in status_lower:
            self.progress_bar.setValue(100)

        self.status_label.setText(status)
        self._add_log(f"📊 {status}")

    def _on_generation_complete(self, result: dict):
        """Handle generation completion."""
        self.timer.stop()
        self.generate_btn.setEnabled(True)

        # Enable Open/Save buttons for available formats
        # Show the 3D model!
        if result.get("glb") and Path(result["glb"]).exists():
            glb_path = Path(result["glb"]).absolute()
            glb_uri = glb_path.as_uri()
            base_dir = QUrl.fromLocalFile(str(glb_path.parent) + "/")

            # Use model-viewer but gracefully handle PySide6 SwiftShader WebGL failures
            # on machines without D3D11 / OpenGL.
            self.model_viewer.setHtml(
                f"""
            <html><head>
            <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"></script>
            <style>
                body {{ margin: 0; background-color: #0f172a; overflow: hidden; color: white;     
                        font-family: system-ui, sans-serif; display: flex; align-items: center; justify-content: center; }}
                #fallback {{ display: none; text-align: center; padding: 20px; }}
                .btn {{ background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; 
                       cursor: pointer; font-weight: bold; margin-top: 15px; text-decoration: none; display: inline-block; }}
                .btn:hover {{ background: #2563eb; }}
            </style>
            </head><body>
            <div id="fallback">
                <h3>⚠️ 3D Preview Unavailable</h3>
                <p>Your system's embedded hardware acceleration (WebGL) is disabled.</p>
                <p style="color: #60a5fa; margin-top: 15px;">Please use the ⬇️ Download buttons below</p>
            </div>
            
            <model-viewer id="mv" src="{glb_uri}" alt="A 3D model" auto-rotate camera-controls 
                          style="width: 100vw; height: 100vh; border: none; outline: none; position: absolute; top:0; left:0;">
            </model-viewer>
            
            <script>
                // Detect WebGL capability. If missing, destroy model-viewer and show fallback.
                try {{
                    var canvas = document.createElement('canvas');
                    var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) {{ throw new Error("No WebGL context"); }}
                }} catch (e) {{
                    document.getElementById('mv').remove();
                    document.getElementById('fallback').style.display = 'block';
                }}
            </script>
            </body></html>
            """,
                baseUrl=base_dir,
            )

        # Enable Open/Save buttons for available formats
        if result.get("obj"):
            self.btn_save_obj.setEnabled(True)
        if result.get("stl"):
            self.btn_save_stl.setEnabled(True)
        if result.get("glb"):
            self.btn_save_glb.setEnabled(True)

        self.status_label.setText("Complete!")
        self.status_icon.setText("✅")
        self.progress_bar.setValue(100)

        # Mark generation as successful in Supabase
        gen_id = getattr(self, "_current_generation_id", None)
        if gen_id and self.start_time:
            elapsed_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)
            try:
                mark_generation_complete(gen_id, success=True, time_ms=elapsed_ms)
            except Exception as e:
                print(f"[MainWindow] Failed to mark generation complete: {e}")

        # Refresh credit balance (delayed to ensure DB is updated)
        QTimer.singleShot(500, self._refresh_credit_balance)

        # Log outputs
        outputs = []
        for fmt in ["obj", "stl", "glb", "fbx", "usdz"]:
            if result.get(fmt):
                outputs.append(fmt.upper())

        self._add_log("✅ 3D model generation complete!")
        if outputs:
            self._add_log(f"📦 Outputs: {', '.join(outputs)}")

        # Save model info to Supabase (paths stored, not actual files)
        gen_id = getattr(self, "_current_generation_id", None)
        if gen_id and result:
            try:
                from core.model_storage import save_model_info_to_supabase

                # Collect model files
                model_files = {}
                for fmt in ["obj", "stl", "glb", "fbx", "usdz"]:
                    if result.get(fmt):
                        model_files[fmt] = result[fmt]

                if model_files:
                    input_name = (
                        Path(self.selected_file).name
                        if self.selected_file
                        else "unknown"
                    )
                    processing_method = getattr(self, "_current_model", "cloud_api")

                    save_result = save_model_info_to_supabase(
                        user_id=str(self.session_manager.user_id),
                        generation_id=gen_id,
                        model_files=model_files,
                        input_filename=input_name,
                        processing_method=processing_method,
                    )

                    if save_result.get("success"):
                        self._add_log("📋 Model info saved to database")
                    else:
                        self._add_log(
                            f"⚠️ DB save failed: {save_result.get('error', 'Unknown')}"
                        )
            except Exception as e:
                self._add_log(f"⚠️ Storage error: {e}")

        # Store result paths for Open/Save buttons
        self._last_result = result

        # Show beautiful completion modal (matches web app)
        is_trial = getattr(self, "_is_trial_generation", False)
        if is_trial:
            self._add_log(
                "🎉 Your first generation is FREE! Buy credits for more generations."
            )

        dialog = CompletionDialog(self, result, is_trial=is_trial)
        dialog.exec()

        if is_trial:
            self._is_trial_generation = False  # Reset flag
            # Refresh after trial prompt
            QTimer.singleShot(300, self._refresh_credit_balance)

    def _on_generation_error(self, error: str):
        """Handle generation error."""
        self.timer.stop()
        self.generate_btn.setEnabled(True)

        # Enable buttons on error (for next retry)
        # Enable buttons on error (for next retry/access to previous if any)
        self.btn_save_obj.setEnabled(True)
        self.btn_save_stl.setEnabled(True)
        self.btn_save_glb.setEnabled(True)

        self.status_label.setText(f"Error: {error}")
        self.status_icon.setText("❌")
        self._add_log(f"❌ Error: {error}")

        # Mark generation as failed — credits are refunded
        gen_id = getattr(self, "_current_generation_id", None)
        if gen_id:
            try:
                mark_generation_complete(gen_id, success=False, error=error)
                self._add_log("💰 Credits refunded due to failed generation")
                self._refresh_credit_balance()
            except Exception as e:
                print(f"[MainWindow] Failed to mark generation failed: {e}")

    def _update_timer(self):
        """Update elapsed time and ETA."""
        if self.start_time and hasattr(self, "progress_bar"):
            elapsed = datetime.now() - self.start_time
            elapsed_seconds = int(elapsed.total_seconds())
            minutes, seconds = divmod(elapsed_seconds, 60)
            self.elapsed_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")

            # Calculate ETA based on current progress
            current_value = self.progress_bar.value()
            if current_value > 5 and current_value < 100:
                # Estimate total time based on current progress
                estimated_total = (elapsed_seconds * 100) / current_value
                remaining = estimated_total - elapsed_seconds
                if remaining > 0:
                    eta_min, eta_sec = divmod(int(remaining), 60)
                    self.eta_label.setText(f"ETA: {eta_min:02d}:{eta_sec:02d}")
                else:
                    self.eta_label.setText("ETA: 00:00")
            elif current_value >= 100:
                self.eta_label.setText("ETA: 00:00")

    def _on_save_output(self, format_name: str):
        """Handle save output button click."""
        if not hasattr(self, "_last_result") or not self._last_result:
            QMessageBox.warning(self, "No Output", "No generated model available.")
            return

        format_key = format_name.lower()
        source_path = self._last_result.get(format_key)

        if not source_path or not Path(source_path).exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"{format_name.upper()} file not found. Please generate a model first.",
            )
            return

        default_name = Path(source_path).name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {format_name.upper()}",
            default_name,
            f"{format_name.upper()} Files (*.{format_name.lower()});;All Files (*)",
        )

        if file_path:
            try:
                import shutil

                shutil.copy2(source_path, file_path)
                self._add_log(f"💾 Saved {format_name.upper()}: {Path(file_path).name}")
                QMessageBox.information(
                    self, "Saved", f"File saved successfully to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not save file: {e}")

    def _on_logout(self):
        """Handle logout button click."""
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.session_manager.logout()
            self.close()
            # Re-show auth dialog
            from ui.auth_dialog import AuthDialog

            auth_dialog = AuthDialog(self.session_manager)
            if auth_dialog.exec() == AuthDialog.Accepted:
                self.show()

    def _on_show_history(self):
        """Show the history dialog."""
        from ui.history_dialog import HistoryDialog
        dialog = HistoryDialog(self)
        dialog.exec()

    def _on_show_profile(self):
        """Show the profile dialog."""
        from ui.profile_dialog import ProfileDialog
        dialog = ProfileDialog(self)
        # If user logged out from profile dialog, restart the app
        if dialog.result() == ProfileDialog.Accepted:
            # Check if session is still valid
            if not self.session_manager.is_authenticated():
                self.close()
                from ui.auth_dialog import AuthDialog
                auth_dialog = AuthDialog(self.session_manager)
                if auth_dialog.exec() == AuthDialog.Accepted:
                    self.show()

    def _add_log(self, message: str):
        """Add an entry to the activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        event.accept()
