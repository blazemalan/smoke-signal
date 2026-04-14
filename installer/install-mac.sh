#!/bin/bash
# Smoke Signal Installer for macOS
# Downloads and installs everything needed to run Smoke Signal.

set -e

CONDA_ENV="scribe"
PYTHON_VERSION="3.12"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Helpers ---

step()  { echo ""; echo "=== $1 ==="; }
ok()    { echo "  [OK] $1"; }
warn()  { echo "  [!] $1"; }
fail()  { echo "  [FAIL] $1"; exit 1; }

command_exists() { command -v "$1" &>/dev/null; }

# --- Step 1: Check Architecture ---

step "Checking system"

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ok "Apple Silicon detected (MPS GPU acceleration available)"
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
elif [ "$ARCH" = "x86_64" ]; then
    warn "Intel Mac detected — transcription will run on CPU (slower)"
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
else
    fail "Unsupported architecture: $ARCH"
fi

# --- Step 2: Homebrew + ffmpeg ---

step "Checking for Homebrew and ffmpeg"

if command_exists brew; then
    ok "Homebrew found"
else
    echo "  Homebrew not found. It's needed to install ffmpeg."
    read -p "  Install Homebrew? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add brew to PATH for Apple Silicon
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        ok "Homebrew installed"
    else
        warn "Skipping Homebrew. You'll need to install ffmpeg manually."
    fi
fi

if command_exists ffmpeg; then
    ok "ffmpeg already installed"
elif command_exists brew; then
    echo "  Installing ffmpeg..."
    brew install ffmpeg
    ok "ffmpeg installed"
else
    warn "ffmpeg not installed. Install it with: brew install ffmpeg"
fi

# --- Step 3: Conda ---

step "Checking for Conda"

CONDA_EXE=""

# Check common conda locations
for p in \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda" \
    "$HOME/miniforge3/bin/conda" \
    "/opt/homebrew/Caskroom/miniconda/base/bin/conda" \
    "/usr/local/Caskroom/miniconda/base/bin/conda"; do
    if [ -x "$p" ]; then
        CONDA_EXE="$p"
        break
    fi
done

if [ -z "$CONDA_EXE" ] && command_exists conda; then
    CONDA_EXE="$(command -v conda)"
fi

if [ -n "$CONDA_EXE" ]; then
    ok "Found conda at: $CONDA_EXE"
else
    echo "  Conda not found. Downloading Miniconda..."
    INSTALLER="/tmp/Miniconda3-installer.sh"
    curl -fsSL "$MINICONDA_URL" -o "$INSTALLER"
    bash "$INSTALLER" -b -p "$HOME/miniconda3"
    rm -f "$INSTALLER"
    CONDA_EXE="$HOME/miniconda3/bin/conda"

    if [ -x "$CONDA_EXE" ]; then
        ok "Miniconda installed"
        # Initialize conda for the current shell
        eval "$($CONDA_EXE shell.bash hook)"
    else
        fail "Miniconda installation failed"
    fi
fi

# --- Step 4: Create Conda Environment ---

step "Setting up Python environment"

if $CONDA_EXE env list 2>/dev/null | grep -qw "$CONDA_ENV"; then
    ok "Environment '$CONDA_ENV' already exists"
else
    echo "  Creating conda environment with Python $PYTHON_VERSION (this takes a few minutes)..."
    $CONDA_EXE create -n "$CONDA_ENV" python="$PYTHON_VERSION" -y > /dev/null 2>&1
    ok "Environment '$CONDA_ENV' created"
fi

# --- Step 5: Install PyTorch ---

step "Installing PyTorch"

echo "  This may take a few minutes..."
$CONDA_EXE run -n "$CONDA_ENV" pip install torch torchaudio 2>&1 | tail -1
ok "PyTorch installed"

# --- Step 6: Install Smoke Signal ---

step "Installing Smoke Signal"

$CONDA_EXE run -n "$CONDA_ENV" pip install -e "$PROJECT_DIR[watch]" 2>&1 | tail -1
ok "Smoke Signal installed"

# --- Step 7: Verify ---

step "Verifying installation"

$CONDA_EXE run -n "$CONDA_ENV" smoke-signal verify 2>&1 | while read -r line; do
    echo "  $line"
done

# --- Done ---

echo ""
echo "============================================"
echo "  Smoke Signal installed successfully!"
echo "============================================"
echo ""
echo "  Next steps:"
echo "    1. Run: $CONDA_EXE run -n $CONDA_ENV smoke-signal setup"
echo "       (Opens the setup wizard to configure your watch folder)"
echo ""
echo "    2. Run: $CONDA_EXE run -n $CONDA_ENV smoke-signal-tray"
echo "       (Starts the system tray app)"
echo ""
echo "  The first transcription will download AI models (~1.75 GB)."
echo ""
if [ "$ARCH" = "arm64" ]; then
    echo "  Tip: Apple Silicon will use MPS acceleration by default."
    echo "  If you hit issues, set 'device: cpu' in config.yaml to use CPU instead."
    echo ""
fi
