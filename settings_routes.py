# ╔══════════════════════════════════════════════════════════════╗
# ║ settings_routes.py                                           ║
# ║ feat #10: Страница настроек пользователя                    ║
# ║  - смена пароля                                              ║
# ║  - выбор темы (light/dark/system)                           ║
# ║  - уведомления на почту вкл/выкл                            ║
# ║ feat: переключение ветки main/dev (только admin)             ║
# ╚══════════════════════════════════════════════════════════════╝

import os
import sys
import subprocess
import threading
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from db import get_db, BASE_DIR
from auth_utils import login_required, hash_pw
from activity_log import log_action

settings_bp = Blueprint('settings', __name__)

BRANCH_FILE  = os.path.join(BASE_DIR, "_branch.txt")
LOCK_FILE    = os.path.join(BASE_DIR, "_updating.lock")
RESTART_FLAG = os.path.join(BASE_DIR, "_restart.flag")


def _get_active_branch() -> str:
    """Читает активную ветку из _branch.txt."""
    if os.path.exists(BRANCH_FILE):
        try:
            val = open(BRANCH_FILE, encoding="utf-8").read().strip()
            if val in ("main", "dev"):
                return val
        except Exception:
            pass
    return "main"


@settings_bp.route('/settings', methods=['GET'])
@login_required
def settings():
    db = get_db()
    user = db.execute(
        'SELECT id, username, full_name, role, email, theme, email_notifications '
        'FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    db.close()
    active_branch   = _get_active_branch()
    is_switching    = os.path.exists(LOCK_FILE)
    return render_template(
        'settings.html',
        user=user,
        active_branch=active_branch,
        is_switching=is_switching,
    )


@settings_bp.route('/settings/password', methods=['POST'])
@login_required
def settings_password():
    current_pw  = request.form.get('current_password', '').strip()
    new_pw      = request.form.get('new_password', '').strip()
    confirm_pw  = request.form.get('confirm_password', '').strip()

    if not current_pw or not new_pw or not confirm_pw:
        flash('Заполните все поля для смены пароля.', 'error')
        return redirect(url_for('settings.settings'))

    if new_pw != confirm_pw:
        flash('Новый пароль и подтверждение не совпадают.', 'error')
        return redirect(url_for('settings.settings'))

    if len(new_pw) < 6:
        flash('Новый пароль должен содержать не менее 6 символов.', 'error')
        return redirect(url_for('settings.settings'))

    db = get_db()
    user = db.execute(
        'SELECT password FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()

    if not user or user['password'] != hash_pw(current_pw):
        db.close()
        flash('Текущий пароль указан неверно.', 'error')
        return redirect(url_for('settings.settings'))

    db.execute(
        'UPDATE users SET password = ?, must_change_password = 0 WHERE id = ?',
        (hash_pw(new_pw), session['user_id'])
    )
    db.commit()
    db.close()
    flash('Пароль успешно изменён.', 'success')
    return redirect(url_for('settings.settings'))


@settings_bp.route('/settings/preferences', methods=['POST'])
@login_required
def settings_preferences():
    theme               = request.form.get('theme', 'light')
    email_notifications = 1 if request.form.get('email_notifications') else 0
    email               = request.form.get('email', '').strip()

    if theme not in ('light', 'dark', 'system'):
        theme = 'light'

    db = get_db()
    cols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
    if 'email' not in cols:
        db.execute('ALTER TABLE users ADD COLUMN email TEXT DEFAULT NULL')
    if 'theme' not in cols:
        db.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'light'")
    if 'email_notifications' not in cols:
        db.execute('ALTER TABLE users ADD COLUMN email_notifications INTEGER DEFAULT 0')

    db.execute(
        'UPDATE users SET theme = ?, email_notifications = ?, email = ? WHERE id = ?',
        (theme, email_notifications, email or None, session['user_id'])
    )
    db.commit()
    db.close()

    session['theme'] = theme
    flash('Настройки сохранены.', 'success')
    return redirect(url_for('settings.settings'))


@settings_bp.route('/settings/switch-branch', methods=['POST'])
@login_required
def switch_branch():
    """Переключение ветки main/dev. Только для admin."""
    if session.get('role') != 'admin':
        flash('Недостаточно прав.', 'error')
        return redirect(url_for('settings.settings'))

    target = request.form.get('branch', '').strip()
    if target not in ('main', 'dev'):
        flash('Недопустимое значение ветки.', 'error')
        return redirect(url_for('settings.settings'))

    current = _get_active_branch()
    if target == current:
        flash(f'Уже активна ветка «{target}».', 'info')
        return redirect(url_for('settings.settings'))

    # Защита от двойного запуска
    if os.path.exists(LOCK_FILE):
        flash('Переключение уже выполняется, подождите.', 'warning')
        return redirect(url_for('settings.settings'))

    # Создаём lock
    with open(LOCK_FILE, "w") as f:
        f.write("switching")

    # Логируем
    db = get_db()
    log_action(db, session['user_id'], 'branch_switch', None,
               f'Переключение ветки: {current} → {target}')
    db.commit()
    db.close()

    # Запускаем переключение в фоне — Flask успевает вернуть ответ
    def _do_switch():
        switcher = os.path.join(BASE_DIR, "branch_switcher.py")
        subprocess.run(
            [sys.executable, switcher, target],
            cwd=BASE_DIR,
        )
        # После завершения _restart.flag уже создан → Flask сам остановится
        # Посылаем себе сигнал завершения
        import signal
        os.kill(os.getpid(), signal.SIGTERM)

    t = threading.Thread(target=_do_switch, daemon=True)
    t.start()

    branch_label = '🧪 DEV (экспериментальная)' if target == 'dev' else '✅ MAIN (стабильная)'
    flash(
        f'Переключение на {branch_label} запущено. '
        f'Сервер перезапустится автоматически через несколько секунд...',
        'info'
    )
    return redirect(url_for('settings.settings'))
