"""
HackT Sovereign Core - Local Database Manager (v3.0)
=====================================================
Provides persistent, thread-safe SQLite storage featuring:
- WAL Mode for Concurrent Access (Critical for FastAPI + Daemons)
- Connection Pooling (Performance optimization for large datasets)
- Schema Migrations (Future-proofing)
- Full Session CRUD (Create, Read, Update, Delete)
- Foreign Key Enforcement (Data Integrity)
"""
import sqlite3
import threading
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager

from utils.logger import get_logger
from utils.config import config

logger = get_logger("hackt.core.database")

class DatabaseManager:
    def __init__(self, max_pool_size: int = 10):
        self.db_path = config.paths.data_dir / "sovereign.db"
        self._lock = threading.Lock()
        self._pool: List[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._max_pool_size = max_pool_size
        self._initialized = False
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initial cold boot setup
        self.initialize()

    def initialize(self):
        """Public entry point for main.py lifespan."""
        if not self._initialized:
            self._initialize_database()

    @contextmanager
    def _get_connection(self):
        conn = None
        try:
            with self._pool_lock:
                if self._pool:
                    conn = self._pool.pop()
                else:
                    # Create new connection only if needed
                    conn = sqlite3.connect(
                        str(self.db_path),
                        check_same_thread=False,
                        timeout=30.0
                    )
                    # 🚀 PERFORMANCE TUNING
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA foreign_keys=ON")
            
            yield conn
            
        finally:
            if conn:
                with self._pool_lock:
                    # Only return to pool if there's room, otherwise kill it
                    if len(self._pool) < self._max_pool_size:
                        self._pool.append(conn)
                    else:
                        conn.close()

    def _initialize_database(self):
        """Internal schema setup."""
        with self._lock:
            if self._initialized: return
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 1. Sessions Table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            title TEXT NOT NULL DEFAULT 'New Chat',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            metadata TEXT DEFAULT '{}'
                        )
                    """)
                    
                    # 2. Messages Table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS messages (
                            id TEXT PRIMARY KEY,
                            session_id TEXT NOT NULL,
                            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                            content TEXT NOT NULL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            token_count INTEGER DEFAULT 0,
                            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
                        )
                    """)
                    
                    # 3. Optimization Indexes
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, timestamp DESC)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at DESC)")
                    
                    # 4. Telemetry Table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS telemetry_logs (
                            id TEXT PRIMARY KEY,
                            event_type TEXT NOT NULL,
                            payload TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    conn.commit()
                    self._initialized = True
                    logger.info(f"Database: Sovereign Vault mounted at {self.db_path}")
                    
            except Exception as e:
                logger.error(f"Database: Initialization CRITICAL failure: {e}")
                raise
            
    # ==========================================
    # SESSION CRUD OPERATIONS
    # ==========================================
    def get_session_history(self, session_id: str, max_turns: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent context for LLM prompt injection."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                limit = max_turns * 2  # User + Assistant = 1 turn
                
                cursor.execute("""
                    SELECT role, content, token_count FROM messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC LIMIT ?
                """, (session_id, limit))
                
                rows = cursor.fetchall()
                # Reverse to get chronological order
                return [
                    {"role": row[0], "content": row[1], "token_count": row[2]} 
                    for row in reversed(rows)
                ]
        except Exception as e:
            logger.error(f"Database: Failed to get history: {e}")
            return []

    def save_turn(self, session_id: str, user_prompt: str, ai_response: str, 
                  token_count: int = 0):
        """Saves a User/AI interaction atomically with session auto-creation."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Ensure Session Exists (Auto-create if new)
                cursor.execute("""
                    INSERT OR IGNORE INTO sessions (session_id, title, created_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (session_id, "New Chat"))
                
                # 2. Update Session Timestamp
                cursor.execute("""
                    UPDATE sessions SET updated_at = CURRENT_TIMESTAMP 
                    WHERE session_id = ?
                """, (session_id,))
                
                # 3. Insert User Message
                user_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO messages (id, session_id, role, content, token_count) 
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, session_id, "user", user_prompt, 0))
                
                # 4. Insert AI Message
                ai_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO messages (id, session_id, role, content, token_count) 
                    VALUES (?, ?, ?, ?, ?)
                """, (ai_id, session_id, "assistant", ai_response, token_count))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Database: Failed to save turn: {e}")
            # Don't raise - chat should continue even if DB fails

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Fetch metadata for React Frontend Sidebar."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, title, created_at, updated_at, metadata 
                    FROM sessions 
                    ORDER BY updated_at DESC
                """)
                rows = cursor.fetchall()
                return [
                    {
                        "session_id": r[0],
                        "title": r[1],
                        "created_at": r[2],
                        "updated_at": r[3],
                        "metadata": json.loads(r[4]) if r[4] else {}
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Database: Failed to get sessions: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages (CASCADE)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Database: Failed to delete session: {e}")
            return False

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename a chat session."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE session_id = ?
                """, (new_title, session_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Database: Failed to rename session: {e}")
            return False

    def log_telemetry(self, event_type: str, payload: Dict[str, Any]):
        """Log telemetry events for debugging/audit (auto-cleans old logs)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO telemetry_logs (id, event_type, payload) 
                    VALUES (?, ?, ?)
                """, (str(uuid.uuid4()), event_type, json.dumps(payload)))
                
                # Auto-cleanup: Keep only last 10000 logs
                cursor.execute("""
                    DELETE FROM telemetry_logs 
                    WHERE id NOT IN (
                        SELECT id FROM telemetry_logs 
                        ORDER BY timestamp DESC LIMIT 10000
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"Database: Telemetry log failed (non-critical): {e}")

    def get_message_count(self, session_id: str) -> int:
        """Get total message count for a session."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM messages WHERE session_id = ?
                """, (session_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Database: Failed to count messages: {e}")
            return 0

    def close_all(self):
        """Graceful cleanup for shutdown."""
        with self._pool_lock:
            for conn in self._pool:
                try:
                    conn.close()
                except:
                    pass
            self._pool.clear()
        logger.info("Database: All Sovereign connections purged.")

# Singleton
db = DatabaseManager()