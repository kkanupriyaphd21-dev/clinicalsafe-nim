#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Kill any existing instances
lsof -ti:8002 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true

sleep 1

# Backend
cd backend
if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate
mkdir -p data
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &
echo $! > backend.pid
disown

cd ..

# Wait for backend
for i in {1..30}; do
  if curl -s http://localhost:8002/health >/dev/null 2>&1; then
    echo "Backend ready on http://localhost:8002"
    break
  fi
  sleep 0.5
done

# Frontend
cd frontend
NIM_BACKEND_URL=http://localhost:8002 nohup npm start > frontend.log 2>&1 &
echo $! > frontend.pid
disown

echo "Frontend starting on http://localhost:3000"
echo "PIDs: backend $(cat ../backend/backend.pid), frontend $(cat frontend.pid)"
