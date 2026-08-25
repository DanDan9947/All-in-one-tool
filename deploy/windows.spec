import os
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
import imageio_ffmpeg


project_root = Path(SPECPATH).parent
web_dist = Path(os.environ.get("WEB_DIST_PATH", project_root / "web" / "dist"))
modnet_model = project_root / "server" / "models" / "modnet_photographic.onnx"
app_icon = project_root / "deploy" / "assets" / "dandan-logo.ico"
app_logo = project_root / "deploy" / "assets" / "dandan-logo.png"

if not (web_dist / "index.html").is_file():
    raise SystemExit("web/dist is missing; run npm run build before PyInstaller")
if not modnet_model.is_file():
    raise SystemExit("MODNet model is missing; run server/scripts/download_models.py")
if not app_icon.is_file():
    raise SystemExit("Application icon is missing: deploy/assets/dandan-logo.ico")
if not app_logo.is_file():
    raise SystemExit("Application logo is missing: deploy/assets/dandan-logo.png")

rapidocr_datas = collect_data_files("rapidocr")
onnxruntime_binaries = collect_dynamic_libs("onnxruntime")
conda_runtime_binaries = []
ffmpeg_executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
if not ffmpeg_executable.is_file():
    raise SystemExit("imageio-ffmpeg executable is missing")
ffmpeg_binaries = [(str(ffmpeg_executable), "imageio_ffmpeg/binaries")]
for runtime_root in dict.fromkeys((Path(sys.prefix), Path(sys.base_prefix))):
    for runtime_name in (
        "libssl-3-x64.dll",
        "libcrypto-3-x64.dll",
        "liblzma.dll",
        "libbz2.dll",
        "libexpat.dll",
        "ffi.dll",
    ):
        runtime_path = runtime_root / "Library" / "bin" / runtime_name
        if runtime_path.is_file():
            conda_runtime_binaries.append((str(runtime_path), "."))

a = Analysis(
    [str(project_root / "server" / "desktop.py")],
    pathex=[str(project_root)],
    binaries=onnxruntime_binaries + conda_runtime_binaries + ffmpeg_binaries,
    datas=[
        (str(web_dist), "web/dist"),
        (str(modnet_model), "server/models"),
        (str(app_logo), "deploy/assets"),
        (str(project_root / "THIRD_PARTY_NOTICES.md"), "."),
    ] + rapidocr_datas,
    hiddenimports=collect_submodules("rapidocr")
    + collect_submodules("setuptools._vendor.backports")
    + [
        "onnxruntime.capi._pybind_state",
        "imageio_ffmpeg",
        "uvicorn.logging",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "pytest", "reportlab", "watchfiles", "websockets", "httptools",
        "uvloop", "winloop", "IPython", "matplotlib", "pandas", "torch", "paddle",
        "openvino", "gunicorn", "trio",
        "PIL.AvifImagePlugin", "PIL._avif", "lxml.objectify",
        "pypdfium2", "pypdfium2_raw",
    ],
    noarchive=False,
)

# OCR only uses OpenCV's image-processing APIs. Video conversion uses the
# separately bundled imageio-ffmpeg executable, so OpenCV's video DLL is unused.
# The API accepts JPG, PNG, and WebP only, so Pillow's AVIF binary is unused too.
a.binaries = [
    entry for entry in a.binaries
    if "opencv_videoio_ffmpeg" not in str(entry[0]).lower()
    and "_avif" not in str(entry[0]).lower()
    and "lxml\\objectify" not in str(entry[0]).lower()
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="蛋蛋小工具",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(app_icon),
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="蛋蛋小工具",
)
