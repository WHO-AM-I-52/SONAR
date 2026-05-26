# ╔══════════════════════════════════════════════════════════════╗
# ║                       export_routes.py                       ║
# ║  v2.4: логирование выгрузок в журнале действий               ║
# ╚══════════════════════════════════════════════════════════════╝

from flask import Blueprint, request, send_file, jsonify, session
from datetime import datetime, date, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os

from db import get_db, REPORTS_DIR
from auth_utils import login_required
from activity_log import log_action

report_bp = Blueprint('report', __name__)


# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────────────────────────────

def _short_fio(full_name: str) -> str:
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
    c = hex_color.lstrip('#').upper()
    if len(c) == 6:
        return 'FF' + c
    if len(c) == 8:
        return c
    return 'FFFFFFFF'


def _fmt_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%d.%m.%Y')
    except Exception:
        return iso or '—'


def _mln_to_mld(val) -> str:
    """Млн руб. → млрд руб. (делим на 1000)."""
    if val is None or val == '':
        return '—'
    try:
        mld = float(str(val).replace(',', '.')) / 1000
        return f"{mld:.3f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(val)


def _contact_cell(person: str, phone: str, email: str) -> str:
    parts = []
    if person and person.strip():
        parts.append(f"Ф.И.О. {person.strip()}")
    if phone and phone.strip():
        parts.append(f"Тел: {phone.strip()}")
    if email and email.strip():
        parts.append(email.strip())
    return '\n'.join(parts) if parts else '—'


