"""
Session Manager for Multi-Turn Conversation State Persistence
Manages session lifecycle with TTL (Time-To-Live) and memory cleanup
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Optional, Tuple
from threading import Lock
from dataclasses import dataclass, field
from data_masking import MaskingStore

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    Single session state container
    Holds the masking store and activity timestamp for one conversation session
    """
    session_id: str
    store: MaskingStore
    last_active: float = field(default_factory=time.time)

    def touch(self):
        """Update last active timestamp"""
        self.last_active = time.time()


class SessionStorage:
    """
    Thread-safe singleton session storage with TTL management

    Maintains a global registry of all active sessions, each with:
    - session_id: Unique identifier from client header
    - store: Pseudonym mapping table (real_to_fake + fake_to_real)
    - last_active: Timestamp for TTL eviction
    """

    _instance: Optional['SessionStorage'] = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize session storage with configuration

        Args:
            config: Session management configuration from config.yaml
        """
        # Skip reinitialization for singleton
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.sessions: Dict[str, SessionState] = {}
        self.data_lock = Lock()

        # Configuration
        self.enabled = False
        self.session_header = "X-Session-ID"  # Default header name
        self.ttl_seconds = 1800  # 30 minutes default
        self.cleanup_interval = 60  # 1 minute default

        if config:
            self.enabled = config.get('enabled', False)
            self.session_header = config.get('session_header', 'X-Session-ID')
            self.ttl_seconds = config.get('ttl_seconds', 1800)
            self.cleanup_interval = config.get('cleanup_interval', 60)

        logger.info(
            f"[SessionStorage] Initialized (enabled={self.enabled}, "
            f"ttl={self.ttl_seconds}s, cleanup_interval={self.cleanup_interval}s)"
        )

    def get_or_create_session(self, session_id: Optional[str] = None) -> Tuple[str, MaskingStore]:
        """
        Retrieve existing session or create new one

        Args:
            session_id: Session identifier from client header (None = auto-generate)

        Returns:
            Tuple of (session_id, masking_store)
        """
        if not self.enabled:
            # Session management disabled, return ephemeral store
            return "ephemeral", MaskingStore()

        # Auto-generate session ID if not provided
        if not session_id:
            session_id = f"auto-{uuid.uuid4().hex[:8]}"

        with self.data_lock:
            if session_id in self.sessions:
                # Existing session - touch and return
                session_state = self.sessions[session_id]
                session_state.touch()
                logger.debug(f"[SessionStorage] Retrieved session '{session_id}' (reused store)")
                return session_id, session_state.store
            else:
                # New session - create fresh store
                new_store = MaskingStore()
                new_state = SessionState(session_id=session_id, store=new_store)
                self.sessions[session_id] = new_state
                logger.info(f"[SessionStorage] Created new session '{session_id}'")
                return session_id, new_store

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions based on TTL

        Returns:
            Number of sessions evicted
        """
        if not self.enabled:
            return 0

        current_time = time.time()
        expired_sessions = []

        with self.data_lock:
            for session_id, session_state in list(self.sessions.items()):
                age = current_time - session_state.last_active
                if age > self.ttl_seconds:
                    expired_sessions.append(session_id)
                    # Remove from memory
                    del self.sessions[session_id]

        # Log evictions
        if expired_sessions:
            logger.warning(
                f"\033[93m[SessionStorage] Evicted {len(expired_sessions)} expired sessions "
                f"to free memory: {expired_sessions}\033[0m"
            )

        return len(expired_sessions)

    def get_active_session_count(self) -> int:
        """Get count of currently active sessions"""
        with self.data_lock:
            return len(self.sessions)

    def manually_expire_session(self, session_id: str, timestamp: float):
        """
        Manually set session's last_active timestamp (for testing)

        Args:
            session_id: Session to modify
            timestamp: Unix timestamp to set as last_active
        """
        with self.data_lock:
            if session_id in self.sessions:
                self.sessions[session_id].last_active = timestamp
                logger.debug(f"[SessionStorage] Manually set session '{session_id}' last_active={timestamp}")


# Global singleton instance
_global_session_storage: Optional[SessionStorage] = None


def initialize_session_storage(config: Optional[Dict] = None) -> SessionStorage:
    """
    Factory function to initialize global session storage

    Args:
        config: Session management configuration from config.yaml

    Returns:
        SessionStorage singleton instance
    """
    global _global_session_storage
    if _global_session_storage is None:
        _global_session_storage = SessionStorage(config)
    return _global_session_storage


def get_session_storage() -> Optional[SessionStorage]:
    """Get global session storage instance"""
    return _global_session_storage


async def session_cleanup_task(session_storage: SessionStorage):
    """
    Background async task for periodic session cleanup

    Args:
        session_storage: SessionStorage instance to manage
    """
    if not session_storage.enabled:
        logger.info("[SessionCleanup] Session management disabled, cleanup task exiting")
        return

    logger.info(
        f"[SessionCleanup] Background cleanup task started "
        f"(interval={session_storage.cleanup_interval}s, ttl={session_storage.ttl_seconds}s)"
    )

    while True:
        try:
            await asyncio.sleep(session_storage.cleanup_interval)

            # Perform cleanup
            evicted_count = session_storage.cleanup_expired_sessions()
            active_count = session_storage.get_active_session_count()

            if evicted_count > 0 or active_count > 0:
                logger.info(
                    f"[SessionCleanup] Cleanup cycle: evicted={evicted_count}, active={active_count}"
                )

        except asyncio.CancelledError:
            logger.info("[SessionCleanup] Cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"[SessionCleanup] Error during cleanup: {e}")
            # Continue running despite errors
            await asyncio.sleep(session_storage.cleanup_interval)


# ======================== Testing Utilities ========================

def create_test_session_storage(ttl_seconds: int = 10, cleanup_interval: int = 5) -> SessionStorage:
    """
    Create isolated session storage for testing

    Args:
        ttl_seconds: TTL for test sessions
        cleanup_interval: Cleanup interval for tests

    Returns:
        New SessionStorage instance (bypasses singleton)
    """
    # Force create new instance by resetting singleton
    SessionStorage._instance = None

    config = {
        'enabled': True,
        'ttl_seconds': ttl_seconds,
        'cleanup_interval': cleanup_interval
    }

    storage = SessionStorage(config)
    # Reset singleton flag so next creation works normally
    storage._initialized = False
    return storage
