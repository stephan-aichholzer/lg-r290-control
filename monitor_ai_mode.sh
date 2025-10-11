#!/bin/bash
# AI Mode Monitoring Script
# Displays current AI Mode status, temperatures, and recent activity

echo "======================================"
echo "AI Mode Status - $(date)"
echo "======================================"
echo ""

echo "📊 AI Mode Configuration:"
curl -s http://192.168.2.11:8002/ai-mode | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Enabled: {'✓ YES' if data['enabled'] else '✗ NO'}\")
print(f\"  Last Update: {data['last_update']}\")
print(f\"  Update Interval: {data['update_interval_seconds']}s\")
print(f\"  Adjustment Threshold: {data['adjustment_threshold']}°C\")
print()
print(f\"🌡️  Temperatures:\")
print(f\"  Outdoor: {data['outdoor_temperature']}°C (from Shelly sensor)\")
print(f\"  Target Room: {data['target_room_temperature']}°C (from thermostat)\")
print(f\"  Calculated Flow: {data['calculated_flow_temperature']}°C\")
print()
print(f\"📈 Heating Curve:\")
print(f\"  Mode: {data['heating_curve']['name']}\")
print(f\"  Range: {data['heating_curve']['target_temp_range'][0]}-{data['heating_curve']['target_temp_range'][1]}°C\")
"
echo ""

echo "🔥 Heat Pump Actual Status:"
curl -s http://192.168.2.11:8002/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Power: {'ON ✓' if data['is_on'] else 'OFF ✗'}\")
print(f\"  Target Temperature: {data['target_temperature']}°C (setpoint)\")
print(f\"  Flow Temperature: {data['flow_temperature']}°C (current)\")
print(f\"  Return Temperature: {data['return_temperature']}°C\")
print(f\"  Compressor: {'Running ✓' if data['compressor_running'] else 'Stopped ✗'}\")
"
echo ""

echo "🏠 Thermostat Status:"
curl -s http://192.168.2.11:8001/api/v1/thermostat/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Mode: {data['config']['mode']}\")
print(f\"  Target: {data['config']['target_temp']}°C\")
print(f\"  Current Indoor: {data['current_temp']}°C\")
print(f\"  Outdoor: {data['all_temps']['temp_outdoor']}°C\")
print(f\"  Heating Needed: {'YES ✓' if data['heating_needed'] else 'NO ✗'}\")
"
echo ""

echo "📜 Recent AI Mode Activity (last 10 adjustments):"
docker-compose logs --tail 500 heatpump-service 2>/dev/null | \
  grep "AI Mode: Adjusted" | \
  tail -10 | \
  sed 's/.*\[0m //' | \
  sed 's/^/  /'

if [ $? -ne 0 ]; then
  echo "  No adjustments found in recent logs"
fi

echo ""
echo "======================================"
echo "Monitoring complete"
echo "======================================"
