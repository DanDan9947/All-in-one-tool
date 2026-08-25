@echo off
setlocal EnableExtensions

cd /d "%~dp0"

rem Server settings. Environment variables supplied by the service can override
rem these values, except for the requested fixed listen port.
if not defined APP_ENV set "APP_ENV=production"
if not defined APP_HOST set "APP_HOST=0.0.0.0"
set "APP_PORT=9902"
set "UVICORN_RELOAD=0"

set "PYTHON_EXE="
for %%P in (
    "%~dp0.venv\Scripts\python.exe"
    "C:\ProgramData\anaconda3\envs\wechat-image-tools\python.exe"
    "%USERPROFILE%\.conda\envs\wechat-image-tools\python.exe"
) do (
    if not defined PYTHON_EXE if exist "%%~P" set "PYTHON_EXE=%%~P"
)

if not defined PYTHON_EXE (
    echo [ERROR] No project Python environment was found.
    echo Create .venv and install server\requirements.txt first.
    exit /b 2
)

"%PYTHON_EXE%" -c "import fastapi, uvicorn, onnxruntime, rapidocr" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The Python environment is incomplete: %PYTHON_EXE%
    echo Install dependencies from server\requirements.txt.
    exit /b 3
)

echo Starting Dandan Tools on http://%APP_HOST%:%APP_PORT%/
"%PYTHON_EXE%" -m uvicorn server.app.main:app --host "%APP_HOST%" --port "%APP_PORT%" --no-access-log
exit /b %ERRORLEVEL%
