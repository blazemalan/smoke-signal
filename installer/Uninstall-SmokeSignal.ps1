# Smoke Signal Uninstaller
# Removes the conda environment, shortcuts, and optionally user data.

$ErrorActionPreference = "Stop"

$CONDA_ENV = "smoke-signal"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

# Find conda
$CONDA_EXE = ""
$condaPaths = @(
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
    "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe"
)
foreach ($p in $condaPaths) {
    if (Test-Path $p) { $CONDA_EXE = $p; break }
}

Write-Host ""
Write-Host "Smoke Signal Uninstaller" -ForegroundColor Yellow
Write-Host "========================" -ForegroundColor Yellow
Write-Host ""

# --- Remove conda environment ---

Write-Step "Removing conda environment"

if ($CONDA_EXE -and (& $CONDA_EXE env list 2>$null | Select-String "\b$CONDA_ENV\b")) {
    & $CONDA_EXE env remove -n $CONDA_ENV -y 2>&1 | Out-Null
    Write-Ok "Environment '$CONDA_ENV' removed"
} else {
    Write-Host "  Environment '$CONDA_ENV' not found (already removed or different conda)"
}

# --- Remove shortcuts ---

Write-Step "Removing shortcuts"

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Smoke Signal.lnk"
$startMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Smoke Signal.lnk"

if (Test-Path $desktopShortcut) {
    Remove-Item $desktopShortcut -Force
    Write-Ok "Desktop shortcut removed"
}
if (Test-Path $startMenuShortcut) {
    Remove-Item $startMenuShortcut -Force
    Write-Ok "Start Menu shortcut removed"
}

# --- Optionally remove user data ---

Write-Step "User data"

$dataDir = Join-Path $env:LOCALAPPDATA "SmokeSignal"
if (Test-Path $dataDir) {
    Write-Host "  Your transcripts, profiles, and config are in:"
    Write-Host "    $dataDir" -ForegroundColor White
    Write-Host ""
    $remove = Read-Host "  Delete user data? This cannot be undone. (y/n)"
    if ($remove -eq "y") {
        Remove-Item $dataDir -Recurse -Force
        Write-Ok "User data removed"
    } else {
        Write-Host "  User data kept."
    }
} else {
    Write-Host "  No user data found."
}

Write-Host ""
Write-Host "Uninstall complete." -ForegroundColor Green
Write-Host ""
