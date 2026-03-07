"""
History Dialog for Desktop App

Shows generation history, credit history, and purchase history.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QComboBox, QDateEdit, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon, QColor
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

from core.user_history_manager import (
    get_generation_history,
    get_credit_history,
    get_purchase_history
)
from core.session_manager import get_session_manager
from core.logger import get_logger

logger = get_logger(__name__)


class HistoryDialog(QDialog):
    """Dialog showing user history (generations, credits, purchases)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("History - Voxel Craft")
        self.setMinimumSize(900, 600)
        self._session_manager = get_session_manager()
        self._user_id = self._session_manager.get_user_id() if self._session_manager else None
        
        if not self._user_id:
            QMessageBox.warning(self, "Not Logged In", "Please log in to view history.")
            self.reject()
            return
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📊 Your History")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Generation History Tab
        self.gen_tab = self._create_generation_tab()
        self.tabs.addTab(self.gen_tab, "🎨 Generations")
        
        # Credit History Tab
        self.credit_tab = self._create_credit_tab()
        self.tabs.addTab(self.credit_tab, "💳 Credits")
        
        # Purchase History Tab
        self.purchase_tab = self._create_purchase_tab()
        self.tabs.addTab(self.purchase_tab, "🛒 Purchases")
        
        layout.addWidget(self.tabs)
        
        # Refresh button
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_data)
        btn_layout.addStretch()
        btn_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_generation_tab(self) -> QWidget:
        """Create the generation history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info = QLabel("View your 3D model generation history")
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Table
        self.gen_table = QTableWidget()
        self.gen_table.setColumnCount(7)
        self.gen_table.setHorizontalHeaderLabels([
            "Date", "Type", "Model", "Prompt", "Status", "Credits", "Time"
        ])
        self.gen_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.gen_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.gen_table.setAlternatingRowColors(True)
        layout.addWidget(self.gen_table)
        
        return widget
    
    def _create_credit_tab(self) -> QWidget:
        """Create the credit history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info = QLabel("View your credit transactions")
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Table
        self.credit_table = QTableWidget()
        self.credit_table.setColumnCount(5)
        self.credit_table.setHorizontalHeaderLabels([
            "Date", "Type", "Amount", "Balance After", "Description"
        ])
        self.credit_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.credit_table.setAlternatingRowColors(True)
        layout.addWidget(self.credit_table)
        
        return widget
    
    def _create_purchase_tab(self) -> QWidget:
        """Create the purchase history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info = QLabel("View your payment and purchase history")
        info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info)
        
        # Table
        self.purchase_table = QTableWidget()
        self.purchase_table.setColumnCount(6)
        self.purchase_table.setHorizontalHeaderLabels([
            "Date", "ID", "Amount", "Currency", "Status", "Method"
        ])
        self.purchase_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.purchase_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.purchase_table.setAlternatingRowColors(True)
        layout.addWidget(self.purchase_table)
        
        return widget
    
    def _load_data(self):
        """Load all history data."""
        if not self._user_id:
            return
        
        self._load_generation_history()
        self._load_credit_history()
        self._load_purchase_history()
    
    def _load_generation_history(self):
        """Load generation history into table."""
        try:
            history = get_generation_history(self._user_id)
            self.gen_table.setRowCount(len(history))
            
            for row, item in enumerate(history):
                # Date
                date_str = item.get("created_at", "")
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                self.gen_table.setItem(row, 0, QTableWidgetItem(date_str))
                
                # Type
                gen_type = item.get("generation_type", "image")
                self.gen_table.setItem(row, 1, QTableWidgetItem(gen_type.title()))
                
                # Model
                model = item.get("model", "tripo3d")
                self.gen_table.setItem(row, 2, QTableWidgetItem(model))
                
                # Prompt
                prompt = item.get("prompt", item.get("image_url", ""))[:100]
                self.gen_table.setItem(row, 3, QTableWidgetItem(prompt))
                
                # Status
                status = item.get("status", "unknown")
                status_item = QTableWidgetItem(status.upper())
                if status == "completed":
                    status_item.setBackground(QColor("#d4edda"))
                elif status == "failed":
                    status_item.setBackground(QColor("#f8d7da"))
                elif status == "pending":
                    status_item.setBackground(QColor("#fff3cd"))
                self.gen_table.setItem(row, 4, status_item)
                
                # Credits
                credits = item.get("credits_used", 0)
                self.gen_table.setItem(row, 5, QTableWidgetItem(str(credits)))
                
                # Time
                time_taken = item.get("time_taken", "N/A")
                self.gen_table.setItem(row, 6, QTableWidgetItem(str(time_taken)))
            
            self.gen_table.resizeRowsToContents()
            
        except Exception as e:
            logger.error(f"Failed to load generation history: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load generation history: {e}")
    
    def _load_credit_history(self):
        """Load credit history into table."""
        try:
            history = get_credit_history(self._user_id)
            self.credit_table.setRowCount(len(history))
            
            for row, item in enumerate(history):
                # Date
                date_str = item.get("created_at", "")
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                self.credit_table.setItem(row, 0, QTableWidgetItem(date_str))
                
                # Type
                tx_type = item.get("transaction_type", "unknown")
                self.credit_table.setItem(row, 1, QTableWidgetItem(tx_type.title()))
                
                # Amount
                amount = item.get("amount", 0)
                amount_str = f"+{amount}" if amount > 0 else str(amount)
                amount_item = QTableWidgetItem(amount_str)
                if amount > 0:
                    amount_item.setForeground(QColor("#28a745"))
                elif amount < 0:
                    amount_item.setForeground(QColor("#dc3545"))
                self.credit_table.setItem(row, 2, amount_item)
                
                # Balance After
                balance = item.get("balance_after", 0)
                self.credit_table.setItem(row, 3, QTableWidgetItem(str(balance)))
                
                # Description
                description = item.get("description", "-")
                self.credit_table.setItem(row, 4, QTableWidgetItem(description))
            
            self.credit_table.resizeRowsToContents()
            
        except Exception as e:
            logger.error(f"Failed to load credit history: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load credit history: {e}")
    
    def _load_purchase_history(self):
        """Load purchase history into table."""
        try:
            history = get_purchase_history(self._user_id)
            self.purchase_table.setRowCount(len(history))
            
            for row, item in enumerate(history):
                # Date
                date_str = item.get("created_at", "")
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                self.purchase_table.setItem(row, 0, QTableWidgetItem(date_str))
                
                # ID (shortened)
                tx_id = item.get("id", "")[:12]
                self.purchase_table.setItem(row, 1, QTableWidgetItem(tx_id))
                
                # Amount
                amount = item.get("amount", 0)
                self.purchase_table.setItem(row, 2, QTableWidgetItem(str(amount)))
                
                # Currency
                currency = item.get("currency", "INR")
                self.purchase_table.setItem(row, 3, QTableWidgetItem(currency))
                
                # Status
                status = item.get("status", "unknown")
                status_item = QTableWidgetItem(status.upper())
                if status == "completed":
                    status_item.setBackground(QColor("#d4edda"))
                elif status == "failed":
                    status_item.setBackground(QColor("#f8d7da"))
                elif status == "pending":
                    status_item.setBackground(QColor("#fff3cd"))
                self.purchase_table.setItem(row, 4, status_item)
                
                # Method
                method = item.get("payment_method", item.get("gateway", "-"))
                self.purchase_table.setItem(row, 5, QTableWidgetItem(method))
            
            self.purchase_table.resizeRowsToContents()
            
        except Exception as e:
            logger.error(f"Failed to load purchase history: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load purchase history: {e}")


def show_history_dialog(parent=None):
    """Show the history dialog."""
    dialog = HistoryDialog(parent)
    dialog.exec()
