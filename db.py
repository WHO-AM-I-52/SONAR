# ╔══════════════════════════════════════════════════════════════╗
# ║                         db.py                               ║
# ║  Подключение к базе данных и пути к папкам приложения       ║
# ╚══════════════════════════════════════════════════════════════╝

import sqlite3
import os

# ─── ПУТИ ────────────────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'db', 'database.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
ALLOWED_EXT = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'xlsx', 'zip'}

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# ─── МИГРАЦИЯ ───────────────────────────────────────────────────────────────

def _has_column(conn, table: str, column: str) -> bool:
    """True если колонка уже есть в таблице."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r['name'] == column for r in rows)


def _migrate(conn):
    """
    Автоматическое добавление новых таблиц и колонок если они отсутствуют.
    ВАЖНО: все изменения должны быть идемпотентны — при повторном запуске
    на уже обновлённой БД ничего не должно ломаться.
    """

    # ─ Таблица присутствия онлайн
    conn.execute("""
        CREATE TABLE IF NOT EXISTS online_presence (
            user_id   INTEGER PRIMARY KEY,
            last_seen TEXT NOT NULL
        )
    """)

    # ─ Колонка action в request_history (добавляется один раз на старые БД)
    if not _has_column(conn, 'request_history', 'action'):
        conn.execute(
            "ALTER TABLE request_history ADD COLUMN action TEXT DEFAULT 'edit'"
        )

    # ════════════════════════════════════════════════════════════════
    # МинЭК: справочники и новые поля (добавлено для выгрузки МинЭК)
    # ════════════════════════════════════════════════════════════════

    # ─ Справочник «Предмет обращения» ─────────────────────────────
    # Содержит типы предметов обращений (подбор зу, подбор мер поддержки и т.п.)
    # Расширяется через интерфейс администратора без правки кода.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subject_types (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    # Начальное наполнение справочника — только если он пустой
    cnt = conn.execute("SELECT COUNT(*) FROM subject_types").fetchone()[0]
    if cnt == 0:
        default_subjects = [
            ('подбор зу',),
            ('подбор мер поддержки',),
            ('подбор индустриального парка',),
            ('консультация',),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO subject_types (name) VALUES (?)",
            default_subjects
        )

    # ─ Справочник «Итоги работы по обращению» ─────────────────────
    # Содержит финальные статусы с цветом заливки для выгрузки МинЭК.
    # color_hex — цвет в формате RRGGBB (без #), используется в openpyxl PatternFill.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS result_types (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE,
            color_hex TEXT NOT NULL DEFAULT 'FFFFFF'
        )
    """)

    # Начальное наполнение — только если справочник пустой
    cnt = conn.execute("SELECT COUNT(*) FROM result_types").fetchone()[0]
    if cnt == 0:
        default_results = [
            ('Вопрос решен',                  'C6EFCE'),  # зелёный
            ('Взято на сопровождение',        'FFEB9C'),  # жёлтый
            ('Обращение частично отработано', 'FFCC99'),  # оранжевый
            ('На исполнении',                 'BDD7EE'),  # голубой
            ('Отказ',                         'FFC7CE'),  # красный
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO result_types (name, color_hex) VALUES (?, ?)",
            default_results
        )

    # ─ Новые поля в таблице requests ──────────────────────────────
    # subject_type_id  — предмет обращения (FK → subject_types)
    # feedback_date    — дата получения обратной связи (Сведения об ответе)
    # result_type_id   — итоги работы по обращению (FK → result_types)
    #
    # Используем _has_column чтобы ALTER TABLE не падал на уже обновлённых БД.

    if not _has_column(conn, 'requests', 'subject_type_id'):
        conn.execute(
            "ALTER TABLE requests ADD COLUMN subject_type_id INTEGER REFERENCES subject_types(id)"
        )

    if not _has_column(conn, 'requests', 'feedback_date'):
        conn.execute(
            "ALTER TABLE requests ADD COLUMN feedback_date TEXT"
        )

    if not _has_column(conn, 'requests', 'result_type_id'):
        conn.execute(
            "ALTER TABLE requests ADD COLUMN result_type_id INTEGER REFERENCES result_types(id)"
        )

    conn.commit()


# ─── ПОДКЛЮЧЕНИЕ К БД ───────────────────────────────────────────────────────────

def get_db():
    """
    Открывает соединение с базой данных SQLite.
    - row_factory = sqlite3.Row позволяет обращаться к полям по имени
    - WAL-режим улучшает производительность при параллельных запросах
    - _migrate() автоматически добавляет новые таблицы/колонки если они отсутствуют
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn
