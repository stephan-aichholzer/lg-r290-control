#!/bin/bash
# System Status Overview
# Quick glance at entire system status

set -e

CONTAINER="lg_r290_service"
API_URL="http://localhost:8002"

echo "=========================================="
echo "  LG R290 SYSTEM STATUS"
echo "  $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=========================================="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container ${CONTAINER} is not running"
    echo ""
    echo "Start with: docker-compose up -d"
    exit 1
fi

# Container status
echo "🐳 DOCKER CONTAINERS"
echo "------------------------------------------"
docker ps --filter "name=lg_r290" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Heat Pump Status
echo "🔥 HEAT PUMP"
echo "------------------------------------------"
curl -s ${API_URL}/status 2>/dev/null | jq '{
  power: (if .is_on then "ON ✅" else "OFF ❌" end),
  compressor: (if .compressor_running then "ON 🔥" else "OFF" end),
  target_temp: (.target_temperature | tostring + "°C"),
  flow_temp: (.flow_temperature | tostring + "°C"),
  outdoor_temp: (.outdoor_temperature | tostring + "°C"),
  mode: .operating_mode
}' | sed 's/"//g' || echo "❌ Failed to fetch status"
echo ""

# AI Mode Status
echo "🤖 AI MODE"
echo "------------------------------------------"
AI_STATUS=$(curl -s ${API_URL}/ai-mode 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$AI_STATUS" | jq '{
      enabled: (if .enabled then "ON ✅" else "OFF ❌" end),
      heating_curve: .heating_curve,
      calculated_flow_temp: (.calculated_flow_temperature | tostring + "°C"),
      adjustment_needed: .adjustment_needed
    }' | sed 's/"//g'
else
    echo "❌ Failed to fetch AI Mode status"
fi
echo ""

# Scheduler Status
echo "📅 SCHEDULER"
echo "------------------------------------------"
SCHED_STATUS=$(curl -s ${API_URL}/schedule 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$SCHED_STATUS" | jq '{
      enabled: (if .enabled then "ON ✅" else "OFF ❌" end),
      current_day: .current_day,
      current_time: .current_time,
      timezone: .timezone,
      schedules: .schedule_count
    }' | sed 's/"//g'
else
    echo "❌ Failed to fetch scheduler status"
fi
echo ""

# Thermostat Status
echo "🌡️  THERMOSTAT"
echo "------------------------------------------"
THERMOSTAT_URL="http://192.168.2.11:8001"
THERMO_STATUS=$(curl -s ${THERMOSTAT_URL}/api/v1/thermostat/status 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$THERMO_STATUS" | jq '{
      mode: .config.mode,
      target_temp: (.config.target_temp | tostring + "°C"),
      indoor_temp: (.all_temps.temp_indoor | tostring + "°C"),
      outdoor_temp: (.all_temps.temp_outdoor | tostring + "°C"),
      pump: (if .switch_state then "ON ✅" else "OFF ❌" end)
    }' | sed 's/"//g'
else
    echo "❌ Thermostat unavailable (using fallback)"
fi
echo ""

# Recent Activity
echo "📜 RECENT ACTIVITY (Last 10 lines)"
echo "------------------------------------------"
docker logs ${CONTAINER} 2>&1 | grep -E "Schedule match|Schedule applied|Adjusted flow|AI Mode" | tail -10 || echo "No recent activity"
echo ""

# Health Check
echo "💚 HEALTH CHECK"
echo "------------------------------------------"
HEALTH=$(curl -s ${API_URL}/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$HEALTH" | jq '.' | sed 's/"//g'
else
    echo "❌ Health check failed"
fi
echo ""

echo "=========================================="
echo "📊 MONITORING COMMANDS"
echo "------------------------------------------"
echo "  ./monitor_scheduler.sh    - Detailed scheduler logs"
echo "  ./monitor_ai_mode.sh      - Detailed AI Mode logs"
echo "  docker-compose logs -f    - Live logs (all services)"
echo "=========================================="
