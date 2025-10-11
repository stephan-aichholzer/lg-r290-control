#!/bin/bash
# AI Mode Data Logger
# Logs AI Mode status to CSV file for analysis

LOG_FILE="ai_mode_log.csv"

# Create header if file doesn't exist
if [ ! -f "$LOG_FILE" ]; then
    echo "timestamp,enabled,outdoor_temp,target_room_temp,calculated_flow_temp,actual_setpoint,actual_flow_temp,heating_curve,indoor_temp,heating_needed" > "$LOG_FILE"
fi

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Fetch and parse data in one Python script
python3 << 'PYEOF'
import json
import sys
import urllib.request

try:
    # Fetch data
    ai_data = json.loads(urllib.request.urlopen('http://192.168.2.11:8002/ai-mode').read())
    hp_data = json.loads(urllib.request.urlopen('http://192.168.2.11:8002/status').read())
    th_data = json.loads(urllib.request.urlopen('http://192.168.2.11:8001/api/v1/thermostat/status').read())

    # Parse fields
    enabled = "1" if ai_data.get('enabled') else "0"
    outdoor_temp = ai_data.get('outdoor_temperature', '')
    target_room_temp = ai_data.get('target_room_temperature', '')
    calc_flow_temp = ai_data.get('calculated_flow_temperature', '')
    actual_setpoint = hp_data.get('target_temperature', '')
    actual_flow_temp = hp_data.get('flow_temperature', '')
    heating_curve = ai_data.get('heating_curve', {}).get('name', '').replace(',', ' ')
    indoor_temp = th_data.get('current_temp', '')
    heating_needed = "1" if th_data.get('heating_needed') else "0"

    timestamp = sys.argv[1] if len(sys.argv) > 1 else ''

    # Output CSV line
    print(f"{timestamp},{enabled},{outdoor_temp},{target_room_temp},{calc_flow_temp},{actual_setpoint},{actual_flow_temp},{heating_curve},{indoor_temp},{heating_needed}")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    python3 -c "
import json, sys, urllib.request
ai = json.loads(urllib.request.urlopen('http://192.168.2.11:8002/ai-mode').read())
hp = json.loads(urllib.request.urlopen('http://192.168.2.11:8002/status').read())
th = json.loads(urllib.request.urlopen('http://192.168.2.11:8001/api/v1/thermostat/status').read())
enabled = '1' if ai.get('enabled') else '0'
outdoor_temp = ai.get('outdoor_temperature', '')
target_room_temp = ai.get('target_room_temperature', '')
calc_flow_temp = ai.get('calculated_flow_temperature', '')
actual_setpoint = hp.get('target_temperature', '')
actual_flow_temp = hp.get('flow_temperature', '')
heating_curve = ai.get('heating_curve', {}).get('name', '').replace(',', ' ')
indoor_temp = th.get('current_temp', '')
heating_needed = '1' if th.get('heating_needed') else '0'
print(f'$TIMESTAMP,{enabled},{outdoor_temp},{target_room_temp},{calc_flow_temp},{actual_setpoint},{actual_flow_temp},{heating_curve},{indoor_temp},{heating_needed}')
" >> "$LOG_FILE"
    echo "Logged to $LOG_FILE at $TIMESTAMP"
else
    echo "Failed to log data"
    exit 1
fi
