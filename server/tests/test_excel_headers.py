from io import BytesIO

from openpyxl import Workbook

from app.services.excel_headers import extract_excel_headers


def _workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "報表資料"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_detects_header_after_report_title_and_converts_to_simplified():
    content = _workbook_bytes(
        [
            ["理 文 造 紙 有 限 公 司"],
            ["報 價 單 明 細 表"],
            [],
            ["客戶編號", "客戶名稱", "銷售員", "貨幣"],
            ["6010001", "測試客戶", "陳先生", "RMB"],
        ]
    )

    result = extract_excel_headers(content, "quotation.xlsx")
    sheet = result["sheets"][0]

    assert sheet["sheetName"] == "報表資料"
    assert sheet["headerRow"] == 4
    assert sheet["originalHeaders"] == ["客戶編號", "客戶名稱", "銷售員", "貨幣"]
    assert sheet["headers"] == ["客户编号", "客户名称", "销售员", "货币"]


def test_detects_first_csv_row_as_header():
    content = "公司,投訴編號,處理狀態\n廣東公司,CPN001,完成\n".encode("utf-8")

    result = extract_excel_headers(content, "complaints.csv")
    sheet = result["sheets"][0]

    assert sheet["headerRow"] == 1
    assert sheet["headers"] == ["公司", "投诉编号", "处理状态"]
