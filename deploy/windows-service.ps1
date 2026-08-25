param(
    [ValidateSet("Install", "Uninstall", "Start", "Stop", "Restart", "Status")]
    [string]$Action = "Install",
    [string]$ServiceName = "DandanTools",
    [string]$DisplayName = "Dandan Tools Service",
    [string]$NssmPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$startupBat = Join-Path $projectRoot "system.bat"
$logDirectory = Join-Path $projectRoot "logs"

function Resolve-Nssm {
    if ($script:NssmPath -and (Test-Path -LiteralPath $script:NssmPath)) {
        return (Resolve-Path -LiteralPath $script:NssmPath).Path
    }

    $localCandidates = @(
        (Join-Path $PSScriptRoot "nssm.exe"),
        "C:\tools\nssm\nssm.exe",
        "C:\ProgramData\chocolatey\bin\nssm.exe"
    )
    foreach ($candidate in $localCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "nssm.exe was not found. Put it at deploy\nssm.exe or pass -NssmPath C:\path\nssm.exe."
}

function Invoke-Nssm([string[]]$Arguments) {
    $nssm = Resolve-Nssm
    & $nssm @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $startupBat)) {
    throw "Startup script not found: $startupBat"
}

switch ($Action) {
    "Install" {
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
        $commandProcessor = Join-Path $env:SystemRoot "System32\cmd.exe"
        $parameters = "/d /s /c `"`"$startupBat`"`""

        Invoke-Nssm @("install", $ServiceName, $commandProcessor, $parameters)
        Invoke-Nssm @("set", $ServiceName, "DisplayName", $DisplayName)
        Invoke-Nssm @("set", $ServiceName, "Description", "FastAPI and web service on TCP port 9902")
        Invoke-Nssm @("set", $ServiceName, "AppDirectory", $projectRoot)
        Invoke-Nssm @("set", $ServiceName, "Start", "SERVICE_AUTO_START")
        Invoke-Nssm @("set", $ServiceName, "AppExit", "Default", "Restart")
        Invoke-Nssm @("set", $ServiceName, "AppRestartDelay", "5000")
        Invoke-Nssm @("set", $ServiceName, "AppStdout", (Join-Path $logDirectory "service.log"))
        Invoke-Nssm @("set", $ServiceName, "AppStderr", (Join-Path $logDirectory "service-error.log"))
        Invoke-Nssm @("set", $ServiceName, "AppRotateFiles", "1")
        Invoke-Nssm @("set", $ServiceName, "AppRotateBytes", "10485760")
        Invoke-Nssm @("start", $ServiceName)
        Write-Host "Service installed and started: $ServiceName (port 9902)"
    }
    "Uninstall" {
        Invoke-Nssm @("stop", $ServiceName)
        Invoke-Nssm @("remove", $ServiceName, "confirm")
        Write-Host "Service removed: $ServiceName"
    }
    "Start" { Invoke-Nssm @("start", $ServiceName) }
    "Stop" { Invoke-Nssm @("stop", $ServiceName) }
    "Restart" { Invoke-Nssm @("restart", $ServiceName) }
    "Status" { Invoke-Nssm @("status", $ServiceName) }
}
