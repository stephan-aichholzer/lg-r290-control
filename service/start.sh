#!/bin/bash
set -e

echo "=========================================="
echo "LG R290 Heat Pump Control Stack - Starting"
echo "=========================================="
echo ""

# Start monitor_and_keep_alive.py in background
echo "[1/2] Starting monitor daemon (keep-alive + status caching)..."
python3 /app/monitor_and_keep_alive.py > /app/monitor.log 2>&1 &
MONITOR_PID=$!
echo "✅ Monitor daemon started (PID: $MONITOR_PID)"
echo ""

# Wait for status.json to be created
echo "[2/2] Waiting for initial status.json..."
MAX_WAIT=30
ELAPSED=0
while [ ! -f /app/status.json ] && [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    echo -n "."
done
echo ""

if [ -f /app/status.json ]; then
    echo "✅ status.json created"
    echo ""
else
    echo "⚠️  Warning: status.json not created after ${MAX_WAIT}s"
    echo "   Service may not function correctly"
    echo ""
fi

# Start FastAPI service in foreground
echo "=========================================="
echo "Starting FastAPI service..."
echo "=========================================="
exec uvicorn main:app --host 0.0.0.0 --port 8000
