# ╔══════════════════════════════════════════════════════════════╗
# ║ search_routes.py                                             ║
# ║ GlobalSearch: быстрый API + полная страница результатов     ║
# ║ Расширяемый список полей через SEARCH_FIELDS                ║
# ╚══════════════════════════════════════════════════════════════╝

from flask import Blueprint, request, jsonify, render_template, session
from db import get_db
from auth_utils import login_required

search_bp = Blueprint('search', __name__)

# ─── ПОЛЯ ПОИСКА ────────────────────────────────────────────────────────────────
# Чтобы добавить новое поле — просто добавьте строку в список.
# label — отображается в подсказке дропдауна рядом с совпадением
SEARCH_FIELDS = [
    {'col': 'request_number',      'label': '№ обращения'},
    {'col': 'applicant_full_name', 'label': 'Полн. наим.'},
    {'col': 'applicant_short_name','label': 'Краткое наим.'},
    {'col': 'applicant_inn',       'label': 'ИНН'},
    {'col': 'project_name',        'label': 'Проект'},
    {'col': 'contact_person',      'label': 'Контакт'},
    {'col': 'contact_phone',       'label': 'Телефон'},
    {'col': 'contact_email',       'label': 'E-mail'},
    {'col': 'additional_info',     'label': 'Доп. инфо'},
]

_MAX_DROPDOWN = 7   # максимум строк в дропдауне
_MAX_PAGE     = 50  # максимум строк на странице результатов


def _build_query(q: str, limit: int):
    """Строит SQL и params для поиска по всем SEARCH_FIELDS."""
    pattern = f'%{q}%'
    where_parts = ' OR '.join(f"r.{f['col']} LIKE ?" for f in SEARCH_FIELDS)
    params = [pattern] * len(SEARCH_FIELDS)

    sql = f"""
        SELECT
            r.id,
            r.request_number,
            r.applicant_short_name,
            r.applicant_full_name,
            r.applicant_inn,
            r.project_name,
            r.status,
            r.request_date,
            u.full_name  AS employee_name
        FROM requests r
        LEFT JOIN users u ON r.assigned_to = u.id
        WHERE ({where_parts})
        ORDER BY r.id DESC
        LIMIT ?
    """
    params.append(limit)
    return sql, params


# ─── API: быстрый поиск для дропдауна ───────────────────────────────────────────
@search_bp.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    conn = get_db()
    sql, params = _build_query(q, _MAX_DROPDOWN)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        # Определяем, в каком поле найдено совпадение (для подсказки)
        match_label = ''
        ql = q.lower()
        for f in SEARCH_FIELDS:
            val = r[f['col']] or ''
            if ql in val.lower():
                match_label = f['label']
                break

        results.append({
            'id':            r['id'],
            'number':        r['request_number'] or f'ID {r["id"]}',
            'name':          r['applicant_short_name'] or r['applicant_full_name'] or '—',
            'inn':           r['applicant_inn'] or '',
            'project':       r['project_name'] or '',
            'status':        r['status'] or '',
            'match_label':   match_label,
            'url':           f'/request/{r["id"]}/view',
        })
    return jsonify({'results': results, 'q': q})


# ─── Страница полных результатов ─────────────────────────────────────────────────
@search_bp.route('/search')
@login_required
def search_page():
    q = request.args.get('q', '').strip()
    results = []
    total = 0

    if len(q) >= 2:
        conn = get_db()
        sql, params = _build_query(q, _MAX_PAGE)
        rows = conn.execute(sql, params).fetchall()
        # Считаем точный total без LIMIT
        count_sql = sql.replace(
            'SELECT\n            r.id,\n            r.request_number,\n            r.applicant_short_name,\n            r.applicant_full_name,\n            r.applicant_inn,\n            r.project_name,\n            r.status,\n            r.request_date,\n            u.full_name  AS employee_name',
            'SELECT COUNT(*) AS cnt'
        ).replace('ORDER BY r.id DESC\n        LIMIT ?', '')
        total = conn.execute(count_sql, params[:-1]).fetchone()['cnt']
        conn.close()
        results = [dict(r) for r in rows]

    return render_template('search.html', q=q, results=results,
                           total=total, limit=_MAX_PAGE)
