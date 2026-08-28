import asyncio
import os
from pathlib import Path
import shutil
import time
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, Response

from .config import get_settings
from .errors import AppError
from .image_utils import decode_image
from .services.ink_cutout import remove_white_background
from .services.image_compression import compress_image
from .services.excel_headers import ExcelHeaderError, extract_excel_headers
from .services.screen_recording_store import (
    RecordingNotFoundError,
    RecordingSequenceError,
)
from .services.screen_recording_transcoder import (
    RecordingTranscodeError,
    RecordingTranscodeTimeoutError,
)
from .services.video_compression import VideoCompressionOptions
from .services.windows_build import WindowsBuildManager

router = APIRouter(prefix="/api/v1")


class StartWindowsBuildRequest(BaseModel):
    targetDirectory: str | None = None


class CreateScreenRecordingRequest(BaseModel):
    mimeType: str


class CompleteScreenRecordingRequest(BaseModel):
    fileName: str
    durationSeconds: int = Field(ge=0)


@router.post("/windows-builds")
async def start_windows_build(
    request: Request, body: StartWindowsBuildRequest | None = None
):
    target_directory = body.targetDirectory if body else None
    result = await request.app.state.windows_build_manager.start(
        request.headers.get("Authorization"),
        target_directory=target_directory,
    )
    if result.get("requiresAppExit"):
        async def exit_after_response() -> None:
            await asyncio.sleep(2)
            os._exit(0)

        asyncio.create_task(exit_after_response())
    return {"success": True, "data": result, "requestId": request.state.request_id}


@router.get("/windows-builds/current")
async def current_windows_build(request: Request):
    return {
        "success": True,
        "data": request.app.state.windows_build_manager.status(),
        "requestId": request.state.request_id,
    }


@router.get("/windows-builds/artifacts/{file_name}")
async def download_windows_build_artifact(request: Request, file_name: str) -> FileResponse:
    manager: WindowsBuildManager = request.app.state.windows_build_manager
    artifact_path = manager.get_artifact_path(file_name)
    if artifact_path is None or not artifact_path.is_file():
        raise AppError("ARTIFACT_NOT_FOUND", "构建产物不存在或未生成", 404)

    media_type = (
        "application/zip"
        if file_name.endswith(".zip")
        else "application/vnd.microsoft.portable-executable"
    )
    return FileResponse(
        path=artifact_path,
        media_type=media_type,
        filename=artifact_path.name,
        headers={
            "X-Request-Id": request.state.request_id,
            "Cache-Control": "no-store",
        },
    )


async def read_image_body(request: Request, file: UploadFile | None) -> bytes:
    settings = get_settings()
    if file is not None:
        data = await file.read(settings.max_upload_bytes + 1)
    else:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise AppError("INVALID_CONTENT_TYPE", "请上传 JPG、PNG 或 WebP 图片", 415)
        data = await request.body()
    if len(data) > settings.max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", f"图片不能超过 {settings.max_upload_mb}MB", 413)
    return data


async def read_pdf_upload(file: UploadFile | None) -> bytes:
    settings = get_settings()
    if file is None or not file.filename:
        raise AppError("INVALID_PDF", "請選擇 PDF 文件", 400)
    if not file.filename.lower().endswith(".pdf"):
        raise AppError("INVALID_PDF", "僅支持 PDF 文件", 400)
    content_type = (file.content_type or "").split(";", 1)[0].lower()
    if content_type not in {
        "",
        "application/pdf",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        raise AppError("INVALID_PDF", "僅支持 PDF 文件", 415)
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise AppError("INVALID_PDF", "PDF 文件不能為空", 400)
    if len(data) > settings.max_upload_bytes:
        raise AppError(
            "PDF_TOO_LARGE",
            f"PDF 不能超過 {settings.max_upload_mb}MB",
            413,
        )
    return data


async def read_image_compression_upload(request: Request, file: UploadFile | None) -> bytes:
    settings = get_settings()
    if file is not None and file.filename:
        data = await file.read(settings.image_compression_max_upload_bytes + 1)
    else:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise AppError("INVALID_CONTENT_TYPE", "仅支持 JPG、PNG 和 WebP 图片", 415)
        data = await request.body()
    if not data:
        raise AppError("EMPTY_FILE", "图片不能为空", 400)
    if len(data) > settings.image_compression_max_upload_bytes:
        raise AppError(
            "FILE_TOO_LARGE",
            f"图片不能超过 {settings.image_compression_max_upload_mb}MB",
            413,
        )
    return data


async def run_inference(request: Request, operation):
    semaphore: asyncio.Semaphore = request.app.state.inference_semaphore
    settings = get_settings()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=settings.inference_wait_seconds)
    except TimeoutError as exc:
        raise AppError("SERVER_BUSY", "当前处理人数较多，请稍后重试", 503) from exc
    try:
        return await asyncio.to_thread(operation)
    finally:
        semaphore.release()


