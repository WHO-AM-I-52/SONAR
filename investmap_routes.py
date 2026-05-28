# ╔══════════════════════════════════════════════════════════════╗
# ║                  investmap_routes.py                        ║
# ║  Конвертер инвестплощадок — только для администратора       ║
# ╚══════════════════════════════════════════════════════════════╝

from flask import Blueprint, render_template, request, jsonify, session
from auth_utils import login_required, admin_required
from tools.investmap_export import convert_excel_to_text

investmap_bp = Blueprint('investmap', __name__)


@investmap_bp.route('/admin/investmap')
@login_required
@admin_required
def investmap():
    return render_template('investmap.html')


@investmap_bp.route('/admin/investmap/convert', methods=['POST'])
@login_required
@admin_required
def investmap_convert():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'Файл не передан'}), 400
    if not f.filename.lower().endswith('.xlsx'):
        return jsonify({'error': 'Поддерживается только формат .xlsx'}), 400

    result = convert_excel_to_text(f.read())
    return jsonify(result)
