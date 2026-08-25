from io import BytesIO


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "status": "ok",
        "ocrReady": True,
        "cutoutReady": True,
        "pdfConversionReady": True,
        "screenRecordingReady": True,
        "videoCompressionReady": True,
    }
    assert body["requestId"]


def test_excel_header_upload(client):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["報表名稱"])
    sheet.append([])
    sheet.append(["客戶編號", "客戶名稱", "銷售員"])
    sheet.append(["6010001", "測試客戶", "陳先生"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()

    response = client.post(
        "/api/v1/excel-headers",
        files={
            "file": (
                "report.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    sheet_result = response.json()["data"]["sheets"][0]
    assert sheet_result["headerRow"] == 3
    assert sheet_result["headers"] == ["客户编号", "客户名称", "销售员"]


def test_ocr_multipart(client, png_bytes):
    response = client.post(
        "/api/v1/ocr", files={"file": ("sample.png", png_bytes, "image/png")}
    )
    assert response.status_code == 200
    assert response.json()["data"]["text"] == "测试文字"


def test_cutout_accepts_raw_image_for_miniprogram(client, png_bytes):
    response = client.post(
        "/api/v1/cutout", content=png_bytes, headers={"Content-Type": "image/png"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_ink_cutout_accepts_raw_image_for_miniprogram(client, png_bytes):
    response = client.post(
        "/api/v1/ink-cutout?threshold=18",
        content=png_bytes,
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_invalid_image_has_consistent_error(client):
    response = client.post(
        "/api/v1/ocr",
        content=b"not-an-image",
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_IMAGE"
    assert response.json()["requestId"]


def test_rejects_wrong_content_type(client):
    response = client.post(
        "/api/v1/cutout", content=b"hello", headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 415
    assert response.json()["code"] == "INVALID_CONTENT_TYPE"


def test_rejects_oversized_image(client, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    response = client.post(
        "/api/v1/ocr", content=b"x", headers={"Content-Type": "image/png"}
    )
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_image_compression_returns_metadata(client):
    from io import BytesIO
    from PIL import Image

    source = BytesIO()
    Image.effect_noise((1000, 700), 80).convert("RGB").save(source, "PNG")
    response = client.post(
        "/api/v1/image-compressions",
        files={"file": ("large.png", source.getvalue(), "image/png")},
        data={"preset": "small", "outputFormat": "auto"},
    )
    assert response.status_code == 200
    assert response.headers["x-output-format"] in {"jpeg", "webp"}
    assert int(response.headers["x-original-size"]) == len(source.getvalue())
    assert int(response.headers["x-output-size"]) == len(response.content)
    assert response.headers["x-target-reached"] == "true"


def test_image_compression_preserves_transparency(client):
    from io import BytesIO
    from PIL import Image

    source = BytesIO()
    Image.new("RGBA", (80, 60), (255, 0, 0, 80)).save(source, "PNG")
    response = client.post(
        "/api/v1/image-compressions?preset=balanced&outputFormat=auto",
        content=source.getvalue(),
        headers={"Content-Type": "image/png"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_image_compression_rejects_invalid_target(client, png_bytes):
    response = client.post(
        "/api/v1/image-compressions",
        files={"file": ("sample.png", png_bytes, "image/png")},
        data={"preset": "custom", "targetSizeKb": "1"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TARGET_SIZE"


def test_pdf_conversion_and_download(client, pdf_bytes):
    response = client.post(
        "/api/v1/pdf-conversions",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"outputFormat": "xlsx"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["fileName"] == "sample.xlsx"
    assert body["data"]["format"] == "xlsx"
    assert body["data"]["expiresAt"].endswith("Z")

    download = client.get(
        f"/api/v1/pdf-conversions/{body['data']['token']}/download"
    )
    assert download.status_code == 200
    assert download.content == b"converted-xlsx"
    assert "sample.xlsx" in download.headers["content-disposition"]
    assert download.headers["cache-control"] == "no-store"


def test_pdf_conversion_rejects_wrong_format(client, pdf_bytes):
    response = client.post(
        "/api/v1/pdf-conversions",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        data={"outputFormat": "csv"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_pdf_conversion_rejects_non_pdf_extension(client):
    response = client.post(
        "/api/v1/pdf-conversions",
        files={"file": ("sample.txt", b"hello", "text/plain")},
        data={"outputFormat": "docx"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PDF"


def test_pdf_download_rejects_unknown_token(client):
    response = client.get("/api/v1/pdf-conversions/not-found/download")
    assert response.status_code == 404
    assert response.json()["code"] == "RESULT_NOT_FOUND"


def test_screen_recording_writes_chunks_and_downloads_once(client):
    created = client.post(
        "/api/v1/screen-recordings",
        json={"mimeType": "video/webm;codecs=vp9,opus"},
    )
    assert created.status_code == 201
    recording_id = created.json()["data"]["recordingId"]

    first = client.put(
        f"/api/v1/screen-recordings/{recording_id}/chunks/0",
        content=b"webm-header",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert first.status_code == 200
    assert first.json()["data"] == {"nextSequence": 1, "sizeBytes": 11}

    duplicate = client.put(
        f"/api/v1/screen-recordings/{recording_id}/chunks/0",
        content=b"webm-header",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["sizeBytes"] == 11

    second = client.put(
        f"/api/v1/screen-recordings/{recording_id}/chunks/1",
        content=b"-payload",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert second.status_code == 200

    completed = client.post(
        f"/api/v1/screen-recordings/{recording_id}/complete",
        json={"fileName": "屏幕录制_20260805_120000.mp4", "durationSeconds": 3},
    )
    assert completed.status_code == 200
    result = completed.json()["data"]
    assert result["fileName"] == "屏幕录制_20260805_120000.mp4"
    assert result["format"] == "mp4"
    assert result["sizeBytes"] == 19

    download = client.get(f"/api/v1/screen-recordings/{result['token']}/download")
    assert download.status_code == 200
    assert download.content == b"webm-header-payload"
    assert download.headers["content-type"].startswith("video/mp4")

    retry = client.get(f"/api/v1/screen-recordings/{result['token']}/download")
    assert retry.status_code == 200
    assert retry.content == b"webm-header-payload"

    deleted = client.delete(f"/api/v1/screen-recordings/results/{result['token']}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/screen-recordings/{result['token']}/download")
    assert missing.status_code == 404


def test_screen_recording_rejects_out_of_order_chunk(client):
    created = client.post(
        "/api/v1/screen-recordings", json={"mimeType": "video/webm"}
    )
    recording_id = created.json()["data"]["recordingId"]
    response = client.put(
        f"/api/v1/screen-recordings/{recording_id}/chunks/2",
        content=b"chunk",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_CHUNK_SEQUENCE"


def test_screen_recording_can_be_cancelled(client):
    created = client.post(
        "/api/v1/screen-recordings", json={"mimeType": "video/webm"}
    )
    recording_id = created.json()["data"]["recordingId"]
    assert client.delete(f"/api/v1/screen-recordings/{recording_id}").status_code == 204
    completed = client.post(
        f"/api/v1/screen-recordings/{recording_id}/complete",
        json={"fileName": "cancelled.mp4", "durationSeconds": 0},
    )
    assert completed.status_code == 404


def test_screen_recording_rejects_non_webm(client):
    response = client.post(
        "/api/v1/screen-recordings", json={"mimeType": "video/mp4"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_RECORDING_FORMAT"
