# ╔══════════════════════════════════════════════════════════════╗
# ║               tools/investmap_export.py                     ║
# ║  Конвертер выгрузки ГИС НСИ (инвестплощадки) → текст        ║
# ║  Формат 1: 1 площадка (атрибут|значение по строкам)         ║
# ║  Формат 2: N площадок (строки=площадки, столбцы=атрибуты)   ║
# ╚══════════════════════════════════════════════════════════════╝

import openpyxl
import io


def _clean(val):
    """Приводит значение ячейки к строке, убирает лишние пробелы."""
    if val is None:
        return ''
    s = str(val).strip()
    # Убираем HTML-теги если вдруг попали
    import re
    s = re.sub(r'<[^>]+>', '', s)
    return s


def _is_format1(ws):
    """
    Определяет формат выгрузки:
    Формат 1: 2 столбца (атрибут | значение), много строк.
    Формат 2: много столбцов (1я строка = заголовки), много строк-площадок.
    """
    max_col = ws.max_column
    max_row = ws.max_row
    if max_col <= 2 and max_row >= 3:
        return True
    return False


def parse_format1(ws):
    """
    Формат 1: 1 площадка.
    Каждая строка: (название атрибута, значение).
    Возвращает список строк для вставки в чат.
    """
    lines = []
    for row in ws.iter_rows(min_row=1):
        cells = [_clean(c.value) for c in row]
        # Берём первые два столбца
        attr = cells[0] if len(cells) > 0 else ''
        val  = cells[1] if len(cells) > 1 else ''
        if not attr:
            continue
        val_out = val if val else 'ПУСТО'
        lines.append(f"{attr} → {val_out}")
    return lines


def parse_format2(ws):
    """
    Формат 2: N площадок.
    Строка 1 = заголовки атрибутов.
    Строки 2+ = данные площадок.
    Возвращает список блоков (каждый блок — список строк).
    """
    headers = []
    for cell in next(ws.iter_rows(min_row=1, max_row=1)):
        headers.append(_clean(cell.value))

    blocks = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        cells = [_clean(c.value) for c in row]
        # Пропускаем полностью пустые строки
        if not any(cells):
            continue
        lines = [f"=== ПЛОЩАДКА {row_idx - 1} ==="]
        for h, v in zip(headers, cells):
            if not h:
                continue
            val_out = v if v else 'ПУСТО'
            lines.append(f"{h} → {val_out}")
        blocks.append(lines)
    return blocks


def convert_excel_to_text(file_bytes):
    """
    Основная функция.
    Принимает bytes файла .xlsx.
    Возвращает dict:
      {
        'format': 1 или 2,
        'count': количество площадок,
        'text': итоговый текст для вставки в чат,
        'error': None или строка ошибки
      }
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active

        if _is_format1(ws):
            lines = parse_format1(ws)
            text = '\n'.join(lines)
            return {
                'format': 1,
                'count': 1,
                'text': text,
                'error': None
            }
        else:
            blocks = parse_format2(ws)
            text = '\n\n'.join(['\n'.join(b) for b in blocks])
            return {
                'format': 2,
                'count': len(blocks),
                'text': text,
                'error': None
            }

    except Exception as e:
        return {
            'format': None,
            'count': 0,
            'text': '',
            'error': str(e)
        }
