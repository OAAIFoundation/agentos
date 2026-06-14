"""
Audit Logger for AgentOS
Tracks routing decisions, data masking, and policy enforcement in real-time
"""

import time
from typing import Dict, List, Literal
from collections import deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)

LogLevel = Literal["info", "warning", "error"]


class AuditLog:
    """Single audit log entry"""
    def __init__(
        self,
        level: LogLevel,
        category: str,
        message: str,
        details: Dict = None
    ):
        self.timestamp = time.time()
        self.level = level
        self.category = category
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "details": self.details
        }


class AuditLogger:
    """
    Thread-safe in-memory audit logger
    Stores recent logs for real-time dashboard display
    """

    def __init__(self, max_logs: int = 1000):
        """
        Initialize audit logger

        Args:
            max_logs: Maximum number of logs to keep in memory
        """
        self.logs = deque(maxlen=max_logs)
        self.lock = Lock()
        self.max_logs = max_logs

    def log(
        self,
        level: LogLevel,
        category: str,
        message: str,
        details: Dict = None
    ):
        """
        Add a new log entry

        Args:
            level: Log level (info, warning, error)
            category: Category (routing, masking, policy, etc.)
            message: Human-readable message
            details: Optional additional details
        """
        log_entry = AuditLog(level, category, message, details)

        with self.lock:
            self.logs.append(log_entry)

        # Also log to standard logger
        log_func = {
            "info": logger.info,
            "warning": logger.warning,
            "error": logger.error
        }.get(level, logger.info)

        log_func(f"[{category}] {message}")

    def info(self, category: str, message: str, details: Dict = None):
        """Log info level"""
        self.log("info", category, message, details)

    def warning(self, category: str, message: str, details: Dict = None):
        """Log warning level"""
        self.log("warning", category, message, details)

    def error(self, category: str, message: str, details: Dict = None):
        """Log error level"""
        self.log("error", category, message, details)

    def get_logs(
        self,
        level: str = "all",
        limit: int = 100,
        category: str = None
    ) -> List[Dict]:
        """
        Retrieve logs with filtering

        Args:
            level: Filter by level (all, info, warning, error, warning+)
            limit: Maximum number of logs to return
            category: Filter by category

        Returns:
            List of log dictionaries
        """
        with self.lock:
            logs_list = list(self.logs)

        # Filter by level
        if level == "warning+":
            # Warning and above (warning + error)
            logs_list = [
                log for log in logs_list
                if log.level in ("warning", "error")
            ]
        elif level == "error":
            logs_list = [log for log in logs_list if log.level == "error"]
        elif level != "all":
            logs_list = [log for log in logs_list if log.level == level]

        # Filter by category
        if category:
            logs_list = [log for log in logs_list if log.category == category]

        # Sort by timestamp (newest first)
        logs_list.sort(key=lambda x: x.timestamp, reverse=True)

        # Limit results
        logs_list = logs_list[:limit]

        return [log.to_dict() for log in logs_list]

    def clear(self):
        """Clear all logs"""
        with self.lock:
            self.logs.clear()


# Global audit logger instance
_audit_logger: AuditLogger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(max_logs=1000)
    return _audit_logger


def init_audit_logger(max_logs: int = 1000):
    """Initialize global audit logger"""
    global _audit_logger
    _audit_logger = AuditLogger(max_logs=max_logs)
    return _audit_logger
