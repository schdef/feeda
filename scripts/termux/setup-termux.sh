#!/bin/bash
set -e

# Feeda Termux Setup Script (Proot Debian & Native)
echo "=== Setting up Feeda on Android / Termux ==="

# 1. Update Termux packages
echo "[1/5] Updating Termux packages..."
pkg update -y && pkg upgrade -y
pkg install -y proot-distro git curl nodejs-lts

# 2. Setup proot-distro Debian (recommended for reliable SQLite, C-extensions, and Python packages)
echo "[2/5] Setting up Debian environment in proot-distro..."
if ! proot-distro list | grep -q "debian.*installed"; then
    proot-distro install debian
fi

# 3. Provision Debian environment
echo "[3/5] Installing dependencies inside Debian..."
proot-distro login debian -- bash -c "
    apt update && apt install -y python3 python3-pip python3-venv git curl build-essential
"

# 4. Clone or link repo into Debian
echo "[4/5] Preparing Feeda workspace..."
proot-distro login debian -- bash -c "
    mkdir -p /root/feeda
"

# 5. Build frontend and prepare virtualenv
echo "[5/5] Building frontend and installing backend dependencies..."
if [ -d "frontend" ]; then
    cd frontend
    npm install
    npm run build
    cd ..
fi

proot-distro login debian -- bash -c "
    cd /root/feeda
    python3 -m venv .venv
    if [ -f backend/requirements.txt ]; then
        .venv/bin/pip install --upgrade pip
        .venv/bin/pip install -r backend/requirements.txt
    fi
"

# Symlink management scripts to Termux home for easy execution
mkdir -p "$HOME/bin"
cp "$(dirname "$0")/start_feeda.sh" "$HOME/start_feeda.sh"
cp "$(dirname "$0")/stop_feeda.sh" "$HOME/stop_feeda.sh"
cp "$(dirname "$0")/status_feeda.sh" "$HOME/status_feeda.sh"
chmod +x "$HOME/start_feeda.sh" "$HOME/stop_feeda.sh" "$HOME/status_feeda.sh"

echo "=== Termux Setup Complete! ==="
echo "You can now control Feeda with:"
echo "  ~/start_feeda.sh"
echo "  ~/status_feeda.sh"
echo "  ~/stop_feeda.sh"
