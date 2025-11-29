"""
GUI logging components for the application.

This module provides logging handlers and utilities specifically designed for GUI applications,
including record storage for re-rendering and signal emission for thread-safe GUI updates.
"""

import logging
from typing import List
from PySide6.QtCore import QObject, Signal


class LogRecord:
    """Enhanced log record that stores all necessary information for GUI display"""
    
    def __init__(self, record: logging.LogRecord, formatted_message: str):
        self.timestamp = record.created
        self.level = record.levelno
        self.level_name = record.levelname
        self.message = record.getMessage()
        self.formatted_message = formatted_message
        self.module = record.module
        self.funcName = record.funcName
        self.lineno = record.lineno


class LogSignalEmitter(QObject):
    """Signal emitter for thread-safe GUI logging updates"""
    log_record_added = Signal(object)  # LogRecord object
    log_cleared = Signal()


class GuiLogHandler(logging.Handler):
    """
    Custom logging handler that stores log records and emits signals for GUI updates.
    
    This handler maintains a list of log records that can be used for re-rendering
    the log display with different filtering options (e.g., showing/hiding debug logs).
    """

    def __init__(self, signal_emitter: LogSignalEmitter, max_records: int = 1000):
        super().__init__()
        self.signal_emitter = signal_emitter
        self.max_records = max_records
        self.records: List[LogRecord] = []
        
        # Set up default formatter
        self.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record, store it, and signal the GUI"""
        try:
            # Format the message for display
            import time
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created))
            milliseconds = int((record.created - int(record.created)) * 1000)
            formatted_message = f"{timestamp},{milliseconds:03d} - {record.getMessage()}"

            # Create our enhanced log record
            gui_record = LogRecord(record, formatted_message)

            # Store the record
            self.records.append(gui_record)

            # Maintain max records limit
            if len(self.records) > self.max_records:
                self.records.pop(0)

            # Emit signal for GUI update
            self.signal_emitter.log_record_added.emit(gui_record)

        except Exception:
            # Avoid recursive logging errors
            self.handleError(record)

    def get_records(self, min_level: int = logging.INFO) -> List[LogRecord]:
        """
        Get all stored log records at or above the specified level.
        
        Args:
            min_level: Minimum logging level to include (e.g., logging.DEBUG, logging.INFO)
            
        Returns:
            List of LogRecord objects filtered by level
        """
        return [record for record in self.records if record.level >= min_level]

    def clear_records(self) -> None:
        """Clear all stored log records and emit clear signal"""
        self.records.clear()
        self.signal_emitter.log_cleared.emit()


