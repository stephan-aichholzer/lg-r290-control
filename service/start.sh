#!/bin/bash
set -e

echo "=========================================="
echo "LG R290 Heat Pump Control Stack - Starting"
echo "=========================================="
echo ""

# Create initial status.json for healthcheck
echo "[1/3] Creating initial status file..."
cat > /app/status.json <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "power_state": "UNKNOWN",
  "operating_mode": 0,
  "target_temp": 0.0,
  "flow_temp": 0.0,
  "return_temp": 0.0,
  "outdoor_temp": 0.0,
  "error_code": 0,
  "status": "starting"
}
EOF
echo "✅ Initial status file created"
echo ""

# Start monitor_and_keep_alive.py in background
echo "[2/3] Starting monitor daemon (keep-alive + status caching)..."
python3 /app/monitor_and_keep_alive.py &
MONITOR_PID=$!
echo "✅ Monitor daemon started (PID: $MONITOR_PID)"
echo "   Logs: /app/monitor.log (clean data) and /app/error.log (errors)"
echo ""

# Wait for status.json to be updated by monitor daemon
echo "[3/3] Waiting for monitor to update status.json..."
MAX_WAIT=30
ELAPSED=0
while [ ! -f /app/status.json ] && [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    echo -n "."
done
echo ""

if [ -f /app/status.json ]; then
    # Check if it was updated by monitor (not just our initial file)
    FILE_AGE=$(( $(date +%s) - $(stat -c %Y /app/status.json) ))
    if [ $FILE_AGE -lt 20 ]; then
        echo "✅ Monitor daemon is updating status.json"
    else
        echo "⚠️  Warning: status.json not updated by monitor after ${MAX_WAIT}s"
        echo "   Service may not function correctly"
    fi
    echo ""
else
    echo "⚠️  Warning: status.json disappeared"
    echo ""
fi

# Start FastAPI service in background
echo "=========================================="
echo "Starting FastAPI service..."
echo "=========================================="
uvicorn main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!
echo "✅ FastAPI started (PID: $UVICORN_PID)"
echo ""

# Monitor loop - exit container if monitor daemon dies
echo "=========================================="
echo "Entering supervision mode"
echo "Monitoring status.json freshness every 30s"
echo "Container will exit if file becomes stale (>60s)"
echo "=========================================="
echo ""

while true; do
    sleep 30

    # Check if status.json exists and is fresh
    if [ -f /app/status.json ]; then
        FILE_AGE=$(( $(date +%s) - $(stat -c %Y /app/status.json) ))

        if [ $FILE_AGE -gt 60 ]; then
            echo "❌ CRITICAL: status.json is stale (${FILE_AGE}s old)"
            echo "❌ Monitor daemon has crashed - exiting container for restart"
            exit 1
        fi
    else
        echo "❌ CRITICAL: status.json missing - exiting container for restart"
        exit 1
    fi
done
