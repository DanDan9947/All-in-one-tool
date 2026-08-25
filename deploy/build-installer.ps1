param(
    [string]$CompilerPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $PSScriptRoot "windows-installer.iss"
$distDirectory = Join-Path $projectRoot "dist"
$portableDirectory = Get-ChildItem -LiteralPath $distDirectory -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "_internal") } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$portableExecutable = $portableDirectory |
    ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -File -Filter "*.exe" } |
    Select-Object -First 1

if (-not $portableDirectory -or -not $portableExecutable) {
    throw "Portable application not found. Run deploy\build-windows.ps1 first."
}

if (-not $CompilerPath) {
    $compilerCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files\Inno Setup 7\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $CompilerPath = $compilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}

if (-not $CompilerPath -or -not (Test-Path -LiteralPath $CompilerPath)) {
    throw "ISCC.exe was not found. Install Inno Setup 7 or specify -CompilerPath."
}

& $CompilerPath $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

$installerOutput = Get-ChildItem -LiteralPath $distDirectory -File -Filter "*.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $installerOutput) {
    throw "Installer output was not found."
}

$installerMb = [math]::Round($installerOutput.Length / 1MB, 2)
if ($installerOutput.Length -gt 120MB) {
    throw "Installer exceeds the 120 MB release limit: $installerMb MB"
}

$installerOutput |
    Select-Object FullName, Length, LastWriteTime
