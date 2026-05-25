# ╔══════════════════════════════════════════════════════════════╗
# ║                       export_routes.py                       ║
# ║  v2.1: выгрузка Excel + маршрут МинЭК               ║
# ╚══════════════════════════════════════════════════════════════╝

from flask import Blueprint, request, redirect, url_for, send_file, jsonify, session
from datetime import datetime, date, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import re
import os

from db import get_db, REPORTS_DIR
from auth_utils import login_required


# ─── НАСТРОЙКИ BLUEPRINT ──────────────────────────────────────────────────

report_bp = Blueprint('report', __name__)


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ───────────────────────────────────────────

def _short_fio(full_name: str) -> str:
    """
    Преобразует полное ФИО в формат «Фамилия И.О.».
    Пример: 'Иванов Иван Иванович' → 'Иванов И.И.'
    Если частей недостаточно — возвращает как есть.
    """
    if not full_name:
        return '—'
    parts = full_name.strip().split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0].upper()}.{parts[2][0].upper()}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0].upper()}."
    return full_name


def _std_border(color='CCCCCC'):
    s = Side(style='thin', color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def _hex_to_argb(hex_color: str) -> str:
    """
    Приводит '#RRGGBB' или 'RRGGBB' в 'FFRRGGBB' для openpyxl PatternFill.
    """
    c = hex_color.lstrip('#').upper()
    if len(c) == 6:
        return 'FF' + c
    if len(c) == 8:
        return c
    return 'FFFFFFFF'


# ─── СТАНДАРТНАЯ ВЫГРУЗКА ───────────────────────────────────────────────

@report_bp.route('/report')
@login_required
def report():
    df = request.args.get('date_from', '')
    dt = request.args.get('date_to', '')
    sf = request.args.get('status', '')

    conn = get_db()
    q = ("SELECT r.*,u.full_name as employee_name,ass.full_name as assigned_name "
         "FROM requests r "
         "LEFT JOIN users u   ON r.created_by=u.id "
         "LEFT JOIN users ass ON r.assigned_to=ass.id "
         "WHERE 1=1")
    p = []
    if df:
        q += ' AND r.request_date>=?'
        p.append(df)
    if dt:
        q += ' AND r.request_date<=?'
        p.append(dt)
    if sf:
        q += ' AND r.status=?'
        p.append(sf)

    rows = conn.execute(q + ' ORDER BY r.request_date', p).fetchall()
    conn.close()

    sm = {
        'draft':    'Черновик',
        'review':   'На проверке',
        'accepted': 'Принято в работу',
        'answered': 'Ответ направлен',
    }

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Отчёт'

    hfill = PatternFill("solid", fgColor="1B5E7B")
    hfont = Font(bold=True, color="FFFFFF", size=10)
    alt   = PatternFill("solid", fgColor="EAF4FB")
    br    = _std_border()

    ws.merge_cells('A1:Q1')
    per = f" за период {df}–{dt}" if (df or dt) else ""
    ws['A1'].value     = f"Обращения на подбор земельных участков{per}"
    ws['A1'].font      = Font(bold=True, size=13, color="1B5E7B")
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.row_dimensions[1].height = 26

    ws.merge_cells('A2:Q2')
    ws['A2'].value     = (
        f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}  "
        f"Всего: {len(rows)}"
    )
    ws['A2'].font      = Font(italic=True, size=9, color="888888")
    ws['A2'].alignment = Alignment(horizontal='center')

    hdrs = [
        '№ обращения', 'Дата', 'Статус', 'Источник', 'Заявитель', 'Название проекта',
        'Контактное лицо', 'Телефон', 'E-mail', 'Инвестиции (млн)',
        'Рабочих мест', 'Площадь (га)', 'Застройка (м²)', 'Право пользования',
        'Районы', 'Ответственный', 'Дата ответа',
    ]
    for ci, h in enumerate(hdrs, 1):
        c = ws.cell(row=3, column=ci, value=h)
        c.fill = hfill
        c.font = hfont
        c.border = br
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[3].height = 38

    for ri, r in enumerate(rows, 4):
        fill = alt if ri % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        vals = [
            r['request_number'] or '—',
            r['request_date'] or '—',
            sm.get(r['status'], r['status']),
            r['source_type'] or '—',
            r['applicant_short_name'] or r['applicant_full_name'] or '—',
            r['project_name'] or '—',
            r['contact_person'] or '—',
            r['contact_phone'] or '—',
            r['contact_email'] or '—',
            r['investment_total'],
            r['jobs_total'],
            r['site_area_ha'],
            r['site_build_area_m2'],
            r['site_right'] or '—',
            r['preferred_districts'] or '—',
            r['assigned_name'] or r['employee_name'] or '—',
            r['answer_date'] or '—',
        ]
        for ci, val in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill = fill
            c.border = br
            c.alignment = Alignment(vertical='center', wrap_text=True)
        ws.row_dimensions[ri].height = 16

    for ci, w in enumerate(
        [16, 12, 20, 16, 28, 30, 20, 15, 24, 12, 10, 10, 12, 16, 24, 20, 12], 1
    ):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.freeze_panes = 'A4'

    fn = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    fp = os.path.join(REPORTS_DIR, fn)
    wb.save(fp)

    return send_file(
        fp, as_attachment=True, download_name=fn,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


# ─── ЕЖЕНЕДЕЛЬНАЯ ВЫГРУЗКА ДЛЯ МИНЭК ──────────────────────────────

@report_bp.route('/report/minek')
@login_required
def report_minek():
    """
    Еженедельная выгрузка для МинЭК.

    Query-параметры:
      date_from, date_to  — диапазон дат (по умолчанию: текущая неделя)
      status              — фильтр по статусу (по умолчанию: все)

    Файл содержит два листа:
      1. ‘Обращения’ — основная таблица
      2. ‘Легенда’    — расшифровка цветов из result_types
    """
    today = date.today()

    # По умолчанию — текущая неделя (пн – вс)
    week_start = today - timedelta(days=today.weekday())          # понедель
    week_end   = week_start + timedelta(days=6)                   # воскресенье

    df = request.args.get('date_from', week_start.isoformat())
    dt = request.args.get('date_to',   week_end.isoformat())
    sf = request.args.get('status', '')

    conn = get_db()

    # Основные данные обращений
    q = """
        SELECT
            r.*,
            u.full_name   AS employee_name,
            ass.full_name AS assigned_name,
            st.name       AS subject_type_name,
            rt.name       AS result_type_name,
            rt.color_hex  AS result_color
        FROM requests r
        LEFT JOIN users         u   ON r.created_by      = u.id
        LEFT JOIN users         ass ON r.assigned_to     = ass.id
        LEFT JOIN subject_types st  ON r.subject_type_id = st.id
        LEFT JOIN result_types  rt  ON r.result_type_id  = rt.id
        WHERE r.request_date >= ? AND r.request_date <= ?
    """
    p = [df, dt]
    if sf:
        q += ' AND r.status = ?'
        p.append(sf)
    q += ' ORDER BY r.request_date, r.id'

    rows = conn.execute(q, p).fetchall()

    # Справочник итогов для легенды
    result_types = conn.execute(
        'SELECT id, name, color_hex FROM result_types ORDER BY id'
    ).fetchall()

    conn.close()

    sm = {
        'draft':    'Черновик',
        'review':   'На проверке',
        'accepted': 'В работе',
        'answered': 'Отвечено',
    }

    # ══════════════════════════════════════════════════════════════
    # ЛИСТ 1 — ОБРАЩЕНИЯ
    # ══════════════════════════════════════════════════════════════

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Обращения'

    HEADER_COLOR = '1B5E7B'
    hfill = PatternFill('solid', fgColor=HEADER_COLOR)
    hfont = Font(bold=True, color='FFFFFF', size=10)
    alt   = PatternFill('solid', fgColor='EAF4FB')
    br    = _std_border()

    # ── Заголовок ────────────────────────────────────────────────────────
    NCOLS = 21
    ws.merge_cells(f'A1:{get_column_letter(NCOLS)}1')
    ws['A1'].value = (
        f"Еженедельный доклад МинЭК: обращения за период "
        f"{_fmt_date(df)} – {_fmt_date(dt)}"
    )
    ws['A1'].font      = Font(bold=True, size=13, color=HEADER_COLOR)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    ws.merge_cells(f'A2:{get_column_letter(NCOLS)}2')
    ws['A2'].value = (
        f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}   "
        f"Обращений в выборке: {len(rows)}"
    )
    ws['A2'].font      = Font(italic=True, size=9, color='888888')
    ws['A2'].alignment = Alignment(horizontal='center')

    # ── Шапка (3-я строка) ──────────────────────────────────────────────
    HEADERS = [
        '№',                      # A
        'Дата обращения',         # B
        'Статус',                  # C
        'Источник',                # D
        'Предмет обращения',   # E
        'Заявитель',              # F
        'Название проекта',    # G
        'Контактное лицо',    # H
        'Телефон',                # I
        'Инвестиции (млн)',      # J
        'Рабочих мест',         # K
        'Площадь (га)',           # L
        'Застройка (м²)',          # M
        'Право пользования',   # N
        'Районы',                  # O
        'Ответственный',         # P  (в формате ФИО)
        'Дата ответа',            # Q
        'Дата обр. связи',      # R  (feedback_date)
        'Итоги работы',          # S  (result_type_name)
        'Доп. сведения',          # T
        'Номер обращения',     # U
    ]

    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(row=3, column=ci, value=h)
        c.fill = hfill
        c.font = hfont
        c.border = br
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[3].height = 40

    # ── Данные ─────────────────────────────────────────────────────────
    for ri, r in enumerate(rows, 4):
        base_fill = alt if ri % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')

        # Цвет строки по итогу (если есть)
        row_color = r['result_color'] if r['result_color'] else None
        if row_color:
            argb  = _hex_to_argb(row_color)
            rfill = PatternFill('solid', fgColor=argb)
        else:
            rfill = base_fill

        vals = [
            ri - 3,                                                         # A № п/п
            r['request_date'] or '—',                                       # B
            sm.get(r['status'], r['status']),                               # C
            r['source_type'] or '—',                                        # D
            r['subject_type_name'] or '—',                                  # E
            r['applicant_short_name'] or r['applicant_full_name'] or '—',   # F
            r['project_name'] or '—',                                       # G
            r['contact_person'] or '—',                                     # H
            r['contact_phone'] or '—',                                      # I
            r['investment_total'],                                          # J
            r['jobs_total'],                                                # K
            r['site_area_ha'],                                              # L
            r['site_build_area_m2'],                                        # M
            r['site_right'] or '—',                                         # N
            r['preferred_districts'] or '—',                               # O
            _short_fio(r['assigned_name'] or r['employee_name']),           # P
            r['answer_date'] or '—',                                        # Q
            r['feedback_date'] or '—',                                      # R
            r['result_type_name'] or '—',                                   # S
            r['additional_info'] or '—',                                    # T
            r['request_number'] or '—',                                     # U
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill   = rfill
            c.border = br
            c.alignment = Alignment(vertical='center', wrap_text=(ci not in (1, 9, 17, 18)))
        ws.row_dimensions[ri].height = 18

    # ── Ширина колонок ──────────────────────────────────────────────────
    col_widths = [
        5,   # A №
        12,  # B дата
        14,  # C статус
        16,  # D источник
        22,  # E предмет
        28,  # F заявитель
        30,  # G проект
        20,  # H контакт
        15,  # I тел
        12,  # J инвестиции
        10,  # K рабочих мест
        10,  # L площадь
        12,  # M застройка
        16,  # N право
        24,  # O районы
        16,  # P ответственный
        12,  # Q дата ответа
        12,  # R обратная связь
        22,  # S итоги
        30,  # T доп. сведения
        16,  # U номер
    ]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'B4'   # заморозка: строки 1-3 + колонка A

    # ══════════════════════════════════════════════════════════════
    # ЛИСТ 2 — ЛЕГЕНДА ЦВЕТОВ
    # ══════════════════════════════════════════════════════════════

    wl = wb.create_sheet(title='Легенда')

    wl.merge_cells('A1:C1')
    wl['A1'].value     = 'Легенда цветов (итоги работы по обращению)'
    wl['A1'].font      = Font(bold=True, size=12, color=HEADER_COLOR)
    wl['A1'].alignment = Alignment(horizontal='center')
    wl.row_dimensions[1].height = 22

    # Шапка легенды
    for ci, h in enumerate(['Цвет', 'Итог', 'Описание'], 1):
        c = wl.cell(row=2, column=ci, value=h)
        c.fill = PatternFill('solid', fgColor=HEADER_COLOR)
        c.font = Font(bold=True, color='FFFFFF', size=10)
        c.border = _std_border()
        c.alignment = Alignment(horizontal='center', vertical='center')
    wl.row_dimensions[2].height = 20

    if result_types:
        for li, rt in enumerate(result_types, 3):
            color_hex = rt['color_hex'] or 'FFFFFF'
            argb      = _hex_to_argb(color_hex)

            # Ячейка с цветом
            ca = wl.cell(row=li, column=1, value='')
            ca.fill   = PatternFill('solid', fgColor=argb)
            ca.border = _std_border()

            # Название итога
            cb = wl.cell(row=li, column=2, value=rt['name'])
            cb.fill   = PatternFill('solid', fgColor=argb)
            cb.font   = Font(bold=True, size=10)
            cb.border = _std_border()
            cb.alignment = Alignment(vertical='center')

            # Опционально: HEX-код цвета
            cc = wl.cell(row=li, column=3, value=color_hex)
            cc.font   = Font(italic=True, size=9, color='888888')
            cc.border = _std_border()
            cc.alignment = Alignment(vertical='center')

            wl.row_dimensions[li].height = 18
    else:
        wl.cell(row=3, column=1,
                value='Справочник итогов пуст. Добавьте значения в разделе «Справочники».')

    wl.column_dimensions['A'].width = 8
    wl.column_dimensions['B'].width = 30
    wl.column_dimensions['C'].width = 12

    # ── Сохранение файла ──────────────────────────────────────────────────
    fn = f"minek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    fp = os.path.join(REPORTS_DIR, fn)
    wb.save(fp)

    return send_file(
        fp, as_attachment=True,
        download_name=fn,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def _fmt_date(iso: str) -> str:
    """'Форматирует ISO-дату YYYY-MM-DD → DD.MM.YYYY (fallback: как есть)."""
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return iso or '—'


# ─── AUTOSAVE / WAL CHECKPOINT ───────────────────────────────────────────────────────

@report_bp.route('/autosave', methods=['POST'])
@login_required
def autosave():
    try:
        conn = get_db()
        conn.execute('PRAGMA wal_checkpoint(PASSIVE)')
        conn.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
