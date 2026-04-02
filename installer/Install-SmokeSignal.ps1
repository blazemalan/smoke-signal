# Smoke Signal Installer
# Downloads and installs everything needed to run Smoke Signal.

$ErrorActionPreference = "Stop"

$CONDA_ENV = "smoke-signal"
$PYTHON_VERSION = "3.12"
$PROJECT_DIR = (Resolve-Path "$PSScriptRoot\..").Path
$MINICONDA_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$MINICONDA_INSTALLER = "$env:TEMP\Miniconda3-installer.exe"

# --- Helpers ---

function Write-Step($msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "  [!] $msg" -ForegroundColor Yellow
}

function Write-Fail($msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# --- Step 1: GPU Detection ---

Write-Step "Checking GPU"

$GPU_NAME = ""
$CUDA_VERSION = ""
$HAS_GPU = $false

if (Test-Command "nvidia-smi") {
    try {
        $smiOutput = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0 -and $smiOutput) {
            $GPU_NAME = $smiOutput.Trim()
            $HAS_GPU = $true
            Write-Ok "Found GPU: $GPU_NAME"

            # Parse CUDA version from nvidia-smi header
            $header = & nvidia-smi 2>$null | Select-String "CUDA Version"
            if ($header -match "CUDA Version:\s+([\d.]+)") {
                $CUDA_VERSION = $Matches[1]
                Write-Ok "CUDA support: $CUDA_VERSION"
            }
        }
    } catch {
        Write-Warn "nvidia-smi found but failed to query GPU"
    }
}

if (-not $HAS_GPU) {
    Write-Warn "No NVIDIA GPU detected. Smoke Signal will run in CPU mode (very slow)."
    Write-Host "  For best performance, an NVIDIA GPU with 10+ GB VRAM is recommended."
    Write-Host ""
    $continue = Read-Host "  Continue with CPU-only install? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Installation cancelled."
        exit 0
    }
}

# Determine PyTorch index URL based on CUDA version
$TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
if ($HAS_GPU) {
    # Map driver CUDA version to best available PyTorch wheel
    $cudaMajor = [int]($CUDA_VERSION.Split('.')[0])
    $cudaMinor = [int]($CUDA_VERSION.Split('.')[1])

    if ($cudaMajor -ge 13 -or ($cudaMajor -eq 12 -and $cudaMinor -ge 8)) {
        $TORCH_INDEX = "https://download.pytorch.org/whl/cu128"
    } elseif ($cudaMajor -eq 12 -and $cudaMinor -ge 4) {
        $TORCH_INDEX = "https://download.pytorch.org/whl/cu124"
    } elseif ($cudaMajor -ge 12) {
        $TORCH_INDEX = "https://download.pytorch.org/whl/cu121"
    } else {
        Write-Warn "CUDA $CUDA_VERSION is older than expected. Trying cu121 wheels."
        $TORCH_INDEX = "https://download.pytorch.org/whl/cu121"
    }
    Write-Ok "Will install PyTorch with: $TORCH_INDEX"
}

# --- Step 2: Conda ---

Write-Step "Checking for Conda"

$CONDA_EXE = ""

# Check common conda locations
$condaPaths = @(
    "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
    "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
    "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
    "C:\miniconda3\Scripts\conda.exe",
    "C:\ProgramData\miniconda3\Scripts\conda.exe"
)

foreach ($p in $condaPaths) {
    if (Test-Path $p) {
        $CONDA_EXE = $p
        break
    }
}

if (-not $CONDA_EXE -and (Test-Command "conda")) {
    $CONDA_EXE = (Get-Command conda).Source
}

if ($CONDA_EXE) {
    Write-Ok "Found conda at: $CONDA_EXE"
} else {
    Write-Host "  Conda not found. Downloading Miniconda..."
    try {
        Invoke-WebRequest -Uri $MINICONDA_URL -OutFile $MINICONDA_INSTALLER -UseBasicParsing
        Write-Host "  Installing Miniconda (this takes a minute)..."
        Start-Process -FilePath $MINICONDA_INSTALLER -ArgumentList "/InstallationType=JustMe", "/AddToPath=0", "/RegisterPython=0", "/S", "/D=$env:USERPROFILE\miniconda3" -Wait -NoNewWindow
        $CONDA_EXE = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"

        if (Test-Path $CONDA_EXE) {
            Write-Ok "Miniconda installed"
        } else {
            Write-Fail "Miniconda installation failed"
            exit 1
        }
    } catch {
        Write-Fail "Failed to download/install Miniconda: $_"
        exit 1
    } finally {
        if (Test-Path $MINICONDA_INSTALLER) {
            Remove-Item $MINICONDA_INSTALLER -Force
        }
    }
}

# Get conda base directory for activation
$CONDA_BASE = Split-Path (Split-Path $CONDA_EXE)

# --- Step 3: Create Conda Environment ---

