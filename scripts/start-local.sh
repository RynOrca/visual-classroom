#!/usr/bin/env bash
# Start V3 local dev stack: SurrealDB + API + Worker + Frontend
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W 2>/dev/null || pwd)"
cd "$ROOT"

mkdir -p logs data/surreal

echo "==> Starting SurrealDB (port 8000)"
if curl -s --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "    SurrealDB already running"
else
  nohup ./tools/surreal.exe start --no-banner --user root --pass root --bind 127.0.0.1:8000 --allow-all "rocksdb:data/surreal/mydatabase.db" > logs/surreal.log 2>&1 &
  echo $! > logs/surreal.pid
  sleep 2
  echo "    PID $(cat logs/surreal.pid)"
fi

echo "==> Starting API (port 5055)"
API_RELOAD=false nohup uv run --env-file .env run_api.py > logs/api.log 2>&1 &
echo $! > logs/api.pid
echo "    PID $(cat logs/api.pid)"

echo "==> Starting worker"
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 nohup uv run --env-file .env surreal-commands-worker --import-modules commands --max-tasks 5 > logs/worker.log 2>&1 &
echo $! > logs/worker.pid
echo "    PID $(cat logs/worker.pid)"

echo "==> Starting frontend (port 3000)"
(cd frontend && NEXT_TELEMETRY_DISABLED=1 nohup npm run dev > ../logs/frontend.log 2>&1 & echo $! > ../logs/frontend.pid)
echo "    PID $(cat logs/frontend.pid)"

echo ""
echo "Services:"
echo "  Frontend   http://localhost:3000"
echo "  API docs   http://localhost:5055/docs"
echo "  SurrealDB  http://127.0.0.1:8000"
echo "Logs in ./logs"
