import sqlite3
import logging

class HybridMemory:
    def __init__(self, db_path: str = "data/conversations.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Added 'synced' column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                synced INTEGER DEFAULT 0, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def add_message(self, session_id: str, role: str, content: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, synced) VALUES (?, ?, ?, 0)",
            (session_id, role, content)
        )
        conn.commit()
        conn.close()

    def get_unsynced(self) -> list:
        """Fetch messages that haven't hit Supabase yet."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, session_id, role, content FROM messages WHERE synced = 0")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def mark_as_synced(self, msg_ids: list):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.executemany("UPDATE messages SET synced = 1 WHERE id = ?", [(i,) for i in msg_ids])
        conn.commit()
        conn.close()

memory_manager = HybridMemory()