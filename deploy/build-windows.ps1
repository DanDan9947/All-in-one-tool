param(
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonExecutable) {
    $condaPython = Join-Path $env:USERPROFILE ".conda\envs\wechat-image-tools\python.exe"
    if (Test-Path -LiteralPath $condaPython) {
        $PythonExecutable = $condaPython
    } else {
        $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
    }
}

$pythonVersion = & $PythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pythonVersion -ne "3.11") {
    throw "Windows build requires Python 3.11; found $pythonVersion"
}

$buildEnvironment = Join-Path $projectRoot "build\windows-venv"
& $PythonExecutable -m venv --clear $buildEnvironment
$buildPython = Join-Path $buildEnvironment "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $buildPython)) {
    throw "Unable to create the clean Windows build environment."
}
$pipOptions = @("--disable-pip-version-check", "--prefer-binary", "--timeout", "30", "--retries", "2")
& $buildPython -m pip install @pipOptions -r (Join-Path $projectRoot "server\requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Unable to install locked Windows build dependencies. Check the package index or proxy."
}
& $buildPython -m pip install @pipOptions -r (Join-Path $projectRoot "server\requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Unable to install locked Windows test dependencies. Check the package index or proxy."
}

$opencvVariants = & $buildPython -c "import importlib.metadata as m; print(','.join(sorted(d.metadata['Name'] for d in m.distributions() if d.metadata['Name'].lower() in {'opencv-python','opencv-python-headless'})))"
if ($opencvVariants -match ",") {
    throw "Multiple OpenCV variants detected in clean build environment: $opencvVariants"
}

$nodeVersion = & node --version
$nodeMajor = [int]($nodeVersion.TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 22) {
    throw "Windows build requires Node.js 22 or newer; found $nodeVersion"
}

$webSource = Join-Path $projectRoot "web"
$webBuildRoot = Join-Path $projectRoot "build\web-build"
if (Test-Path -LiteralPath $webBuildRoot) {
    Remove-Item -LiteralPath $webBuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $webBuildRoot | Out-Null
Copy-Item -LiteralPath @(
    (Join-Path $webSource "package.json"),
    (Join-Path $webSource "package-lock.json"),
    (Join-Path $webSource "tsconfig.json"),
    (Join-Path $webSource "vite.config.ts"),
    (Join-Path $webSource "index.html")
) -Destination $webBuildRoot
Copy-Item -LiteralPath (Join-Path $webSource "src") -Destination $webBuildRoot -Recurse
$webPublic = Join-Path $webSource "public"
if (Test-Path -LiteralPath $webPublic) {
    Copy-Item -LiteralPath $webPublic -Destination $webBuildRoot -Recurse
}

Push-Location $webBuildRoot
try {
    & npm.cmd ci
    & npm.cmd test
    & npm.cmd run build
} finally {
    Pop-Location
}
$env:WEB_DIST_PATH = Join-Path $webBuildRoot "dist"

& $buildPython -m pytest (Join-Path $projectRoot "server\tests") -q

$ffmpegExecutable = & $buildPython -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
$ffmpegEncoders = & $ffmpegExecutable -hide_banner -encoders 2>&1
if (-not ($ffmpegEncoders -match "libx264") -or -not ($ffmpegEncoders -match "\saac\s")) {
    throw "Bundled FFmpeg must provide libx264 and AAC encoders"
}

$modelPath = Join-Path $projectRoot "server\models\modnet_photographic.onnx"
if (-not (Test-Path -LiteralPath $modelPath)) {
    & $buildPython (Join-Path $projectRoot "server\scripts\download_models.py")
}

Push-Location $projectRoot
try {
    & $buildPython -m PyInstaller --noconfirm --clean `
        --distpath (Join-Path $projectRoot "dist") `
        --workpath (Join-Path $projectRoot "build\pyinstaller") `
        (Join-Path $projectRoot "deploy\windows.spec")
} finally {
    Pop-Location
}

$outputDirectory = Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "_internal") } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $outputDirectory) {
    throw "PyInstaller portable output was not found."
}
$portableFiles = @(Get-ChildItem -LiteralPath $outputDirectory -Recurse -File)
$portableBytes = ($portableFiles | Measure-Object Length -Sum).Sum
$portableMb = [math]::Round($portableBytes / 1MB, 2)
Write-Host "Portable application size: $portableMb MB ($($portableFiles.Count) files)"
Get-ChildItem -LiteralPath $outputDirectory -Recurse -File |
    Sort-Object Length -Descending |
    Select-Object -First 20 FullName, @{Name="SizeMB"; Expression={[math]::Round($_.Length / 1MB, 2)}} |
    Format-Table -AutoSize
if ($portableBytes -gt 385MB) {
    throw "Portable application exceeds the 385 MB release limit: $portableMb MB"
}
$archiveName = (Split-Path -Leaf $outputDirectory) + "-windows-x64.zip"
$archivePath = Join-Path (Join-Path $projectRoot "dist") $archiveName
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
Compress-Archive -Path (Join-Path $outputDirectory "*") -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host "Windows portable app: $outputDirectory"
Write-Host "Distribution archive: $archivePath"
