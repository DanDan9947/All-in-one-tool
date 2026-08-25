param(
    [string]$CompilerPath = "",
    [string]$PortablePath = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $PSScriptRoot "windows-installer.iss"
$distDirectory = if ($OutputPath) {
    New-Item -ItemType Directory -Path $OutputPath -Force | Select-Object -ExpandProperty FullName
} else {
    Join-Path $projectRoot "dist"
}
$portableDirectory = if ($PortablePath) {
    Get-Item -LiteralPath $PortablePath -ErrorAction Stop
} else {
    Get-ChildItem -LiteralPath (Join-Path $projectRoot "dist") -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "_internal") } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}
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

& $CompilerPath "/DPortableSource=$($portableDirectory.FullName)" "/DInstallerOutputDir=$distDirectory" $installerScript
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
if ($installerOutput.Length -gt 125MB) {
    throw "Installer exceeds the 125 MB release size budget: $installerMb MB"
}

$installerOutput |
    Select-Object FullName, Length, LastWriteTime
