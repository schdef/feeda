#!/bin/bash
set -e

# Feeda Termux Start Script
PIDFILE="$HOME/.feeda.pid"
LOGFILE="$HOME/feeda.log"

# Prevent Android from sleeping the CPU
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

# Check if already running
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Feeda is already running with PID $PID."
        exit 0
    else
        rm -f "$PIDFILE"
    fi
fi

# Also check for running process
if pgrep -f 'python -m feeda' >/dev/null 2>&1; then
    echo "Feeda process already detected running."
    exit 0
fi

echo "Starting Feeda server..."

# Detect whether running via proot-distro debian or native termux
if command -v proot-distro >/dev/null 2>&1 && proot-distro list | grep -q "debian.*installed"; then
    echo "Running inside proot-distro debian..."
    nohup proot-distro login debian -- bash -c "
        cd /root/feeda/backend && \
        export FEEDA_PORT=\${FEEDA_PORT:-8000} && \
        export FEEDA_HOST=\${FEEDA_HOST:-0.0.0.0} && \
        if [ -f /root/feeda/.venv/bin/python ]; then
            exec /root/feeda/.venv/bin/python -m feeda
        else
            exec python3 -m feeda
        fi
    " >> "$LOGFILE" 2>&1 &
    PID=$!
else
    echo "Running in native environment..."
    BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    cd "$BASE_DIR/backend"
    export FEEDA_PORT="${FEEDA_PORT:-8000}"
    export FEEDA_HOST="${FEEDA_HOST:-0.0.0.0}"
    if [ -f "$BASE_DIR/backend/.venv/bin/python" ]; then
        nohup "$BASE_DIR/backend/.venv/bin/python" -m feeda >> "$LOGFILE" 2>&1 &
    else
        nohup python3 -m feeda >> "$LOGFILE" 2>&1 &
    fi
    PID=$!
fi

echo "$PID" > "$PIDFILE"
echo "Feeda started with PID $PID. Logs: $LOGFILE"

# Wait a brief moment and verify it's up
sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "Feeda is running healthy! Access UI at http://<phone-ip>:${FEEDA_PORT:-8000}"
else
    echo "Warning: Feeda process exited early. Last 10 log lines:"
    tail -n 10 "$LOGFILE"
    exit 1
fi
