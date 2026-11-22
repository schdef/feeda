#!/bin/bash

# Feeda Termux Status Script
PIDFILE="$HOME/.feeda.pid"
LOGFILE="$HOME/feeda.log"
PORT="${FEEDA_PORT:-8000}"

RUNNING=0
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        RUNNING=1
    fi
fi

if [ "$RUNNING" -eq 0 ] && pgrep -f 'python -m feeda' >/dev/null 2>&1; then
    RUNNING=1
    PID=$(pgrep -f 'python -m feeda' | head -n 1)
fi

echo "========================================"
echo " Feeda Service Status"
echo "========================================"

if [ "$RUNNING" -eq 1 ]; then
    echo "Status: RUNNING (PID: $PID)"
    # Health check
    if command -v curl >/dev/null 2>&1; then
        HEALTH=$(curl -s "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)
        if [ -n "$HEALTH" ]; then
            echo "API Health: OK ($HEALTH)"
        else
            echo "API Health: Port $PORT not responding yet"
        fi
    fi
else
    echo "Status: STOPPED"
fi

if [ -f "$LOGFILE" ]; then
    echo "----------------------------------------"
    echo "Recent Logs (last 10 lines of $LOGFILE):"
    echo "----------------------------------------"
    tail -n 10 "$LOGFILE"
fi
echo "========================================"
