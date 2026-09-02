#!/usr/bin/env bash
# Quick local setup for AI Executive Assistant (macOS/Linux).
#
# Installs backend + mobile dependencies, starts PostgreSQL (via Docker if
# available), applies migrations, and seeds sample data. Does NOT start the
# backend or Expo dev servers themselves — those are interactive/foreground
# processes, so the script prints the exact commands to run them at the end.
#
# Windows: see README.md's "Windows (PowerShell) equivalents" section instead.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
MOBILE_DIR="$ROOT_DIR/mobile"

command_exists() { command -v "$1" >/dev/null 2>&1; }
docker_available() { command_exists docker && docker info >/dev/null 2>&1; }

echo "== AI Executive Assistant: quick local setup =="

missing=()
command_exists python3 || missing+=("python3 (3.12+)")
command_exists node || missing+=("node (18+)")
command_exists npm || missing+=("npm")
if ! docker_available && ! command_exists psql; then
  missing+=("a running Docker daemon (recommended) or a local PostgreSQL 16 install")
fi
if [ ${#missing[@]} -ne 0 ]; then
  echo "Missing prerequisites:"
  printf '  - %s\n' "${missing[@]}"
  exit 1
fi

echo
echo "-- Backend --"
cd "$BACKEND_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example"
fi

if docker_available; then
  echo "Starting PostgreSQL via docker compose..."
  docker compose up -d
  echo "Waiting for PostgreSQL to accept connections..."
  for _ in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
else
  echo "Docker (daemon) not available — assuming a local PostgreSQL 16 is"
  echo "already running and matches backend/.env. If this is the first run,"
  echo "create the test database once with: createdb ai_executive_assistant_test"
fi

echo "Applying migrations..."
alembic upgrade head

echo "Seeding sample data..."
python -m scripts.seed || echo "(database already has data — skipping seed, this is expected on a re-run)"

deactivate

echo
echo "-- Mobile --"
cd "$MOBILE_DIR"
npm install

cat <<'EOF'

== Setup complete ==

Start the backend (in one terminal):
  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
  -> http://localhost:8000  (interactive docs at /docs)

Start the mobile app (in another terminal):
  cd mobile && npx expo start
  -> press "a" for the Android emulator, "i" for the iOS simulator, or scan
     the QR code with Expo Go on a physical device

Testing on a physical phone? It can't reach your computer's localhost:
  1. Find your computer's LAN IP (e.g. 192.168.1.42)
  2. cd backend && uvicorn app.main:app --reload --host 0.0.0.0
  3. cd mobile && EXPO_PUBLIC_API_URL=http://192.168.1.42:8000/api/v1 npx expo start
  (phone and computer must be on the same Wi-Fi network)
EOF
