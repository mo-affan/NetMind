<#
.SYNOPSIS
    One-time NetMind setup on Windows: virtual environment, packages, tests.

.DESCRIPTION
    Run from anywhere; the script works in the repository folder that contains it.
    It does not change your execution policy and does not delete anything.

        powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1

    (-ExecutionPolicy Bypass applies to this one command only.)

    Steps:
      1. Checks the checkout is complete (netmind\__main__.py exists).
      2. Uses .venv if it already exists; otherwise creates it with the chosen Python.
      3. Installs requirements.txt (core) and requirements-dev.txt (pytest).
      4. Tries requirements-capture.txt (Scapy); a failure here is only a warning.
      5. Checks the imports and runs the tests.

.PARAMETER PythonVersion
    Python to create .venv with, via the py launcher, e.g. "3.13". Default: the first
    available of 3.13, 3.12, 3.14, then "python".

.PARAMETER Recreate
    Rename the existing .venv to .venv.bak-<timestamp> and create a fresh one.

.PARAMETER SkipTests
    Do not run the test suite at the end.

.PARAMETER SkipCapture
    Do not try to install Scapy.
#>
param(
    [string]$PythonVersion = "",
    [switch]$Recreate,
    [switch]$SkipTests,
    [switch]$SkipCapture
)

# "Continue", not "Stop": in Windows PowerShell 5.1, native programs that write to stderr
# (pip warnings, py probing a missing version) would otherwise abort the script. Every
# native call below checks $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
Write-Host "NetMind setup in $Repo" -ForegroundColor Cyan

function Fail($msg) {
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

# ---- 1. checkout is complete -------------------------------------------------
if (-not (Test-Path (Join-Path $Repo "netmind\__main__.py"))) {
    Fail ("netmind\__main__.py is missing: this checkout is out of date.`n" +
          "  Update it first:  git fetch origin   then   git merge --ff-only origin/main")
}

# ---- 2. virtual environment ----------------------------------------------------
$VenvPy = Join-Path $Repo ".venv\Scripts\python.exe"

if ($Recreate -and (Test-Path (Join-Path $Repo ".venv"))) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Rename-Item -Path (Join-Path $Repo ".venv") -NewName ".venv.bak-$stamp" -ErrorAction Stop
    Write-Host "Renamed the old .venv to .venv.bak-$stamp (delete it yourself when no longer needed)"
}

function Find-Python {
    param([string]$Wanted)
    $hasPy = $null -ne (Get-Command py -ErrorAction SilentlyContinue)
    if ($Wanted) {
        if (-not $hasPy) { Fail "the py launcher was not found, so -PythonVersion cannot be used" }
        & py "-$Wanted" -c "import sys" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "Python $Wanted is not installed (check with: py --list)" }
        return ,@("py", "-$Wanted")
    }
    if ($hasPy) {
        foreach ($v in @("3.13", "3.12", "3.14")) {
            & py "-$v" -c "import sys" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { return ,@("py", "-$v") }
        }
    }
    # the leading comma keeps a one-element array from being flattened into a string
    if (Get-Command python -ErrorAction SilentlyContinue) { return ,@("python") }
    Fail "no Python found. Install Python 3.13 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')."
}

if (Test-Path $VenvPy) {
    Write-Host "Using the existing virtual environment .venv"
} else {
    $py = Find-Python -Wanted $PythonVersion
    $exe = $py[0]
    $pyArgs = @()
    if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }
    Write-Host "Creating .venv with: $($py -join ' ')"
    & $exe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPy)) { Fail "could not create .venv" }
}

$ver = & $VenvPy -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
Write-Host "Python in .venv: $ver"
$minor = [int](& $VenvPy -c "import sys; print(sys.version_info[1])")
if ($minor -lt 10) { Fail "Python $ver is too old; use 3.12, 3.13 or 3.14 (see -PythonVersion)" }

# ---- 3. packages -------------------------------------------------------------------
Write-Host "`nInstalling packages (this can take a few minutes the first time)..." -ForegroundColor Cyan
& $VenvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed (check your internet connection)" }
& $VenvPy -m pip install -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) {
    Fail ("installing requirements failed with Python $ver.`n" +
          "  If the error mentions building a wheel or 'Microsoft Visual C++', a package has no`n" +
          "  ready-made wheel for this Python. Install Python 3.13 and run:`n" +
          "    powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 -PythonVersion 3.13 -Recreate")
}

if (-not $SkipCapture) {
    & $VenvPy -m pip install -r requirements-capture.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Scapy could not be installed. Live capture and pcap reading will not work;" -ForegroundColor Yellow
        Write-Host "         the demo, NS2 analysis, dashboard and API still work." -ForegroundColor Yellow
    }
}

# ---- 4. imports and tests --------------------------------------------------------
Write-Host "`nChecking imports..." -ForegroundColor Cyan
& $VenvPy -c "import netmind, numpy, pandas, sklearn, networkx, plotly, streamlit, fastapi, uvicorn; print('core imports OK, netmind', netmind.__version__)"
if ($LASTEXITCODE -ne 0) { Fail "a required package does not import (see the error above)" }
& $VenvPy -m netmind --help | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "python -m netmind --help failed" }

if (-not $SkipTests) {
    Write-Host "`nRunning tests..." -ForegroundColor Cyan
    & $VenvPy -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Some tests failed (see above). Please send the output." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\Activate.ps1                 (activate the environment in this terminal)"
Write-Host "  python -m netmind demo                        (synthetic demo)"
Write-Host "  python -m netmind dashboard                   (dashboard, in a second terminal)"
Write-Host "Or: powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1"
