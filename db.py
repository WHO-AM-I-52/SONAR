# ╔══════════════════════════════════════════════════════════════╗
# ║                         db.py                               ║
# ║  Подключение к базе данных и пути к папкам приложения       ║
# ╚══════════════════════════════════════════════════════════════╝

import sqlite3
import os

# ─── ПУТИ ──────────────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'db', 'database.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
ALLOWED_EXT = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'xlsx', 'zip'}

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# ─── МИГРАЦИЯ ────────────────────────────────────────────────────────────────────

def _migrate(conn):
    """Автоматическое добавление новых таблиц если они отсутствуют."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS online_presence (
            user_id  INTEGER PRIMARY KEY,
            last_seen TEXT NOT NULL
        )
    """)
    conn.commit()


# ─── ПОДКЛЮЧЕНИЕ К БД ──────────────────────────────────────────────────────────────

def get_db():
    """
    Открывает соединение с базой данных SQLite.
    - row_factory = sqlite3.Row позволяет обращаться к полям по имени
    - WAL-режим улучшает производительность при параллельных запросах
    - _migrate() автоматически добавляет новые таблицы если они отсутствуют
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn
