#!/bin/bash
# Monitor AI Mode Activity
# Shows AI Mode logs, status, and heating curve decisions

set -e

CONTAINER="lg_r290_service"
API_URL="http://localhost:8002"

echo "=========================================="
echo "  AI MODE MONITOR"
echo "=========================================="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container ${CONTAINER} is not running"
    exit 1
fi

# Get AI Mode status
echo "🤖 AI MODE STATUS"
echo "------------------------------------------"
curl -s ${API_URL}/ai-mode | jq '.' 2>/dev/null || echo "❌ Failed to fetch AI Mode status"
echo ""

# Get heat pump status
echo "🔥 HEAT PUMP STATUS"
echo "------------------------------------------"
curl -s ${API_URL}/status | jq '{
  is_on: .is_on,
  compressor_running: .compressor_running,
  target_temperature: .target_temperature,
  flow_temperature: .flow_temperature,
  return_temperature: .return_temperature,
  outdoor_temperature: .outdoor_temperature
}' 2>/dev/null || echo "❌ Failed to fetch heat pump status"
echo ""

# Get thermostat target temp (used by AI Mode)
echo "🌡️  TARGET ROOM TEMPERATURE"
echo "------------------------------------------"
THERMOSTAT_URL=$(docker exec ${CONTAINER} printenv THERMOSTAT_API_URL 2>/dev/null || echo "http://iot-api:8000")
docker exec ${CONTAINER} curl -s ${THERMOSTAT_URL}/api/v1/thermostat/status 2>/dev/null | jq '{
  target_temp: .config.target_temp,
  indoor_temp: .all_temps.temp_indoor,
  mode: .config.mode
}' || echo "❌ Failed to fetch thermostat (using fallback 21°C)"
echo ""

# Show recent AI Mode logs
echo "📜 RECENT AI MODE LOGS (Last 20)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep -E "adaptive_controller|AI Mode" | tail -20
echo ""

# Show temperature adjustments
echo "📊 TEMPERATURE ADJUSTMENTS (Last 10)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep "Adjusted flow temperature" | tail -10 || echo "No adjustments found"
echo ""

# Show heating curve selections
echo "📈 HEATING CURVE SELECTIONS (Last 10)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep -E "Selected curve|heating_curve" | tail -10 || echo "No curve selections logged"
echo ""

# Show outdoor temp cutoff events
echo "🌡️  OUTDOOR TEMP CUTOFF/RESTART EVENTS (Last 5)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep -E "Outdoor temp|cutoff|restart" | tail -5 || echo "No cutoff events"
echo ""

# Show heating curve configuration
echo "⚙️  HEATING CURVE CONFIGURATION"
echo "------------------------------------------"
docker exec ${CONTAINER} cat /app/heating_curve_config.json 2>/dev/null | jq '.settings' || echo "❌ Failed to read heating_curve_config.json"
echo ""

echo "=========================================="
echo "💡 TIP: Watch live AI Mode logs with:"
echo "   docker logs -f ${CONTAINER} | grep -E 'adaptive_controller|AI Mode'"
echo "=========================================="
