"""
Log display widget for the application.

This module provides a specialized text widget for displaying log messages with
color coding, filtering, and re-rendering capabilities.
"""

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QCheckBox, QLabel
from PySide6.QtGui import QTextCursor
from typing import Optional

from ui.gui_logging import LogRecord, GuiLogHandler


class LogDisplayWidget(QWidget):
    """
    A widget for displaying log messages with color coding and filtering capabilities.
    
    Features:
    - Color-coded log levels (DEBUG=grey, INFO=black, WARNING=orange, ERROR=red)
    - Debug logging toggle checkbox
    - Auto-scroll to bottom
    - Re-rendering of all logs when debug filter changes
    """

    def __init__(self, log_handler: GuiLogHandler, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_handler = log_handler
        self.show_debug = False

        self.setup_ui()
        self.connect_signals()

        # Initial rendering of existing logs
        self.re_render_logs()

    def setup_ui(self) -> None:
        """Setup the log display UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Header with debug checkbox
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Connection Log:"))
        
        # Add stretch to push checkbox to the right
        header_layout.addStretch()
        
        # Debug logging checkbox
        self.debug_checkbox = QCheckBox("Show Debug Logs")
        self.debug_checkbox.setChecked(self.show_debug)
        self.debug_checkbox.stateChanged.connect(self.on_debug_toggle)
        header_layout.addWidget(self.debug_checkbox)
        
        layout.addLayout(header_layout)
        
        # Log text display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(150)
        layout.addWidget(self.log_display)

    def connect_signals(self) -> None:
        """Connect signals from the log handler"""
        self.log_handler.signal_emitter.log_record_added.connect(self.on_log_record_added)
        self.log_handler.signal_emitter.log_cleared.connect(self.on_logs_cleared)

    def on_debug_toggle(self, state: int) -> None:
        """Handle debug checkbox toggle"""
        self.show_debug = bool(state)
        self.re_render_logs()


    def on_log_record_added(self, record: LogRecord) -> None:
        """Handle new log record added"""
        # Only display if it meets the current filter criteria
        min_level = logging.DEBUG if self.show_debug else logging.INFO
        if record.level >= min_level:
            self.append_log_record(record)

    def on_logs_cleared(self) -> None:
        """Handle logs cleared event"""
        self.log_display.clear()

    def re_render_logs(self) -> None:
        """Re-render all logs based on current filter settings"""
        # Clear current display
        self.log_display.clear()

        # Get filtered records
        min_level = logging.DEBUG if self.show_debug else logging.INFO
        records = self.log_handler.get_records(min_level)

        # Display all filtered records
        for record in records:
            self.append_log_record(record)


    def append_log_record(self, record: LogRecord) -> None:
        """Append a single log record to the display with color coding"""
        # Define HTML colors for different log levels
        color_map = {
            logging.DEBUG: "#808080",      # Grey
            logging.INFO: "#000000",       # Black
            logging.WARNING: "#FFA500",    # Orange
            logging.ERROR: "#FF0000",      # Red
            logging.CRITICAL: "#FF0000"    # Red
        }

        # Get color for the log level
        color = color_map.get(record.level, color_map[logging.INFO])

        # Create HTML formatted message
        html_message = f'<span style="color: {color};">{record.formatted_message}</span>'

        # Move cursor to end and insert HTML
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html_message + "<br>")

        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self) -> None:
        """Clear all logs from display and handler"""
        self.log_handler.clear_records()

    def get_debug_enabled(self) -> bool:
        """Get current debug logging state"""
        return self.show_debug

    def set_debug_enabled(self, enabled: bool) -> None:
        """Set debug logging state"""
        self.debug_checkbox.setChecked(enabled)
        # The state change will trigger on_debug_toggle automatically


