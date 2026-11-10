#!/usr/bin/env bash
# Guided Wealth Orbit setup for macOS and Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. It will install Python 3.13 for this project."
  read -r -p "Install uv now? [Y/n] " install_uv
  install_uv="${install_uv:-Y}"
  if [[ ! "$install_uv" =~ ^[Yy] ]]; then
    echo "Install uv from https://docs.astral.sh/uv/ and run this script again."
    exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  if [[ -f "${HOME}/.local/bin/env" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.local/bin/env"
  fi
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20 or newer is required to build the UI."
  if command -v brew >/dev/null 2>&1; then
    echo "brew install node"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Install Node.js 20 or newer from https://nodejs.org/ (or use nvm / NodeSource)."
    echo "Do not use apt nodejs packages older than 20."
  else
    echo "Install Node.js 20 or newer from https://nodejs.org/"
  fi
  exit 1
fi

node_major="$(node -p "process.versions.node.split('.')[0]")"
if [[ "$node_major" -lt 20 ]]; then
  echo "Node.js 20 or newer is required. This machine has $(node -v)."
  echo "Install Node.js 20 or newer from https://nodejs.org/ (or use nvm / NodeSource)."
  exit 1
fi

uv python install 3.13
uv sync
exec uv run python scripts/setup_guide.py
