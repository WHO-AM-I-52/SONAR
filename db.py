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

    # ─ Колонка action в request_history
    if not _has_column(conn, 'request_history', 'action'):
        conn.execute(
            "ALTER TABLE request_history ADD COLUMN action TEXT DEFAULT 'edit'"
        )

    # ════════════════════════════════════════════════════════════════
    # МинЭК: справочники и новые поля
    # ════════════════════════════════════════════════════════════════

    # ─ Справочник «Предмет обращения» ─────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subject_types (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cnt = conn.execute("SELECT COUNT(*) FROM subject_types").fetchone()[0]
    if cnt == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO subject_types (name) VALUES (?)",
            [
                ('подбор зу',),
                ('подбор мер поддержки',),
                ('подбор индустриального парка',),
                ('подбор зу, помещений',),
                ('консультация',),
            ]
        )

    # ─ Справочник «Итоги работы по обращению» ─────────────────────
    # color_hex — RRGGBB без #, используется в openpyxl PatternFill
    conn.execute("""
        CREATE TABLE IF NOT EXISTS result_types (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE,
            color_hex TEXT NOT NULL DEFAULT 'FFFFFF'
        )
    """)

    # Полный список из файла МинЭК + стандартные значения.
    # INSERT OR IGNORE — не трогает уже существующие записи.
    default_results = [
        # ── из легенды файла МинЭК ──────────────────────────────
        ('Вопрос решен',                              'C6EFCE'),  # зелёный
        ('Проект взят на сопровождение',              'FFEB9C'),  # жёлтый
        ('Обращение частично отработано',             'FFCC99'),  # оранжевый
        ('На исполнении',                             'BDD7EE'),  # голубой
        # ── дополнительные из данных файла ─────────────────────
        ('Взято на сопровождение',                    'FFEB9C'),  # жёлтый (синоним)
        ('В работе',                                  'BDD7EE'),  # голубой (синоним)
        # ── специальные ─────────────────────────────────────────
        ('Подобранные зу направлены инвестору',       'C6EFCE'),  # зелёный
        ('Подобранные помещения направлены инвестору','C6EFCE'),  # зелёный
        ('Подобранные зу и помещения направлены инвестору', 'C6EFCE'),  # зелёный
        ('Проведено рабочее совещание с инвестором',  'FFEB9C'),  # жёлтый
        ('Проведено совещание (с участием ОИВ/ОМС)',  'FFEB9C'),  # жёлтый
        ('Отказ',                                     'FFC7CE'),  # красный
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO result_types (name, color_hex) VALUES (?, ?)",
        default_results
    )

    # ─ Новые поля в таблице requests ──────────────────────────────
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


# ─── ПОДКЛЮЧЕНИЕ К БД ───────────────────────────────────────────────────────

def get_db():
    """
    Открывает соединение с базой данных SQLite.
    - row_factory = sqlite3.Row — обращение к полям по имени
    - WAL-режим — производительность при параллельных запросах
    - _migrate() — автоматически добавляет новые таблицы/колонки
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn
