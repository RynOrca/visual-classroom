#!/usr/bin/env bash
# Stop V3 local dev stack
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W 2>/dev/null || pwd)"
cd "$ROOT"

for name in frontend worker api surreal; do
  if [ -f "logs/$name.pid" ]; then
    pid=$(cat "logs/$name.pid")
    if [ -n "$pid" ]; then
      echo "Stopping $name (PID $pid)"
      taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "logs/$name.pid"
  fi
done

# Fallback: kill any remaining surreal.exe (only our local binary name)
taskkill //F //IM surreal.exe >/dev/null 2>&1 || true

echo "Done."
