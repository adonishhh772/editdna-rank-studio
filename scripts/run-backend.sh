#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"

cd "$ROOT/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
