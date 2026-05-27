# ╔══════════════════════════════════════════════════════════════╗
# ║                      auth_utils.py                           ║
# ║  v2.1: PBKDF2-HMAC-SHA256 + плавный переход с SHA-256     ║
# ╚══════════════════════════════════════════════════════════════╝

import hashlib
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash


def hash_pw(p: str) -> str:
    """Хеширует пароль через PBKDF2-HMAC-SHA256 с солью (werkzeug)."""
    return generate_password_hash(p)


def check_pw(stored: str, entered: str) -> bool:
    """
    Проверяет пароль. Поддерживает оба формата:
    - новый: pbkdf2:sha256:... (через werkzeug)
    - старый: 64-символьный hex (SHA-256 без соли)
    """
    if stored and stored.startswith('pbkdf2:'):
        return check_password_hash(stored, entered)
    # Обратная совместимость: старые SHA-256 хеши продолжают работать
    return stored == hashlib.sha256(entered.encode()).hexdigest()


def is_legacy_hash(stored: str) -> bool:
    """Возвращает True если хеш старый (SHA-256 без соли)."""
    return bool(stored) and not stored.startswith('pbkdf2:')


# ─── ПРАВА ПОЛЬЗОВАТЕЛЯ (ключи = поля в таблице users) ──────────────────

ALL_PERMISSIONS = {
    'can_create':      'Создавать обращения',
    'can_edit_others': 'Редактировать чужие обращения',
    'can_confirm':     'Принимать / отклонять обращения',
    'can_delete':      'Удалять обращения',
    'can_rollback':    'Откат истории',
    'can_export':      'Экспорт в Excel',
    'can_classifiers': 'Управление справочниками',
    'can_users':       'Управление пользователями',
    'can_view_all':    'Видит все обращения (вкл. поиск)',
}

# Пресет: admin получает все права автоматически
ADMIN_PERMISSIONS = {k: 1 for k in ALL_PERMISSIONS}


def get_user_perm(key: str) -> bool:
    """
    Проверяет право текущего пользователя по ключу.
    Администратор всегда имеет все права.
    """
    if session.get('role') == 'admin':
        return True
    return bool(session.get(f'perm_{key}', 0))


# ─── ДЕКОРАТОРЫ ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Оставлен для обратной совместимости. Проверяет role==admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Доступ запрещён', 'error')
            return redirect(url_for('requests.index'))
        return f(*args, **kwargs)
    return decorated


def permission_required(perm_key: str):
    """
    Универсальный декоратор для проверки конкретного права.
    Использование: @permission_required('can_confirm')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            if not get_user_perm(perm_key):
                flash(f'Недостаточно прав: {ALL_PERMISSIONS.get(perm_key, perm_key)}', 'error')
                return redirect(url_for('requests.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def load_permissions_to_session(user_row) -> None:
    """
    Вызывается при логине. Записывает все права пользователя
    в сессию как perm_<key> = 0/1.
    Администратор получает все права автоматически.
    """
    if user_row['role'] == 'admin':
        for key in ALL_PERMISSIONS:
            session[f'perm_{key}'] = 1
    else:
        for key in ALL_PERMISSIONS:
            session[f'perm_{key}'] = int(user_row[key] or 0)
