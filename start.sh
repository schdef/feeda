#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR/backend"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python -m feeda
