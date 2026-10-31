#!/bin/bash
set -e

# Feeda Deploy Helper Script
# Builds frontend, creates a release package, and optionally transfers it to Termux.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_HOST="${1:-${TERMUX_HOST:-}}"
TARGET_PORT="${2:-8022}"

echo "=== Building Feeda Production Release ==="

# 1. Build frontend
echo "Building frontend..."
cd "$REPO_ROOT/frontend"
npm install
npm run build

# 2. Package release bundle
cd "$REPO_ROOT"
TMP_DIR="$(mktemp -d)"
PACKAGE_FILE="$TMP_DIR/feeda-deploy.tar.gz"

echo "Packaging release files..."
tar --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='*.db*' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='.git' \
    -czf "$PACKAGE_FILE" \
    backend \
    frontend/dist \
    scripts \
    backup \
    start.sh \
    .env.example \
    README.md

echo "Release package created at: $PACKAGE_FILE ($(du -h "$PACKAGE_FILE" | cut -f1))"

if [ -n "$TARGET_HOST" ]; then
    echo "=== Deploying to Termux device: $TARGET_HOST:$TARGET_PORT ==="
    scp -P "$TARGET_PORT" "$PACKAGE_FILE" "$TARGET_HOST:~/feeda-deploy.tar.gz"
    ssh -p "$TARGET_PORT" "$TARGET_HOST" 'bash -s' << 'REMOTE_SCRIPT'
        mkdir -p ~/feeda-tmp
        tar -xzf ~/feeda-deploy.tar.gz -C ~/feeda-tmp
        
        # If running inside proot-distro debian
        if command -v proot-distro >/dev/null 2>&1; then
            proot-distro login debian -- bash -c "
                mkdir -p /root/feeda
                cp -r /data/data/com.termux/files/home/feeda-tmp/* /root/feeda/
            "
        fi
        
        rm -rf ~/feeda-tmp ~/feeda-deploy.tar.gz
        
        # Restart service if start/stop scripts exist
        if [ -f ~/stop_feeda.sh ] && [ -f ~/start_feeda.sh ]; then
            ~/stop_feeda.sh
            sleep 1
            ~/start_feeda.sh
        fi
REMOTE_SCRIPT
    echo "Deployment to $TARGET_HOST finished successfully!"
else
    echo "Note: No target host specified. Usage: ./deploy.sh [user@phone_ip] [ssh_port]"
    echo "To deploy manually, copy $PACKAGE_FILE to your Termux device and extract."
fi

rm -rf "$TMP_DIR"
