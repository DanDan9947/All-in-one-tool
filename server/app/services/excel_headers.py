from __future__ import annotations

import csv
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable

import openpyxl
import xlrd
from opencc import OpenCC


SUPPORTED_EXCEL_SUFFIXES = {".xls", ".xlsx", ".csv"}
MAX_SCAN_ROWS = 50
MAX_SCAN_COLUMNS = 200
MAX_PREVIEW_ROWS = 3
MAX_CELL_TEXT = 200
TRADITIONAL_TO_SIMPLIFIED = OpenCC("t2s")


class ExcelHeaderError(ValueError):
    pass


def extract_excel_headers(content: bytes, file_name: str) -> dict[str, Any]:
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_EXCEL_SUFFIXES:
        raise ExcelHeaderError("仅支持 XLS、XLSX 和 CSV 文件")

    if suffix == ".xls":
        sheets = _read_xls(content)
    elif suffix == ".xlsx":
        sheets = _read_xlsx(content)
    else:
        sheets = _read_csv(content, Path(file_name).stem or "CSV")

    results = []
    for sheet_name, rows in sheets:
        detected = _detect_header(rows)
        if detected is not None:
            results.append({"sheetName": sheet_name, **detected})

    if not results:
        raise ExcelHeaderError("没有在文件中识别到标题行")

    return {"fileName": file_name, "sheetCount": len(results), "sheets": results}


def _read_xls(content: bytes) -> list[tuple[str, list[list[Any]]]]:
    try:
        workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
    except Exception as exc:
        raise ExcelHeaderError("无法读取 XLS 文件，文件可能已损坏或受密码保护") from exc

    sheets: list[tuple[str, list[list[Any]]]] = []
    try:
        for sheet in workbook.sheets():
            row_count = min(sheet.nrows, MAX_SCAN_ROWS)
            column_count = min(sheet.ncols, MAX_SCAN_COLUMNS)
            rows = [sheet.row_values(index, 0, column_count) for index in range(row_count)]
            sheets.append((sheet.name, rows))
    finally:
        workbook.release_resources()
    return sheets


def _read_xlsx(content: bytes) -> list[tuple[str, list[list[Any]]]]:
    try:
        workbook = openpyxl.load_workbook(
            BytesIO(content), read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:
        raise ExcelHeaderError("无法读取 XLSX 文件，文件可能已损坏或受密码保护") from exc

    sheets: list[tuple[str, list[list[Any]]]] = []
    try:
        for sheet in workbook.worksheets:
            rows = [
                list(row[:MAX_SCAN_COLUMNS])
                for row in sheet.iter_rows(max_row=MAX_SCAN_ROWS, values_only=True)
            ]
            sheets.append((sheet.title, rows))
    finally:
        workbook.close()
    return sheets


def _read_csv(content: bytes, sheet_name: str) -> list[tuple[str, list[list[Any]]]]:
    text = None
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ExcelHeaderError("无法识别 CSV 文件编码")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for index, row in enumerate(csv.reader(StringIO(text), dialect)):
        if index >= MAX_SCAN_ROWS:
            break
        rows.append(row[:MAX_SCAN_COLUMNS])
    return [(sheet_name, rows)]


def _detect_header(rows: list[list[Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    best: tuple[float, int, int, int] | None = None
    for row_index, row in enumerate(rows):
        populated = [(column_index, value) for column_index, value in enumerate(row) if _cell_text(value)]
        if len(populated) < 2:
            continue

        values = [_cell_text(value) for _, value in populated]
        text_count = sum(isinstance(value, str) for _, value in populated)
        distinct_count = len({value.casefold() for value in values})
        short_count = sum(len(value) <= 50 for value in values)
        first_column = populated[0][0]
        last_column = populated[-1][0]
        span = last_column - first_column + 1
        density = len(populated) / span
        score = (
            len(populated) * 4
            + text_count * 2
            + distinct_count * 0.5
            + short_count * 0.2
            + density * 8
            - row_index * 0.02
        )
        candidate = (score, -row_index, first_column, last_column)
        if best is None or candidate > best:
            best = candidate

    if best is None:
        return None

    _, negative_row_index, first_column, last_column = best
    header_index = -negative_row_index
    header_row = rows[header_index]
    original_headers = []
    for column_index in range(first_column, last_column + 1):
        value = _cell_text(header_row[column_index] if column_index < len(header_row) else None)
        original_headers.append(value or f"未命名列 {column_index + 1}")
    headers = [TRADITIONAL_TO_SIMPLIFIED.convert(value) for value in original_headers]

    preview_rows = []
    for row in rows[header_index + 1 : header_index + 1 + MAX_PREVIEW_ROWS]:
        values = [
            _cell_text(row[index] if index < len(row) else None)
            for index in range(first_column, last_column + 1)
        ]
        if any(values):
            preview_rows.append(values)

    return {
        "headerRow": header_index + 1,
        "columnCount": len(headers),
        "headers": headers,
        "originalHeaders": original_headers,
        "previewRows": preview_rows,
    }


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value)
    return " ".join(text.replace("\x00", "").split())[:MAX_CELL_TEXT]
