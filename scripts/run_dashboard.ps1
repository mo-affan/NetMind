<#
.SYNOPSIS
    Start the NetMind dashboard (Streamlit) on http://localhost:8501. Ctrl+C stops it.

        powershell -ExecutionPolicy Bypass -File scripts\run_dashboard.ps1
        powershell -ExecutionPolicy Bypass -File scripts\run_dashboard.ps1 -Port 8502
#>
param([int]$Port = 8501)

$ErrorActionPreference = "Continue"   # native commands are checked via $LASTEXITCODE
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$VenvPy = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "ERROR: .venv not found. Run first:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1" -ForegroundColor Red
    exit 1
}
& $VenvPy -m netmind dashboard --port $Port
