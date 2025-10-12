#!/bin/bash
# Monitor Scheduler Activity
# Shows scheduler logs, status, and current configuration

set -e

CONTAINER="lg_r290_service"
API_URL="http://localhost:8002"

echo "=========================================="
echo "  SCHEDULER MONITOR"
echo "=========================================="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container ${CONTAINER} is not running"
    exit 1
fi

# Get scheduler status
echo "📊 SCHEDULER STATUS"
echo "------------------------------------------"
curl -s ${API_URL}/schedule | jq '.' 2>/dev/null || echo "❌ Failed to fetch scheduler status"
echo ""

# Get current thermostat status
echo "🌡️  CURRENT THERMOSTAT STATUS"
echo "------------------------------------------"
THERMOSTAT_URL="http://192.168.2.11:8001"
curl -s ${THERMOSTAT_URL}/api/v1/thermostat/status 2>/dev/null | jq '{
  mode: .config.mode,
  target_temp: .config.target_temp,
  indoor_temp: .all_temps.temp_indoor,
  outdoor_temp: .all_temps.temp_outdoor,
  pump_running: .switch_state
}' || echo "❌ Failed to fetch thermostat status"
echo ""

# Show recent scheduler logs
echo "📜 RECENT SCHEDULER LOGS (Last 20)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep "scheduler" | tail -20
echo ""

# Show schedule matches (applied schedules)
echo "✅ SCHEDULE MATCHES (Last 10)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep -E "Schedule match|Schedule applied" | tail -10
echo ""

# Show schedule skips
echo "⏭️  SCHEDULE SKIPS (Last 5)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep "Schedule skipped" | tail -5 || echo "No skips found"
echo ""

# Show current schedule configuration
echo "⚙️  SCHEDULE CONFIGURATION"
echo "------------------------------------------"
docker exec ${CONTAINER} cat /app/schedule.json 2>/dev/null | jq '.' || echo "❌ Failed to read schedule.json"
echo ""

echo "=========================================="
echo "💡 TIP: Watch live logs with:"
echo "   docker logs -f ${CONTAINER} | grep scheduler"
echo "=========================================="
