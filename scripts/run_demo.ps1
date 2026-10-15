<#
.SYNOPSIS
    Run the NetMind synthetic demo and ask the Copilot about it.

.DESCRIPTION
    Needs scripts\setup_windows.ps1 to have been run once.

        powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
        powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Dashboard

    The demo uses generated (synthetic) traffic with congestion at 70-100 s, a port scan
    at 120-128 s and a ping flood at 150-158 s. Each run adds a new run to data\netmind.db.

.PARAMETER Dashboard
    Also open the dashboard in a new PowerShell window when the demo finishes.
#>
param([switch]$Dashboard)

$ErrorActionPreference = "Continue"   # native commands are checked via $LASTEXITCODE
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$VenvPy = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "ERROR: .venv not found. Run first:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "Running the synthetic demo..." -ForegroundColor Cyan
& $VenvPy -m netmind demo
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: the demo failed (see above)" -ForegroundColor Red; exit 1 }

foreach ($q in @("Why is the network slow?", "Is anyone attacking my network?")) {
    Write-Host "`n>>> Copilot: $q" -ForegroundColor Cyan
    & $VenvPy -m netmind ask $q
}

if ($Dashboard) {
    Write-Host "`nOpening the dashboard in a new window (http://localhost:8501)..." -ForegroundColor Cyan
    $script = Join-Path $Repo "scripts\run_dashboard.ps1"
    Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File `"$script`""
} else {
    Write-Host "`nTo open the dashboard (in a second terminal):" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_dashboard.ps1"
}