@router.get("/health")
async def health(request: Request) -> dict:
    return {
        "success": True,
        "data": {
            "status": "ok",
            "ocrReady": request.app.state.ocr_service.ready,
            "cutoutReady": request.app.state.cutout_service.ready,
            "pdfConversionReady": request.app.state.pdf_conversion_runner.ready,
            "screenRecordingReady": request.app.state.screen_recording_transcoder.ready,
            "videoCompressionReady": request.app.state.video_compression_manager.ready,
        },
        "requestId": request.state.request_id,
    }


@router.post("/excel-headers")
async def excel_headers(request: Request, file: UploadFile | None = File(default=None)) -> dict:
    settings = get_settings()
    if file is None or not file.filename:
        raise AppError("INVALID_EXCEL", "请选择 Excel 文件", 400)
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xls", ".xlsx", ".csv"}:
        raise AppError("INVALID_EXCEL", "仅支持 XLS、XLSX 和 CSV 文件", 415)

    max_bytes = settings.excel_max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise AppError("EMPTY_FILE", "Excel 文件不能为空", 400)
    if len(content) > max_bytes:
        raise AppError(
            "EXCEL_TOO_LARGE",
            f"Excel 文件不能超过 {settings.excel_max_upload_mb}MB",
            413,
        )
    try:
        result = await asyncio.to_thread(extract_excel_headers, content, file.filename)
    except ExcelHeaderError as exc:
        raise AppError("INVALID_EXCEL", str(exc), 422) from exc
    return {"success": True, "data": result, "requestId": request.state.request_id}


@router.post("/image-compressions", response_class=Response)
async def image_compression(
    request: Request,
    file: UploadFile | None = File(default=None),
    preset_form: str | None = Form(default=None, alias="preset"),
    max_dimension_form: int | None = Form(default=None, alias="maxDimension"),
    quality_form: int | None = Form(default=None, alias="quality"),
    target_size_kb_form: int | None = Form(default=None, alias="targetSizeKb"),
    output_format_form: str | None = Form(default=None, alias="outputFormat"),
    preset_query: str | None = Query(default=None, alias="preset"),
    max_dimension_query: int | None = Query(default=None, alias="maxDimension"),
    quality_query: int | None = Query(default=None, alias="quality"),
    target_size_kb_query: int | None = Query(default=None, alias="targetSizeKb"),
    output_format_query: str | None = Query(default=None, alias="outputFormat"),
) -> Response:
    settings = get_settings()
    data = await read_image_compression_upload(request, file)
    preset = preset_form or preset_query or "balanced"
    max_dimension = max_dimension_form or max_dimension_query
    quality = quality_form or quality_query
    target_size_kb = target_size_kb_form or target_size_kb_query
    output_format = output_format_form or output_format_query or "auto"
    result = await asyncio.to_thread(
        compress_image,
        data,
        preset=preset,
        max_dimension=max_dimension,
        quality=quality,
        target_bytes=target_size_kb * 1024 if target_size_kb is not None else None,
        output_format=output_format,
        absolute_max_dimension=settings.image_compression_max_dimension,
    )
    source_name = Path(file.filename if file and file.filename else "compressed-image").stem
    file_name = f"{source_name}-compressed.{result.extension}"
    ratio = max(0, round((1 - len(result.content) / result.original_size) * 100, 1))
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}",
            "X-Original-Size": str(result.original_size),
            "X-Output-Size": str(len(result.content)),
            "X-Image-Width": str(result.width),
            "X-Image-Height": str(result.height),
            "X-Output-Format": result.output_format.lower(),
            "X-Compression-Ratio": str(ratio),
            "X-Compression-Skipped": str(result.skipped).lower(),
            "X-Target-Reached": str(result.target_reached).lower(),
            "Cache-Control": "no-store",
        },
    )


