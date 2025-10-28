"""
SQLite persistence for Jarvis: reminders, notes, preferences.
"""
from __future__ import annotations

import sqlite3
import time
from typing import List, Tuple, Optional

from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            time_utc INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            done INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def add_reminder(text: str, when_epoch_utc: int) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute(
        "INSERT INTO reminders(text, time_utc, created_at, done) VALUES(?,?,?,0)",
        (text, when_epoch_utc, now),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_due_reminders(now_epoch: Optional[int] = None) -> List[Tuple[int, str, int]]:
    now_epoch = now_epoch or int(time.time())
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, text, time_utc FROM reminders WHERE done=0 AND time_utc <= ? ORDER BY time_utc ASC",
        (now_epoch,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_reminder_done(reminder_id: int) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET done=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def add_note(content: str) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("INSERT INTO notes(content, created_at) VALUES(?,?)", (content, now))
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    return nid