Write-Step "Setting up Python environment"

# Check if env already exists
$envList = & $CONDA_EXE env list 2>$null
if ($envList -match "\b$CONDA_ENV\b") {
    Write-Ok "Environment '$CONDA_ENV' already exists"
} else {
    Write-Host "  Creating conda environment with Python $PYTHON_VERSION (this takes a few minutes)..."
    & $CONDA_EXE create -n $CONDA_ENV python=$PYTHON_VERSION -y 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create conda environment"
        exit 1
    }
    Write-Ok "Environment '$CONDA_ENV' created"
}

# --- Step 4: Install ffmpeg ---

Write-Step "Checking for ffmpeg"

# Check if ffmpeg is available in the env
$ffmpegCheck = & $CONDA_EXE run -n $CONDA_ENV ffmpeg -version 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "ffmpeg already installed"
} else {
    Write-Host "  Installing ffmpeg..."
    & $CONDA_EXE install -n $CONDA_ENV ffmpeg -c conda-forge -y 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "conda ffmpeg install failed, checking system ffmpeg..."
        if (Test-Command "ffmpeg") {
            Write-Ok "System ffmpeg found"
        } else {
            Write-Warn "ffmpeg not installed. You may need to install it manually."
            Write-Host "  Download from: https://ffmpeg.org/download.html"
        }
    } else {
        Write-Ok "ffmpeg installed"
    }
}

# --- Step 5: Install PyTorch ---

Write-Step "Installing PyTorch"

Write-Host "  This is the largest download (~2-4 GB). Please be patient..."
& $CONDA_EXE run -n $CONDA_ENV pip install torch torchaudio --index-url $TORCH_INDEX 2>&1 | ForEach-Object {
    if ($_ -match "Successfully installed") { Write-Host "  $_" }
    elseif ($_ -match "already satisfied") { Write-Host "  $_" }
}
if ($LASTEXITCODE -ne 0) {
    Write-Fail "PyTorch installation failed"
    Write-Host "  Try manually: conda run -n $CONDA_ENV pip install torch torchaudio --index-url $TORCH_INDEX"
    exit 1
}
Write-Ok "PyTorch installed"

# --- Step 6: Install Smoke Signal ---

Write-Step "Installing Smoke Signal"

& $CONDA_EXE run -n $CONDA_ENV pip install -e "$PROJECT_DIR[watch]" 2>&1 | ForEach-Object {
    if ($_ -match "Successfully installed") { Write-Host "  $_" }
    elseif ($_ -match "already satisfied") { Write-Host "  $_" }
}
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Smoke Signal installation failed"
    exit 1
}
Write-Ok "Smoke Signal installed"

# --- Step 7: Create Desktop Shortcut ---

Write-Step "Creating desktop shortcut"

try {
    # Find the smoke-signal-tray executable in the conda env
    $envPath = & $CONDA_EXE run -n $CONDA_ENV python -c "import sys; print(sys.prefix)" 2>$null
    $trayExe = Join-Path $envPath.Trim() "Scripts\smoke-signal-tray.exe"

    if (Test-Path $trayExe) {
        $WshShell = New-Object -ComObject WScript.Shell
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $shortcutPath = Join-Path $desktopPath "Smoke Signal.lnk"
        $shortcut = $WshShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $trayExe
        $shortcut.WorkingDirectory = $PROJECT_DIR
        $shortcut.Description = "Smoke Signal — local audio transcription"
        $shortcut.Save()
        Write-Ok "Desktop shortcut created"

        # Also create Start Menu shortcut
        $startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
        $startShortcutPath = Join-Path $startMenuDir "Smoke Signal.lnk"
        $startShortcut = $WshShell.CreateShortcut($startShortcutPath)
        $startShortcut.TargetPath = $trayExe
        $startShortcut.WorkingDirectory = $PROJECT_DIR
        $startShortcut.Description = "Smoke Signal — local audio transcription"
        $startShortcut.Save()
        Write-Ok "Start Menu shortcut created"
    } else {
        Write-Warn "Could not find smoke-signal-tray.exe at: $trayExe"
        Write-Host "  You can run Smoke Signal manually: conda run -n $CONDA_ENV smoke-signal-tray"
    }
} catch {
    Write-Warn "Could not create shortcuts: $_"
}

# --- Step 8: Verify ---

Write-Step "Verifying installation"

& $CONDA_EXE run -n $CONDA_ENV smoke-signal verify 2>&1 | ForEach-Object { Write-Host "  $_" }

# --- Done ---

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Smoke Signal installed successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Double-click 'Smoke Signal' on your desktop"
Write-Host "    2. Follow the setup wizard to connect your HuggingFace account"
Write-Host "    3. Pick the folder where your recordings appear"
Write-Host ""
Write-Host "  The first transcription will download AI models (~1.75 GB)."
Write-Host ""