@router.post("/video-compressions", status_code=status.HTTP_201_CREATED)
async def create_video_compression(
    request: Request,
    file: UploadFile | None = File(default=None),
    preset: str = Form(default="balanced"),
    max_height: int | None = Form(default=None, alias="maxHeight"),
    crf: int | None = Form(default=None),
    target_size_mb: int | None = Form(default=None, alias="targetSizeMb"),
) -> dict:
    if file is None or not file.filename:
        raise AppError("INVALID_VIDEO", "请选择视频文件", 400)
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise AppError("INVALID_VIDEO_FORMAT", "仅支持 MP4、MOV、MKV 和 WebM", 415)
    if preset not in {"small", "balanced", "high", "custom"}:
        raise AppError("INVALID_COMPRESSION_PRESET", "视频压缩预设不正确", 422)
    if max_height is not None and max_height not in {480, 720, 1080, 2160}:
        raise AppError("INVALID_VIDEO_HEIGHT", "视频分辨率不正确", 422)
    if crf is not None and not 18 <= crf <= 35:
        raise AppError("INVALID_VIDEO_QUALITY", "视频质量必须在 18 到 35 之间", 422)
    if target_size_mb is not None and target_size_mb < 1:
        raise AppError("INVALID_TARGET_SIZE", "目标大小不能低于 1MB", 422)

    settings = get_settings()
    manager = request.app.state.video_compression_manager
    job_id, input_path = manager.allocate_upload(suffix)
    size = 0
    try:
        with input_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.video_compression_max_upload_bytes:
                    raise AppError(
                        "VIDEO_TOO_LARGE",
                        f"视频不能超过 {settings.video_compression_max_upload_bytes // 1024 // 1024}MB",
                        413,
                    )
                output.write(chunk)
        if size == 0:
            raise AppError("EMPTY_FILE", "视频不能为空", 400)
    except AppError:
        input_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        input_path.unlink(missing_ok=True)
        raise AppError("VIDEO_STORAGE_ERROR", "磁盘空间不足或无法保存临时视频", 507) from exc

    job = manager.register(
        job_id,
        input_path,
        file.filename,
        VideoCompressionOptions(preset, max_height, crf, target_size_mb),
    )
    manager.start(job.job_id, request.app.state.video_compression_semaphore)
    return {
        "success": True,
        "data": _video_job_payload(job),
        "requestId": request.state.request_id,
    }


@router.get("/video-compressions/{job_id}")
async def get_video_compression(request: Request, job_id: str) -> dict:
    job = request.app.state.video_compression_manager.get(job_id)
    if job is None:
        raise AppError("VIDEO_JOB_NOT_FOUND", "视频压缩任务不存在或已过期", 404)
    return {
        "success": True,
        "data": _video_job_payload(job),
        "requestId": request.state.request_id,
    }


@router.get("/video-compressions/results/{token}", response_class=FileResponse)
async def download_video_compression(request: Request, token: str) -> FileResponse:
    job = request.app.state.video_compression_manager.get_result(token)
    if job is None:
        raise AppError("VIDEO_RESULT_NOT_FOUND", "视频结果不存在或已过期", 404)
    return FileResponse(
        job.output_path,
        media_type="video/mp4",
        filename=job.file_name,
        headers={"Cache-Control": "no-store", "X-Request-Id": request.state.request_id},
    )


@router.delete("/video-compressions/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_video_compression(request: Request, job_id: str) -> Response:
    request.app.state.video_compression_manager.cancel(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _video_job_payload(job) -> dict:
    return {
        "jobId": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "fileName": job.file_name,
        "originalSize": job.original_size,
        "outputSize": job.output_size or None,
        "durationSeconds": job.duration_seconds or None,
        "token": job.token,
        "expiresAt": (
            job.expires_at.isoformat().replace("+00:00", "Z") if job.expires_at else None
        ),
        "errorCode": job.error_code,
        "errorMessage": job.error_message,
    }


@router.post("/ocr")
async def ocr(request: Request, file: UploadFile | None = File(default=None)) -> dict:
    settings = get_settings()
    data = await read_image_body(request, file)
    decoded = decode_image(data, settings.max_image_dimension)
    lines = await run_inference(
        request, lambda: request.app.state.ocr_service.recognize(decoded.image)
    )
    if not lines:
        raise AppError("NO_TEXT_FOUND", "没有识别到文字，请更换图片重试", 422)
    return {
        "success": True,
        "data": {"text": "\n".join(str(line["text"]) for line in lines), "lines": lines},
        "requestId": request.state.request_id,
    }


@router.post("/cutout", response_class=Response)
async def cutout(request: Request, file: UploadFile | None = File(default=None)) -> Response:
    settings = get_settings()
    started = time.perf_counter()
    data = await read_image_body(request, file)
    decoded = decode_image(data, settings.max_image_dimension)
    result = await run_inference(
        request, lambda: request.app.state.cutout_service.remove_background(decoded.image)
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return Response(
        content=result,
        media_type="image/png",
        headers={
            "X-Request-Id": request.state.request_id,
            "X-Process-Time-Ms": str(elapsed_ms),
            "Cache-Control": "no-store",
        },
    )


@router.post("/ink-cutout", response_class=Response)
async def ink_cutout(
    request: Request,
    file: UploadFile | None = File(default=None),
    threshold: int = Query(default=18, ge=0, le=80),
) -> Response:
    settings = get_settings()
    started = time.perf_counter()
    data = await read_image_body(request, file)
    decoded = decode_image(data, settings.max_image_dimension)
    result = await run_inference(
        request, lambda: remove_white_background(decoded.image, threshold)
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return Response(
        content=result,
        media_type="image/png",
        headers={
            "X-Request-Id": request.state.request_id,
            "X-Process-Time-Ms": str(elapsed_ms),
            "Cache-Control": "no-store",
        },
    )


@router.post("/pdf-conversions", status_code=status.HTTP_201_CREATED)
async def create_pdf_conversion(
    request: Request,
    file: UploadFile | None = File(default=None),
    output_format: str = Form(alias="outputFormat"),
) -> dict:
    if output_format not in {"xlsx", "docx"}:
        raise AppError("INVALID_REQUEST", "輸出格式必須是 xlsx 或 docx", 422)
    data = await read_pdf_upload(file)
    settings = get_settings()
    semaphore: asyncio.Semaphore = request.app.state.pdf_conversion_semaphore
    try:
        await asyncio.wait_for(
            semaphore.acquire(),
            timeout=settings.pdf_conversion_wait_seconds,
        )
    except TimeoutError as exc:
        raise AppError("SERVER_BUSY", "當前轉換人數較多，請稍後重試", 503) from exc

    store = request.app.state.conversion_result_store
    job_dir = store.create_job_dir()
    input_path = job_dir / "input.pdf"
    output_path = job_dir / f"output.{output_format}"
    try:
        input_path.write_bytes(data)
        await asyncio.to_thread(
            request.app.state.pdf_conversion_runner.run,
            input_path,
            output_path,
            output_format,
        )
        artifact = store.publish(
            output_path,
            file.filename or "converted.pdf",
            output_format,
        )
    finally:
        semaphore.release()
        shutil.rmtree(job_dir, ignore_errors=True)

    return {
        "success": True,
        "data": {
            "token": artifact.token,
            "fileName": artifact.file_name,
            "format": artifact.output_format,
            "expiresAt": artifact.expires_at.isoformat().replace("+00:00", "Z"),
        },
        "requestId": request.state.request_id,
    }


@router.get("/pdf-conversions/{token}/download", response_class=FileResponse)
async def download_pdf_conversion(request: Request, token: str) -> FileResponse:
    artifact = request.app.state.conversion_result_store.get(token)
    if artifact is None:
        raise AppError(
            "RESULT_NOT_FOUND",
            "轉換結果不存在或已過期，請重新轉換",
            404,
        )
    return FileResponse(
        path=artifact.path,
        media_type=artifact.media_type,
        filename=artifact.file_name,
        headers={
            "X-Request-Id": request.state.request_id,
            "Cache-Control": "no-store",
        },
    )


@router.post("/screen-recordings", status_code=status.HTTP_201_CREATED)
async def create_screen_recording(
    request: Request, body: CreateScreenRecordingRequest
) -> dict:
    mime_type = body.mimeType.strip().lower()
    if not mime_type.startswith("video/webm"):
        raise AppError("INVALID_RECORDING_FORMAT", "仅支持 WebM 录屏格式", 422)
    try:
        session = request.app.state.screen_recording_store.create(mime_type)
    except OSError as exc:
        raise AppError("RECORDING_STORAGE_ERROR", "无法创建本地录屏文件", 507) from exc
    return {
        "success": True,
        "data": {
            "recordingId": session.recording_id,
            "chunkIntervalMs": 2000,
        },
        "requestId": request.state.request_id,
    }


@router.put("/screen-recordings/{recording_id}/chunks/{sequence}")
async def append_screen_recording_chunk(
    request: Request, recording_id: str, sequence: int
) -> dict:
    if sequence < 0:
        raise AppError("INVALID_CHUNK_SEQUENCE", "录屏分片序号不正确", 422)
    settings = get_settings()
    data = await request.body()
    if not data:
        raise AppError("EMPTY_RECORDING_CHUNK", "录屏分片不能为空", 400)
    if len(data) > settings.screen_recording_max_chunk_bytes:
        raise AppError("RECORDING_CHUNK_TOO_LARGE", "录屏分片过大", 413)
    try:
        session = request.app.state.screen_recording_store.append(
            recording_id, sequence, data
        )
    except RecordingNotFoundError as exc:
        raise AppError("RECORDING_NOT_FOUND", "录屏任务不存在或已过期", 404) from exc
    except RecordingSequenceError as exc:
        raise AppError(
            "INVALID_CHUNK_SEQUENCE",
            f"录屏分片顺序错误，下一片应为 {exc.expected}",
            409,
        ) from exc
    except OSError as exc:
        raise AppError("RECORDING_STORAGE_ERROR", "写入录屏文件失败，请检查磁盘空间", 507) from exc
    return {
        "success": True,
        "data": {
            "nextSequence": session.next_sequence,
            "sizeBytes": session.size_bytes,
        },
        "requestId": request.state.request_id,
    }


async def transcode_screen_recording(request: Request, recording_id: str, file_name: str):
    settings = get_settings()
    semaphore: asyncio.Semaphore = request.app.state.screen_recording_conversion_semaphore
    try:
        await asyncio.wait_for(
            semaphore.acquire(),
            timeout=settings.screen_recording_conversion_wait_seconds,
        )
    except TimeoutError as exc:
        raise AppError(
            "RECORDING_CONVERTER_BUSY", "MP4 转换正在忙，请稍后重试", 503
        ) from exc

    finished = None
    output_path = None
    try:
        store = request.app.state.screen_recording_store
        finished = store.finish_input(recording_id)
        output_path = store.create_transcode_path()
        await asyncio.to_thread(
            request.app.state.screen_recording_transcoder.convert,
            finished.path,
            output_path,
        )
        return store.publish_mp4(output_path, file_name)
    except RecordingTranscodeTimeoutError as exc:
        raise AppError(
            "RECORDING_CONVERSION_TIMEOUT", "生成 MP4 超时，请重试", 504
        ) from exc
    except RecordingTranscodeError as exc:
        raise AppError(
            "RECORDING_CONVERSION_FAILED", "无法生成 MP4 视频", 500
        ) from exc
    finally:
        semaphore.release()
        if finished is not None:
            finished.path.unlink(missing_ok=True)
        if output_path is not None:
            output_path.unlink(missing_ok=True)


@router.post("/screen-recordings/{recording_id}/complete")
async def complete_screen_recording(
    request: Request,
    recording_id: str,
    body: CompleteScreenRecordingRequest,
) -> dict:
    try:
        artifact = await transcode_screen_recording(
            request, recording_id, body.fileName
        )
    except RecordingNotFoundError as exc:
        raise AppError("RECORDING_NOT_FOUND", "录屏任务不存在或已过期", 404) from exc
    except ValueError as exc:
        raise AppError("EMPTY_RECORDING", "没有可保存的录屏内容", 400) from exc
    except OSError as exc:
        raise AppError("RECORDING_STORAGE_ERROR", "完成录屏文件失败，请检查磁盘空间", 507) from exc
    return {
        "success": True,
        "data": {
            "token": artifact.token,
            "fileName": artifact.file_name,
            "format": "mp4",
            "sizeBytes": artifact.size_bytes,
            "expiresAt": artifact.expires_at.isoformat().replace("+00:00", "Z"),
        },
        "requestId": request.state.request_id,
    }


@router.get(
    "/screen-recordings/{token}/download",
    response_class=FileResponse,
)
async def download_screen_recording(request: Request, token: str) -> FileResponse:
    store = request.app.state.screen_recording_store
    artifact = store.get_artifact(token)
    if artifact is None:
        raise AppError("RECORDING_NOT_FOUND", "录屏文件不存在或已过期", 404)
    return FileResponse(
        path=artifact.path,
        media_type=artifact.mime_type,
        filename=artifact.file_name,
        headers={
            "X-Request-Id": request.state.request_id,
            "Cache-Control": "no-store",
        },
    )


@router.delete(
    "/screen-recordings/results/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_screen_recording_result(request: Request, token: str) -> Response:
    request.app.state.screen_recording_store.delete_artifact(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/screen-recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_screen_recording(request: Request, recording_id: str) -> Response:
    request.app.state.screen_recording_store.cancel(recording_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
