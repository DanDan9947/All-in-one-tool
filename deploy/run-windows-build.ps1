param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [int]$WaitForProcessId = 0,
    [string]$TargetDirectory = "",
    [switch]$RestartService = $true
)

$ErrorActionPreference = "Stop"
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$buildScript = Join-Path $resolvedRoot "deploy\build-windows.ps1"
$installerScript = Join-Path $resolvedRoot "deploy\build-installer.ps1"
$logDirectory = Join-Path $resolvedRoot "logs"
$logPath = Join-Path $logDirectory "windows-build-latest.log"
$distDirectory = Join-Path $resolvedRoot "dist"

if (-not (Test-Path -LiteralPath $buildScript) -or -not (Test-Path -LiteralPath $installerScript)) {
    throw "Windows build scripts were not found under $resolvedRoot"
}
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -LiteralPath $logPath -Force
try {
    if ($WaitForProcessId -gt 0) {
        Write-Host "Waiting for application process $WaitForProcessId to exit..."
        Wait-Process -Id $WaitForProcessId -ErrorAction SilentlyContinue
    }
    Set-Location -LiteralPath $resolvedRoot

    Write-Host "=== Phase 1: Building Windows Portable Application and ZIP ==="
    & $buildScript -UseExistingEnvironment
    if ($LASTEXITCODE -ne 0) {
        throw "Portable Windows build failed with exit code $LASTEXITCODE"
    }

    Write-Host "=== Phase 2: Building Windows Installer (EXE) ==="
    & $installerScript
    if ($LASTEXITCODE -ne 0) {
        throw "Windows installer build failed with exit code $LASTEXITCODE"
    }

    Write-Host "Windows EXE and ZIP build completed successfully."

    # Copy to target directory if custom path was specified
    if ($TargetDirectory) {
        $resolvedTarget = $null
        if (Test-Path -LiteralPath $TargetDirectory) {
            $resolvedTarget = (Resolve-Path -LiteralPath $TargetDirectory).Path
        } else {
            $resolvedTarget = [System.IO.Path]::GetFullPath($TargetDirectory)
        }
        $resolvedDist = (Resolve-Path -LiteralPath $distDirectory).Path
        if ($resolvedDist -ne $resolvedTarget) {
            Write-Host "=== Phase 3: Copying Artifacts to Custom Target Directory: $TargetDirectory ==="
            New-Item -ItemType Directory -Path $TargetDirectory -Force | Out-Null
            $artifacts = @("DandanTools-Setup.exe", "DandanTools-windows-x64.zip")
            foreach ($artifact in $artifacts) {
                $sourceFile = Join-Path $distDirectory $artifact
                if (Test-Path -LiteralPath $sourceFile) {
                    Copy-Item -LiteralPath $sourceFile -Destination $TargetDirectory -Force
                    Write-Host "Copied $artifact to $TargetDirectory"
                }
            }
        }
    }

    Write-Host "=== Phase 4: Recording Build Status ==="
    $statusObj = @{
        status = "completed"
        completedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        targetDirectory = if ($TargetDirectory) { $TargetDirectory } else { $distDirectory }
        logPath = $logPath
    }
    $statusObj | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDirectory "build-status.json") -Encoding UTF8

    # Restart Windows service
    if ($RestartService) {
        Write-Host "=== Phase 5: Restarting Windows Service (DandanTools) ==="
        $service = Get-Service -Name "DandanTools" -ErrorAction SilentlyContinue
        if ($service) {
            Write-Host "Scheduling background restart for DandanTools service..."
            Start-Process powershell.exe -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Start-Sleep -Milliseconds 2000; Restart-Service -Name 'DandanTools' -Force"
            Write-Host "DandanTools service restart scheduled."
        } else {
            Write-Host "DandanTools service not registered; skipping service restart."
        }
    }

    Write-Host "=== All Build and Deployment Phases Completed Successfully ==="
} catch {
    $errObj = @{
        status = "failed"
        failedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        error = $_.Exception.Message
        logPath = $logPath
    }
    $errObj | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDirectory "build-status.json") -Encoding UTF8
    throw
} finally {
    Stop-Transcript
}
