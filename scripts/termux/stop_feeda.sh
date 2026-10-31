#!/bin/bash

# Feeda Termux Stop Script
PIDFILE="$HOME/.feeda.pid"

echo "Stopping Feeda..."

STOPPED=0

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Sending SIGTERM to Feeda PID $PID..."
        kill "$PID" 2>/dev/null || true
        # Wait up to 5 seconds
        for i in {1..5}; do
            if ! kill -0 "$PID" 2>/dev/null; then
                STOPPED=1
                break
            fi
            sleep 1
        done
        if [ "$STOPPED" -eq 0 ]; then
            echo "Force killing PID $PID..."
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f "$PIDFILE"
fi

# Clean up any lingering python feeda processes inside proot or host
pkill -f 'python -m feeda' 2>/dev/null || true

# Release wake lock if available
if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock
fi

echo "Feeda has been stopped."