# ─── СТАНДАРТНАЯ ВЫГРУЗКА ─────────────────────────────────────────────────────

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
        q += ' AND r.request_date>=?'; p.append(df)
    if dt:
        q += ' AND r.request_date<=?'; p.append(dt)
    if sf:
        q += ' AND r.status=?'; p.append(sf)

    rows = conn.execute(q + ' ORDER BY r.request_date', p).fetchall()

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
    ws['A2'].value = (
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
        c.fill = hfill; c.font = hfont; c.border = br
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
            c.fill = fill; c.border = br
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

    # ── Журнал действий ──────────────────────────────────────────────────────
    log_parts = []
    if df or dt:
        log_parts.append(f"период: {df or '...'} – {dt or '...'}")
    if sf:
        log_parts.append(f"статус: {sm.get(sf, sf)}")
    log_parts.append(f"всего {len(rows)} обращ.")
    try:
        log_action(conn, session['user_id'], 'export_report',
                   detail='; '.join(log_parts))
        conn.commit()
    except Exception:
        pass
    conn.close()

    return send_file(fp, as_attachment=True, download_name=fn,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ─── ЕЖЕНЕДЕЛЬНАЯ ВЫГРУЗКА ДЛЯ МИНЭК ─────────────────────────────────────────

@report_bp.route('/report/minek')
@login_required
def report_minek():
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    df = request.args.get('date_from', week_start.isoformat())
    dt = request.args.get('date_to',   week_end.isoformat())
    sf = request.args.get('status', '')

    conn = get_db()

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
        q += ' AND r.status = ?'; p.append(sf)
    q += ' ORDER BY r.request_date, r.id'

    rows = conn.execute(q, p).fetchall()
    result_types = conn.execute(
        'SELECT id, name, color_hex FROM result_types ORDER BY id'
    ).fetchall()

    HEADER_COLOR = '1B5E7B'
    hfill = PatternFill('solid', fgColor=HEADER_COLOR)
    hfont = Font(bold=True, color='FFFFFF', size=10)
    alt   = PatternFill('solid', fgColor='EAF4FB')
    br    = _std_border()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Заявки'

    NCOLS = 12

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

    HEADERS = [
        '',
        'Дата обращения',
        'Наименование компании',
        'Наименование проекта',
        'Объем инвестиций,\nмлрд рублей',
        'Рабочие места',
        'Предмет обращения',
        'Дата направления презентации',
        'Дата получения обратной связи',
        'Итоги работы по обращению',
        'Менеджер',
        'Телефон, контактное лицо',
    ]

    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(row=3, column=ci, value=h)
        c.fill = hfill; c.font = hfont; c.border = br
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[3].height = 40

    for ri, r in enumerate(rows, 4):
        base_fill = alt if ri % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')
        row_color = r['result_color'] if r['result_color'] else None
        rfill = PatternFill('solid', fgColor=_hex_to_argb(row_color)) if row_color else base_fill

        result_val = r['additional_info'] or r['result_type_name'] or '—'

        vals = [
            ri - 3,
            r['request_date'] or '—',
            r['applicant_short_name'] or r['applicant_full_name'] or '—',
            r['project_name'] or '—',
            _mln_to_mld(r['investment_total']),
            r['jobs_total'] or '—',
            r['subject_type_name'] or '—',
            r['answer_date'] or '—',
            r['feedback_date'] or '—',
            result_val,
            _short_fio(r['assigned_name'] or r['employee_name']),
            _contact_cell(
                r['contact_person'],
                r['contact_phone'],
                r['contact_email'],
            ),
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.fill   = rfill
            c.border = br
            c.alignment = Alignment(
                vertical='center',
                wrap_text=True,
                horizontal='center' if ci == 1 else 'left',
            )
        ws.row_dimensions[ri].height = 30

    col_widths = [5, 13, 28, 35, 12, 12, 22, 16, 16, 30, 16, 32]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'B4'

    wl = wb.create_sheet(title='Справочник')

    wl.merge_cells('A1:C1')
    wl['A1'].value     = 'Легенда цветов (итоги работы по обращению)'
    wl['A1'].font      = Font(bold=True, size=12, color=HEADER_COLOR)
    wl['A1'].alignment = Alignment(horizontal='center')
    wl.row_dimensions[1].height = 22

    for ci, h in enumerate(['Цвет', 'Итог', 'Обозначение'], 1):
        c = wl.cell(row=2, column=ci, value=h)
        c.fill = PatternFill('solid', fgColor=HEADER_COLOR)
        c.font = Font(bold=True, color='FFFFFF', size=10)
        c.border = _std_border()
        c.alignment = Alignment(horizontal='center', vertical='center')
    wl.row_dimensions[2].height = 20

    if result_types:
        for li, rt in enumerate(result_types, 3):
            argb = _hex_to_argb(rt['color_hex'] or 'FFFFFF')
            ca = wl.cell(row=li, column=1, value='')
            ca.fill = PatternFill('solid', fgColor=argb); ca.border = _std_border()
            cb = wl.cell(row=li, column=2, value=rt['name'])
            cb.fill = PatternFill('solid', fgColor=argb)
            cb.font = Font(bold=True, size=10); cb.border = _std_border()
            cb.alignment = Alignment(vertical='center')
            cc = wl.cell(row=li, column=3, value=rt['color_hex'])
            cc.font = Font(italic=True, size=9, color='888888'); cc.border = _std_border()
            cc.alignment = Alignment(vertical='center')
            wl.row_dimensions[li].height = 18
    else:
        wl.cell(row=3, column=1,
                value='Справочник итогов пуст. Добавьте значения в разделе «Справочники».')

    wl.column_dimensions['A'].width = 8
    wl.column_dimensions['B'].width = 36
    wl.column_dimensions['C'].width = 12

    fn = f"minek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    fp = os.path.join(REPORTS_DIR, fn)
    wb.save(fp)

    # ── Журнал действий ──────────────────────────────────────────────────────
    detail = f"период: {_fmt_date(df)} – {_fmt_date(dt)}; всего {len(rows)} обращ."
    try:
        log_action(conn, session['user_id'], 'export_minek', detail=detail)
        conn.commit()
    except Exception:
        pass
    conn.close()

    return send_file(fp, as_attachment=True, download_name=fn,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# ─── AUTOSAVE / WAL CHECKPOINT ───────────────────────────────────────────────

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
