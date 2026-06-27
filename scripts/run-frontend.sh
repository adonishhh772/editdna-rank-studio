#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
cd "$(dirname "$0")/../frontend"
npm run dev
