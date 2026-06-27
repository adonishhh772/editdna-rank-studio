#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BACKEND_DIR}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"

cd "${BACKEND_DIR}"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Backend venv not found. Run: ./scripts/setup_venv.sh" >&2
  exit 1
fi

exec "${VENV_PYTHON}" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
