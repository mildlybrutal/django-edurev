"""Excel (.xlsx) export and import helpers for staff lists. Exports are for the placement cell and
faculty only; the recruiter portal has no export of any kind (AGENTS.md §17)."""

from datetime import date, datetime

from django.http import HttpResponse
from django.utils import timezone

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
# Spreadsheet apps execute cells that start with these as formulas (CSV/formula injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExcelError(ValueError):
    pass


def _cell(value):
    if isinstance(value, datetime):
        return timezone.localtime(value).replace(tzinfo=None) if timezone.is_aware(value) else value
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def workbook_response(filename, sheets):
    """sheets: [(title, [(header, key)], rows)]. Rows are dicts; `key` may be a callable."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font

    wb = Workbook(write_only=True)
    for title, columns, rows in sheets:
        ws = wb.create_sheet(title=title[:31])
        ws.freeze_panes = "A2"
        header = []
        for name, _ in columns:
            c = WriteOnlyCell(ws, value=name)
            c.font = Font(bold=True)
            header.append(c)
        ws.append(header)
        for row in rows:
            ws.append([_cell(key(row) if callable(key) else row.get(key)) for _, key in columns])
    response = HttpResponse(content_type=XLSX)
    stamp = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="{filename}-{stamp}.xlsx"'
    response["Cache-Control"] = "no-store"
    wb.save(response)
    return response


def read_rows(uploaded, required):
    """Rows of the first sheet as dicts keyed by normalised header (lower_snake_case). Returns
    [(excel_row_number, row)]; blank rows are skipped."""
    from openpyxl import load_workbook

    if uploaded.size > MAX_IMPORT_BYTES:
        raise ExcelError(f"The file must be {MAX_IMPORT_BYTES // (1024 * 1024)} MB or smaller.")
    if not uploaded.name.lower().endswith(".xlsx"):
        raise ExcelError("Upload an Excel .xlsx file.")
    uploaded.seek(0)
    if uploaded.read(4) != b"PK\x03\x04":
        raise ExcelError("That file is not a valid .xlsx workbook.")
    uploaded.seek(0)
    try:
        wb = load_workbook(uploaded, read_only=True, data_only=True)
    except Exception as exc:
        raise ExcelError("That file is not a valid .xlsx workbook.") from exc
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    try:
        header = [_key(h) for h in next(rows)]
    except StopIteration:
        raise ExcelError("The sheet is empty.") from None
    missing = [c for c in required if c not in header]
    if missing:
        raise ExcelError(f"Missing column(s): {', '.join(missing)}.")
    out = []
    for number, values in enumerate(rows, start=2):
        if all(v is None or str(v).strip() == "" for v in values):
            continue
        if len(out) >= MAX_IMPORT_ROWS:
            raise ExcelError(f"Import at most {MAX_IMPORT_ROWS} rows at a time.")
        out.append((number, {h: _clean(v) for h, v in zip(header, values, strict=False) if h}))
    wb.close()
    return out


def _key(header):
    return str(header or "").strip().lower().replace(" ", "_").replace("-", "_")


def _clean(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return value
