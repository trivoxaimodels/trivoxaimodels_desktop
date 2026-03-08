"""
Credit Purchase Dialog - Improved version of Buy Credits functionality
"""

import os
import webbrowser
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QFrame,
    QGridLayout,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
    QWidget,
    QComboBox,
    QApplication,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QFont, QPixmap

from core.credit_manager import CREDIT_PACKS
from core.payment_config_sync import get_credit_packs
from core.payment_handler import get_payment_handler, PaymentHandler


class PaymentLinkWorker(QThread):
    finished_success = Signal(str)  # payment_url
    finished_error = Signal(str, str)  # title, error_message
    status_update = Signal(str)

    def __init__(self, create_link_url, pack_id, user_id):
        super().__init__()
        self.create_link_url = create_link_url
        self.pack_id = pack_id
        self.user_id = user_id

    def run(self):
        import requests
        import time

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    self.status_update.emit(f"Server waking up... Retrying (Attempt {attempt}/{max_retries})")
                else:
                    self.status_update.emit("Connecting to payment server...")
                
                response = requests.post(
                    self.create_link_url,
                    json={"pack_id": self.pack_id, "user_id": self.user_id, "source": "desktop"},
                    timeout=25,  # Give 25 seconds per request
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("payment_url"):
                        self.finished_success.emit(data["payment_url"])
                        return
                    else:
                        error_msg = data.get("error", "Unknown error")
                        self.finished_error.emit("Payment Error", f"Failed to create payment link:\n{error_msg}")
                        return
                elif response.status_code in [502, 503, 504]:
                    # These can happen during Render cold start
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue
                else:
                    self.finished_error.emit("Payment Error", f"Server returned error {response.status_code}.\nPlease try again later.")
                    return

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    continue
                else:
                    self.finished_error.emit(
                        "Timeout", 
                        "Payment server took too long to respond.\n"
                        "The server is currently warming up due to inactivity.\n"
                        "Please wait 2 minutes and try clicking 'Buy Now' again."
                    )
                    return
            except requests.exceptions.ConnectionError:
                self.finished_error.emit(
                    "Connection Error", 
                    "Cannot connect to payment server.\n"
                    "Please check your internet connection and try again."
                )
                return
            except Exception as e:
                self.finished_error.emit("Payment Error", f"An unexpected error occurred:\n{str(e)}")
                return
        
        # If loop finishes without returning, we exhausted retries
        self.finished_error.emit(
            "Timeout", 
            "Server took too long to wake up.\n"
            "Please try again in a few moments."
        )


class CreditPurchaseDialog(QDialog):
    """
    Dialog for purchasing credits with dynamic gateway integration.
    """

    def __init__(
        self,
        parent=None,
        current_balance: int = 0,
        user_id: str = "",
        user_email: str = "",
    ):
        super().__init__(parent)
        self.current_balance = current_balance
        self.user_id = user_id
        self.user_email = user_email
        self.setWindowTitle("Buy Credits")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        # Initialize payment handler (with error handling)
        try:
            self.payment_handler: Optional[PaymentHandler] = get_payment_handler()
        except Exception as e:
            print(f"[CreditPurchaseDialog] Payment handler init error: {e}")
            self.payment_handler = None

        # Connect payment handler signals
        if self.payment_handler:
            try:
                self.payment_handler.payment_completed.connect(self._on_payment_completed)
                self.payment_handler.payment_failed.connect(self._on_payment_failed)
            except Exception as e:
                print(f"[CreditPurchaseDialog] Signal connect error: {e}")

        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("💳 Purchase Credits")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e2e8f0;")
        layout.addWidget(title)

        # Current Balance
        balance_frame = QFrame()
        balance_frame.setObjectName("infoCard")
        balance_layout = QHBoxLayout(balance_frame)
        balance_layout.setSpacing(8)
        balance_layout.setContentsMargins(16, 12, 16, 12)

        balance_label = QLabel("Current Balance:")
        balance_label.setStyleSheet("color: #94a3b8; font-size: 14px;")
        balance_value = QLabel(f"{self.current_balance} credits")
        balance_value.setStyleSheet(
            "color: #4ade80; font-size: 16px; font-weight: bold;"
        )

        balance_layout.addWidget(balance_label)
        balance_layout.addStretch()
        balance_layout.addWidget(balance_value)

        layout.addWidget(balance_frame)

        # Credit Packs Section
        packs_group = QGroupBox("Credit Packs")
        packs_group.setObjectName("sectionCard")
        packs_layout = QVBoxLayout(packs_group)
        packs_layout.setSpacing(12)
        packs_layout.setContentsMargins(16, 20, 16, 16)

        # Create scroll area for packs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("contentScroll")

        # Container widget for packs
        packs_container = QWidget()
        packs_layout_inner = QVBoxLayout(packs_container)
        packs_layout_inner.setSpacing(12)

        # Add credit packs (with error handling for network calls)
        try:
            active_gateway = self._get_active_gateway()
        except Exception:
            active_gateway = "gumroad"
        try:
            active_packs = get_credit_packs() or CREDIT_PACKS
        except Exception:
            active_packs = CREDIT_PACKS

        # Get the actual currency from admin config
        self._active_gateway = active_gateway
        self._currency = self._get_currency()
        self._currency_sym = self._get_currency_symbol()

        for pack_id, pack_info in active_packs.items():
            # Check if pack has ID for the active gateway
            gateway_key = f"{active_gateway}_id"
            if pack_info.get(gateway_key) or pack_info.get(
                "gumroad_id"
            ):  # Fallback to gumroad_id for backwards compat
                pack_card = self._create_pack_card(pack_id, pack_info, active_gateway)
                packs_layout_inner.addWidget(pack_card)

        # Add empty state if no packs
        has_packs = False
        for pack in active_packs.values():
            if pack.get(f"{active_gateway}_id") or pack.get("gumroad_id"):
                has_packs = True
                break

        if not has_packs:
            empty_label = QLabel("No credit packs available")
            empty_label.setStyleSheet("color: #64748b; font-size: 14px;")
            empty_label.setAlignment(Qt.AlignCenter)
            packs_layout_inner.addWidget(empty_label)

        scroll.setWidget(packs_container)
        packs_layout.addWidget(scroll)

        layout.addWidget(packs_group)

        # Instructions
        instructions = QLabel(
            "💡 After purchasing, your credits will be automatically added to your account. "
            "Check back in a few minutes if you don't see them immediately."
        )
        instructions.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        buttons_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_balance)
        buttons_layout.addWidget(refresh_btn)

        layout.addLayout(buttons_layout)

    def _create_pack_card(
        self, pack_id: str, pack_info: Dict[str, Any], active_gateway: str
    ) -> QFrame:
        """Create a credit pack card."""
        card = QFrame()
        card.setObjectName("packCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            #packCard {
                background-color: #1a2332;
                border: 1px solid #1e3a5f;
                border-radius: 8px;
                padding: 16px;
            }
            #packCard:hover {
                border-color: #3b82f6;
                background-color: #1e293b;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Pack header
        header_layout = QHBoxLayout()

        # Credits badge
        badge = QLabel(f"+{pack_info['credits']}")
        badge.setStyleSheet("""
            background-color: #3b82f6;
            color: white;
            border-radius: 20px;
            padding: 4px 12px;
            font-weight: bold;
            font-size: 14px;
        """)
        header_layout.addWidget(badge)

        # Pack name
        name = QLabel(pack_info["name"])
        name.setStyleSheet("font-size: 16px; font-weight: bold; color: #e2e8f0;")
        header_layout.addWidget(name)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Price — use currency from admin config
        price_val = pack_info["price"]
        currency_sym = getattr(self, '_currency_sym', '₹')
        price = QLabel(f"{currency_sym}{price_val}")
        price.setStyleSheet("font-size: 20px; font-weight: bold; color: #4ade80;")
        price.setAlignment(Qt.AlignCenter)
        layout.addWidget(price)

        # Value per credit
        if pack_info["credits"] > 0:
            value_per = pack_info["price"] / pack_info["credits"]
            value_label = QLabel(f"{currency_sym}{value_per:.2f} per credit")
            value_label.setStyleSheet("color: #64748b; font-size: 12px;")
            value_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(value_label)

        # Buy button
        buy_btn = QPushButton("🛒 Buy Now")
        buy_btn.setObjectName("primaryButton")
        buy_btn.setCursor(Qt.PointingHandCursor)
        buy_btn.clicked.connect(lambda: self._purchase_pack(pack_id, active_gateway))
        layout.addWidget(buy_btn)

        # Store pack ID for later use
        card.pack_id = pack_id

        return card

    def _get_active_gateway(self) -> str:
        """Get the current active payment gateway."""
        try:
            from core.payment_config_sync import get_payment_config_sync
            return get_payment_config_sync().get_active_provider()
        except Exception:
            return "gumroad"

    def _get_currency(self) -> str:
        """Get the payment currency from admin config."""
        try:
            from core.payment_config_sync import get_payment_config_sync
            return get_payment_config_sync().get_currency()
        except Exception:
            return "INR"

    def _get_currency_symbol(self) -> str:
        """Get the currency symbol for display."""
        currency = getattr(self, '_currency', 'INR')
        symbols = {
            'INR': '₹',
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
        }
        return symbols.get(currency, currency + ' ')

    def _purchase_pack(self, pack_id: str, active_gateway: str):
        """Handle purchase of a credit pack using the active gateway."""
        active_packs = get_credit_packs() or CREDIT_PACKS
        pack_info = active_packs.get(pack_id)
        if not pack_info:
            QMessageBox.warning(self, "Error", "This credit pack is not available.")
            return

        # Get user ID from parent session manager
        user_id = self.user_id
        if not user_id and hasattr(self.parent(), "session_manager"):
            user_id = self.parent().session_manager.user_id

        if not user_id:
            QMessageBox.warning(
                self, "Error", "User not logged in. Please log in to purchase credits."
            )
            return

        if active_gateway == "razorpay":
            self._purchase_with_razorpay(pack_id, pack_info, user_id)
        else:
            # Default: Gumroad
            self._purchase_with_gumroad(pack_id, pack_info)

    def _purchase_with_razorpay(
        self, pack_id: str, pack_info: Dict[str, Any], user_id: str
    ):
        """Purchase credits using Razorpay via the web app's payment link API."""
        # The web server has the Razorpay API keys and creates a payment link
        # Desktop app calls the same endpoint the web frontend uses
        web_base = os.getenv(
            "WEB_API_URL", "https://voxelcraft.onrender.com/api/v1"
        )
        if web_base.endswith("/api/v1"):
            web_base = web_base.replace("/api/v1", "")
        WEB_BASE = web_base.rstrip("/")

        create_link_url = f"{WEB_BASE}/api/razorpay/create-link"

        # Show waiting dialog
        self.progress_dialog = QProgressDialog(
            "Waking up payment server... Please wait a moment.", 
            "Cancel", 0, 0, self
        )
        self.progress_dialog.setWindowTitle("Processing Request")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        
        # Disable the cancel button intentionally to prevent cancelling requests mid-flight
        cancel_btn = self.progress_dialog.findChild(QPushButton)
        if cancel_btn:
            cancel_btn.hide()
            
        self.progress_dialog.show()

        # Start background worker
        self.worker = PaymentLinkWorker(create_link_url, pack_id, user_id)
        
        def on_status_update(status_text):
            if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
                self.progress_dialog.setLabelText(status_text)
                
        def on_success(payment_url):
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()
            
            # Start polling immediately without blocking the UI
            self._start_polling()
            
            # Open browser for payment
            webbrowser.open(payment_url)
            
            # Update the UI internally to show waiting status
            self.buy_btn = self.findChild(QPushButton, "buy_button")
            if self.buy_btn:
                self.buy_btn.setText("Waiting for Payment...")
                self.buy_btn.setEnabled(False)
            
        def on_error(title, msg):
            if hasattr(self, 'progress_dialog'):
                self.progress_dialog.close()
            QMessageBox.critical(self, title, msg)

        self.worker.status_update.connect(on_status_update)
        self.worker.finished_success.connect(on_success)
        self.worker.finished_error.connect(on_error)
        
        self.worker.start()

    def _purchase_with_gumroad(self, pack_id: str, pack_info: Dict[str, Any]):
        """Purchase credits using Gumroad."""
        gumroad_id = pack_info.get("gumroad_id")
        if not gumroad_id:
            QMessageBox.warning(self, "Error", "Payment not available for this pack.")
            return

        purchase_url = f"https://VoxelCraft.gumroad.com/l/{gumroad_id}"
        webbrowser.open(purchase_url)

        QMessageBox.information(
            self,
            "Purchase Started",
            f"✅ You will be redirected to complete your purchase using Gumroad.\n\n"
            f"Pack: {pack_info['name']}\n"
            f"Price: {getattr(self, '_currency_sym', '₹')}{pack_info['price']}\n\n"
            f"Your credits will be added automatically after payment.",
        )

        # Start polling for balance update
        self._start_polling()

    def _on_payment_poll_result(self, success: bool, credits_added: int):
        """Handle payment polling result."""
        if success:
            # PaymentHandler signals will handle the success message
            pass
        else:
            QMessageBox.warning(
                self,
                "Payment Pending",
                "⏰ Payment is still processing. Your credits may take a few minutes to appear.\n\n"
                "If you don't see your credits after 10 minutes, please contact support.",
            )

    def _start_polling(self):
        """Start polling for credit balance update."""
        from PySide6.QtCore import QTimer

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_balance_update)
        self._poll_timer.start(5000)  # Check every 5 seconds

        # Baseline is strictly from when the dialog was opened to prevent race conditions
        self._poll_initial_balance = self.current_balance
        self._poll_count = 0

    def _check_balance_update(self):
        """Check if credits have been updated."""
        from core.credit_manager import get_user_balance

        self._poll_count += 1

        try:
            balance_info = get_user_balance(self.parent().session_manager.user_id)
            new_balance = balance_info.get("credits_balance", 0)

            if new_balance > self._poll_initial_balance:
                # Credits added!
                self._poll_timer.stop()
                added = new_balance - self._poll_initial_balance

                QMessageBox.information(
                    self,
                    "Purchase Complete!",
                    f"✅ Credits successfully added!\n\n"
                    f"Added: +{added} credits\n"
                    f"New balance: {new_balance} credits",
                )

                # Emit signal to refresh parent
                if hasattr(self.parent(), "_refresh_credit_balance"):
                    self.parent()._refresh_credit_balance()

                self.accept()
                return

        except Exception:
            pass

        # Timeout after 5 minutes (60 * 5 seconds)
        if self._poll_count > 60:
            self._poll_timer.stop()
            QMessageBox.warning(
                self,
                "Polling Timeout",
                "⏰ Credit polling timed out. Your credits may still be processing.\n\n"
                "If you don't see your credits after 10 minutes, please contact support.",
            )

    def _on_payment_completed(self, order_id: str, credits_added: int):
        """Handle successful payment completion."""
        QMessageBox.information(
            self,
            "Payment Successful!",
            f"✅ Payment completed successfully!\n\n"
            f"Order ID: {order_id}\n"
            f"Credits Added: +{credits_added}\n\n"
            f"Your credits have been added to your account.",
        )

        # Refresh parent balance
        if hasattr(self.parent(), "_refresh_credit_balance"):
            self.parent()._refresh_credit_balance()

        self.accept()

    def _on_payment_failed(self, order_id: str, error_message: str):
        """Handle payment failure."""
        QMessageBox.critical(
            self,
            "Payment Failed",
            f"❌ Payment failed for order: {order_id}\n\n"
            f"Error: {error_message}\n\n"
            f"Please try again or contact support if the issue persists.",
        )

    def _refresh_balance(self):
        """Refresh the current balance display."""
        if hasattr(self.parent(), "_refresh_credit_balance"):
            self.parent()._refresh_credit_balance()

            # Update current balance
            try:
                from core.credit_manager import get_user_balance

                balance_info = get_user_balance(self.parent().session_manager.user_id)
                self.current_balance = balance_info.get("credits_balance", 0)

                # Recreate the dialog to show updated balance
                self.close()
                new_dialog = CreditPurchaseDialog(self.parent(), self.current_balance)
                new_dialog.exec()
            except Exception:
                pass
