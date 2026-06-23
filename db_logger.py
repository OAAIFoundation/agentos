"""
Database Logger - SQLite-based persistent log storage
Stores request logs for long-term analysis and statistics
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseLogger:
    """SQLite-based logger for request logs"""

    def __init__(self, db_path: str = "data/router_logs.db"):
        """
        Initialize database logger

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()

    def _ensure_db_directory(self):
        """Create database directory if it doesn't exist"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create request_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT,
                    provider TEXT,
                    model TEXT,
                    original_model TEXT,
                    stream INTEGER,
                    message_preview TEXT,
                    status_code INTEGER,
                    error_type TEXT,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON request_logs(timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_level_category
                ON request_logs(level, category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_provider
                ON request_logs(provider)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON request_logs(created_at DESC)
            """)

            logger.info(f"Database initialized at {self.db_path}")

    def add_log(self, log_entry: Dict[str, Any]):
        """
        Add a log entry to database

        Args:
            log_entry: Log entry dict with keys: timestamp, level, category, message, details
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Extract details for indexed columns
                details = log_entry.get("details", {})

                cursor.execute("""
                    INSERT INTO request_logs (
                        timestamp, level, category, message,
                        provider, model, original_model, stream,
                        message_preview, status_code, error_type, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_entry.get("timestamp"),
                    log_entry.get("level"),
                    log_entry.get("category"),
                    log_entry.get("message"),
                    details.get("target_provider"),
                    details.get("target_model"),
                    details.get("original_model"),
                    1 if details.get("stream") else 0,
                    details.get("message_preview"),
                    details.get("status_code"),
                    details.get("error_type"),
                    json.dumps(details) if details else None
                ))

        except Exception as e:
            logger.error(f"Failed to add log to database: {e}")

    def get_logs(
        self,
        level: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query logs from database

        Args:
            level: Filter by log level (info, error, etc.)
            category: Filter by category (routing, system, etc.)
            provider: Filter by provider name
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of records
            offset: Offset for pagination

        Returns:
            List of log entries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Build query dynamically
                query = "SELECT * FROM request_logs WHERE 1=1"
                params = []

                if level and level != "all":
                    query += " AND level = ?"
                    params.append(level)

                if category:
                    query += " AND category = ?"
                    params.append(category)

                if provider:
                    query += " AND provider = ?"
                    params.append(provider)

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Convert to dict format matching original log structure
                logs = []
                for row in rows:
                    log = {
                        "timestamp": row["timestamp"],
                        "level": row["level"],
                        "category": row["category"],
                        "message": row["message"],
                        "details": {}
                    }

                    # Reconstruct details from indexed columns
                    if row["provider"]:
                        log["details"]["target_provider"] = row["provider"]
                    if row["model"]:
                        log["details"]["target_model"] = row["model"]
                    if row["original_model"]:
                        log["details"]["original_model"] = row["original_model"]
                    if row["stream"] is not None:
                        log["details"]["stream"] = bool(row["stream"])
                    if row["message_preview"]:
                        log["details"]["message_preview"] = row["message_preview"]
                    if row["status_code"]:
                        log["details"]["status_code"] = row["status_code"]
                    if row["error_type"]:
                        log["details"]["error_type"] = row["error_type"]

                    # Merge with full details JSON if exists
                    if row["details"]:
                        try:
                            full_details = json.loads(row["details"])
                            log["details"].update(full_details)
                        except:
                            pass

                    logs.append(log)

                return logs

        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return []

    def get_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            Statistics dict
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Build date filter
                date_filter = "WHERE 1=1"
                params = []

                if start_date:
                    date_filter += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    date_filter += " AND timestamp <= ?"
                    params.append(end_date)

                # Total requests
                cursor.execute(f"""
                    SELECT COUNT(*) as total
                    FROM request_logs
                    {date_filter}
                    AND category = 'routing' AND level = 'info'
                """, params)
                total_requests = cursor.fetchone()["total"]

                # By provider
                cursor.execute(f"""
                    SELECT provider, COUNT(*) as count
                    FROM request_logs
                    {date_filter}
                    AND category = 'routing' AND level = 'info'
                    AND provider IS NOT NULL
                    GROUP BY provider
                    ORDER BY count DESC
                """, params)
                by_provider = {row["provider"]: row["count"] for row in cursor.fetchall()}

                # By model
                cursor.execute(f"""
                    SELECT model, COUNT(*) as count
                    FROM request_logs
                    {date_filter}
                    AND category = 'routing' AND level = 'info'
                    AND model IS NOT NULL
                    GROUP BY model
                    ORDER BY count DESC
                """, params)
                by_model = {row["model"]: row["count"] for row in cursor.fetchall()}

                # Error count
                cursor.execute(f"""
                    SELECT COUNT(*) as total
                    FROM request_logs
                    {date_filter}
                    AND level = 'error'
                """, params)
                error_count = cursor.fetchone()["total"]

                return {
                    "total_requests": total_requests,
                    "by_provider": by_provider,
                    "by_model": by_model,
                    "error_count": error_count
                }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_requests": 0,
                "by_provider": {},
                "by_model": {},
                "error_count": 0
            }

    def clear_logs(self, before_date: Optional[str] = None) -> int:
        """
        Clear logs from database

        Args:
            before_date: If provided, only delete logs before this date (ISO format)

        Returns:
            Number of deleted records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if before_date:
                    cursor.execute("""
                        DELETE FROM request_logs WHERE timestamp < ?
                    """, (before_date,))
                else:
                    cursor.execute("DELETE FROM request_logs")

                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} log records")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")
            return 0

    def get_log_count(self) -> int:
        """Get total number of logs in database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM request_logs")
                return cursor.fetchone()["count"]
        except Exception as e:
            logger.error(f"Failed to get log count: {e}")
            return 0

    def vacuum(self):
        """Optimize database (reclaim space after deletions)"""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database optimized")
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
