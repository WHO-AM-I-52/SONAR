# ╔════════════════════════════════════════════════════════════════╗
# ║                         db.py                               ║
# ║  Подключение к базе данных и пути к папкам приложения       ║
# ╚════════════════════════════════════════════════════════════════╝

import sqlite3
import os

# ─── ПУТИ ──────────────────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'db', 'database.db')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
ALLOWED_EXT = {'pdf', 'ppt', 'pptx', 'doc', 'docx', 'xlsx', 'zip'}

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)


# ─── МИГРАЦИЯ ───────────────────────────────────────────────────────────────────

def _has_column(conn, table: str, column: str) -> bool:
    """Труе если колонка уже есть в таблице."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r['name'] == column for r in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return row is not None


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

    # ─ Справочник «Предмет обращения»
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

    # ─ Справочник «Итоги работы по обращению»
    result_types_exists_before = _table_exists(conn, 'result_types')
    conn.execute("""
        CREATE TABLE IF NOT EXISTS result_types (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL UNIQUE,
            color_hex TEXT NOT NULL DEFAULT 'FFFFFF'
        )
    """)

    default_results = [
        ('Вопрос решен',                           'FF0000'),
        ('Проект взят на сопровождение',          '92D050'),
        ('Обращение частично отработано',         'A6A6A6'),
        ('На исполнении',                         'FFFFFF'),
        ('Взято на сопровождение',                 '92D050'),
        ('В работе',                               'FFFFFF'),
        ('Отвечено',                              'FF0000'),
        ('Подобранные зу направлены инвестору',   'FF0000'),
        ('Подобранные помещения направлены инвестору', 'FF0000'),
        ('Подобранные зу и помещения направлены инвестору', 'FF0000'),
        ('Проведено рабочее совещание с инвестором',  '92D050'),
        ('Проведено совещание (с участием ОИВ/ОМС)',  '92D050'),
        ('Отказ',                                   'A6A6A6'),
    ]

    result_cnt = conn.execute("SELECT COUNT(*) FROM result_types").fetchone()[0]
    if (not result_types_exists_before) or result_cnt == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO result_types (name, color_hex) VALUES (?, ?)",
            default_results
        )

    # ─ Новые поля в таблице requests
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

    # ─ Bugfix #3: колонка incoming_number (номер входящего в Directum/СЭДО)
    if not _has_column(conn, 'requests', 'incoming_number'):
        conn.execute(
            "ALTER TABLE requests ADD COLUMN incoming_number TEXT"
        )

    # ════════════════════════════════════════════════════════════════
    # Индексы — fix #6
    # ════════════════════════════════════════════════════════════════
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_status ON requests(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_created_by ON requests(created_by)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_assigned ON requests(assigned_to)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_req_date ON requests(request_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)"
    )

    # ════════════════════════════════════════════════════════════════
    # fix: таблица счётчиков нумерации обращений по годам
    # Решает баг с дублированием номеров при удалении записей.
    # Каждый год хранит свой независимый счётчик.
    # Миграция: при первом запуске инициализирует счётчик текущего года
    # на основе MAX существующих номеров вида «ЗУ-YYYY-NNNN».
    # ════════════════════════════════════════════════════════════════
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_counters (
            year     INTEGER PRIMARY KEY,
            last_seq INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Инициализация счётчика из существующих данных (идемпотентно)
    _init_counters_from_existing(conn)

    conn.commit()


def _init_counters_from_existing(conn):
    """
    При первой миграции: читает существующие номера вида «ЗУ-YYYY-NNNN»
    и восстанавливает счётчики по годам, чтобы новые номера не конфликтовали.
    Повторный вызов безопасен: INSERT OR IGNORE не перезапишет уже заполненные строки.
    """
    rows = conn.execute(
        "SELECT request_number FROM requests WHERE request_number IS NOT NULL"
    ).fetchall()
    year_max = {}
    for row in rows:
        num = row[0] or ''
        # Формат: ЗУ-YYYY-NNNN
        parts = num.split('-')
        if len(parts) == 3:
            try:
                year = int(parts[1])
                seq  = int(parts[2])
                if year_max.get(year, 0) < seq:
                    year_max[year] = seq
            except ValueError:
                pass
    for year, max_seq in year_max.items():
        # INSERT OR IGNORE: не трогает строку, если год уже есть в таблице
        conn.execute(
            "INSERT OR IGNORE INTO request_counters (year, last_seq) VALUES (?, ?)",
            (year, max_seq)
        )


def next_request_number(conn, year: int) -> str:
    """
    Атомарно увеличивает счётчик для указанного года и возвращает
    готовый номер вида «ЗУ-YYYY-NNNN».

    Использует INSERT OR REPLACE + SELECT для атомарной операции в SQLite.
    Вызывать внутри уже открытой транзакции (conn.commit() делает вызывающий код).
    """
    # Создаём строку года если её нет (первый номер в году)
    conn.execute(
        "INSERT OR IGNORE INTO request_counters (year, last_seq) VALUES (?, 0)",
        (year,)
    )
    conn.execute(
        "UPDATE request_counters SET last_seq = last_seq + 1 WHERE year = ?",
        (year,)
    )
    seq = conn.execute(
        "SELECT last_seq FROM request_counters WHERE year = ?",
        (year,)
    ).fetchone()[0]
    return f"ЗУ-{year}-{seq:04d}"


# ─── ПОДКЛЮЧЕНИЕ К БД ────────────────────────────────────────────────────────────────

def get_db():
    """
    Открывает соединение с базой данных SQLite.
    - row_factory = sqlite3.Row — обращение к полям по имени
    - WAL-режим — производительность при параллельных запросах
    - _migrate() — автоматически добавляет новые таблицы/колонки/индексы
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn
