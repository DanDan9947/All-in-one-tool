import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHttpException

from .api import router
from .config import get_settings
from .errors import (
    AppError,
    app_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from .services.cutout import CutoutService
from .services.conversion_store import ConversionResultStore
from .services.ocr import OcrService
from .services.pdf_conversion import PdfConversionRunner
from .services.screen_recording_store import ScreenRecordingStore
from .services.screen_recording_transcoder import ScreenRecordingTranscoder
from .services.video_compression import VideoCompressionManager

logger = logging.getLogger(__name__)


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHttpException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ocr_service = OcrService(settings.ocr_font_path)
    app.state.cutout_service = CutoutService(
        settings.modnet_model_path,
        settings.modnet_model_sha256,
        settings.cutout_inference_max_dimension,
    )
    app.state.inference_semaphore = asyncio.Semaphore(settings.inference_concurrency)
    app.state.pdf_conversion_runner = PdfConversionRunner(
        settings.pdf_max_pages,
        settings.pdf_conversion_timeout_seconds,
    )
    app.state.pdf_conversion_semaphore = asyncio.Semaphore(
        settings.pdf_conversion_concurrency
    )
    app.state.conversion_result_store = ConversionResultStore(
        settings.pdf_temp_dir,
        settings.pdf_result_ttl_seconds,
    )
    app.state.conversion_result_store.initialize()
    app.state.screen_recording_store = ScreenRecordingStore(
        settings.screen_recording_temp_dir,
        settings.screen_recording_abandoned_ttl_seconds,
        settings.screen_recording_result_ttl_seconds,
    )
    app.state.screen_recording_store.initialize()
    app.state.screen_recording_transcoder = ScreenRecordingTranscoder(
        settings.screen_recording_conversion_timeout_seconds
    )
    app.state.screen_recording_conversion_semaphore = asyncio.Semaphore(1)
    app.state.video_compression_manager = VideoCompressionManager(
        settings.video_compression_temp_dir,
        settings.video_compression_result_ttl_seconds,
        settings.video_compression_timeout_seconds,
    )
    app.state.video_compression_manager.initialize()
    app.state.video_compression_semaphore = asyncio.Semaphore(1)
    cleanup_stop = asyncio.Event()

    async def cleanup_conversion_results() -> None:
        cleanup_interval_seconds = min(
            60,
            max(1, settings.pdf_result_ttl_seconds),
        )
        while not cleanup_stop.is_set():
            try:
                await asyncio.wait_for(
                    cleanup_stop.wait(),
                    timeout=cleanup_interval_seconds,
                )
            except TimeoutError:
                app.state.conversion_result_store.cleanup_expired()
                app.state.screen_recording_store.cleanup_expired()
                app.state.video_compression_manager.cleanup_expired()

    cleanup_task = asyncio.create_task(cleanup_conversion_results())
    await asyncio.gather(
        asyncio.to_thread(app.state.ocr_service.load),
        asyncio.to_thread(app.state.cutout_service.load),
    )
    try:
        yield
    finally:
        cleanup_stop.set()
        await cleanup_task
        app.state.conversion_result_store.clear()
        app.state.screen_recording_store.clear()
        await app.state.video_compression_manager.shutdown()


app = FastAPI(
    title="蛋蛋小工具 API",
    version="0.1.0",
    docs_url="/docs" if get_settings().app_env == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)
app.include_router(router)

web_dist_path = get_settings().web_dist_path
if web_dist_path.is_dir() and (web_dist_path / "index.html").is_file():
    app.mount("/", SpaStaticFiles(directory=web_dist_path, html=True), name="web")
else:
    @app.get("/")
    async def root() -> JSONResponse:
        return JSONResponse(
            {"service": "dandan-tools", "health": "/api/v1/health"}
        )
