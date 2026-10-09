"""
SQLite data layer.

Security note: SQL is only used for structural data (ids, timestamps,
foreign keys). Every sensitive field (passwords, usernames, notes, TOTP
secrets, DEK wrapping) is encrypted at the application layer with AES-256-GCM
*before* it reaches SQLite, so the raw .db file on disk is unreadable without
the correct master password or recovery key. All queries are parameterized
to prevent SQL injection.
"""

import sqlite3
import datetime
from contextlib import contextmanager

from app.paths import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,

    password_salt BLOB NOT NULL,
    password_time_cost INTEGER NOT NULL,
    password_memory_cost INTEGER NOT NULL,
    password_parallelism INTEGER NOT NULL,
    wrapped_dek_password BLOB NOT NULL,

    recovery_salt BLOB NOT NULL,
    recovery_time_cost INTEGER NOT NULL,
    recovery_memory_cost INTEGER NOT NULL,
    recovery_parallelism INTEGER NOT NULL,
    wrapped_dek_recovery BLOB NOT NULL,

    totp_enabled INTEGER NOT NULL DEFAULT 0,
    totp_secret_encrypted BLOB,

    auto_lock_minutes INTEGER NOT NULL DEFAULT 5,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,

    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    encrypted_blob BLOB NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vault_items_user ON vault_items(user_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


# ---------- users ----------

def create_user(username: str, pw_salt, pw_params, wrapped_dek_password,
                 rec_salt, rec_params, wrapped_dek_recovery) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO users (
                username,
                password_salt, password_time_cost, password_memory_cost, password_parallelism,
                wrapped_dek_password,
                recovery_salt, recovery_time_cost, recovery_memory_cost, recovery_parallelism,
                wrapped_dek_recovery,
                created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                username,
                pw_salt, pw_params.time_cost, pw_params.memory_cost, pw_params.parallelism,
                wrapped_dek_password,
                rec_salt, rec_params.time_cost, rec_params.memory_cost, rec_params.parallelism,
                wrapped_dek_recovery,
                now_iso(),
            ),
        )
        return cur.lastrowid


def get_user_by_username(username: str):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def list_usernames():
    with get_conn() as conn:
        cur = conn.execute("SELECT username FROM users ORDER BY username")
        return [r[0] for r in cur.fetchall()]


def update_wrapped_dek_password(user_id: int, pw_salt, pw_params, wrapped_dek_password):
    with get_conn() as conn:
        conn.execute(
            """UPDATE users SET
                password_salt=?, password_time_cost=?, password_memory_cost=?, password_parallelism=?,
                wrapped_dek_password=?
               WHERE id=?""",
            (pw_salt, pw_params.time_cost, pw_params.memory_cost, pw_params.parallelism,
             wrapped_dek_password, user_id),
        )


def set_totp(user_id: int, enabled: bool, secret_encrypted):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET totp_enabled=?, totp_secret_encrypted=? WHERE id=?",
            (1 if enabled else 0, secret_encrypted, user_id),
        )


def record_failed_attempt(user_id: int, failed_attempts: int, locked_until: str | None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
            (failed_attempts, locked_until, user_id),
        )


def reset_failed_attempts(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?",
            (user_id,),
        )


def set_auto_lock_minutes(user_id: int, minutes: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET auto_lock_minutes=? WHERE id=?", (minutes, user_id))


# ---------- vault items ----------

def add_vault_item(user_id: int, encrypted_blob: bytes) -> int:
    ts = now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO vault_items (user_id, encrypted_blob, created_at, updated_at) VALUES (?,?,?,?)",
            (user_id, encrypted_blob, ts, ts),
        )
        return cur.lastrowid


def update_vault_item(item_id: int, encrypted_blob: bytes):
    with get_conn() as conn:
        conn.execute(
            "UPDATE vault_items SET encrypted_blob=?, updated_at=? WHERE id=?",
            (encrypted_blob, now_iso(), item_id),
        )


def delete_vault_item(item_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM vault_items WHERE id=?", (item_id,))


def list_vault_items(user_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, encrypted_blob, created_at, updated_at FROM vault_items WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        )
        return cur.fetchall()
