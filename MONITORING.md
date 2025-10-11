# AI Mode Monitoring Guide

This guide helps you monitor and test AI Mode over several days before deploying to production.

## Quick Status Check

### View Current AI Mode Status
```bash
./monitor_ai_mode.sh
```

Shows:
- ✅ AI Mode enabled/disabled
- 🌡️ Current temperatures (outdoor, room, flow)
- 📈 Active heating curve
- 🔥 Heat pump actual status
- 🏠 Thermostat status
- 📜 Recent AI adjustments

## Data Logging for Analysis

### Manual Logging (One-Time Snapshot)
```bash
./log_ai_mode.sh
```

Creates/appends to `ai_mode_log.csv` with:
- Timestamp
- All temperatures
- Calculated vs actual values
- Heating curve used
- Heating needed status

### Automatic Logging (Every Hour)

Set up a cron job to log data automatically:

```bash
# Edit crontab
crontab -e

# Add this line (logs every hour at minute 0)
0 * * * * cd /home/stephan/projects/lg_r290_control && ./log_ai_mode.sh

# Or log every 30 minutes
*/30 * * * * cd /home/stephan/projects/lg_r290_control && ./log_ai_mode.sh

# Or log every 10 minutes (more detailed)
*/10 * * * * cd /home/stephan/projects/lg_r290_control && ./log_ai_mode.sh
```

### View Logged Data
```bash
# View entire log
cat ai_mode_log.csv

# View last 20 entries
tail -20 ai_mode_log.csv

# View with column formatting
column -t -s, ai_mode_log.csv | less -S
```

## Real-Time Monitoring

### Watch AI Mode Live (Updates Every 30s)
```bash
watch -n 30 './monitor_ai_mode.sh'
```

### Follow Live Logs (See Adjustments in Real-Time)
```bash
docker-compose logs -f heatpump-service | grep -E "(AI Mode|outdoor:|target_room:|flow temp)"
```

### Follow All Logs
```bash
docker-compose logs -f heatpump-service
```

## What to Monitor During Testing

### ✅ Check These Key Points:

1. **Temperature Source Accuracy**
   - Is outdoor temp from Shelly sensor correct? (compare with weather)
   - Is indoor temp matching thermostat display?

2. **Heating Curve Selection**
   - Does it select correct curve based on target room temp?
     - ≤21°C → ECO Mode
     - 21-23°C → Comfort Mode
     - >23°C → High Demand

3. **Flow Temperature Calculation**
   - Does calculated flow temp match the curve?
   - Example: outdoor 11.7°C, target 21.5°C → Comfort Mode → 35°C

4. **Adjustment Behavior**
   - Does it only adjust when diff ≥ 2°C (threshold)?
   - Does it avoid excessive adjustments?

5. **Cutoff Temperature**
   - Does it turn OFF when outdoor ≥ 18°C?
   - Does it turn back ON when outdoor < 17°C?

6. **Fallback Behavior**
   - If thermostat API is unavailable, does it use default 21°C?
   - If Shelly outdoor sensor fails, does it fall back to heat pump sensor?

## Analyzing Collected Data

### View Data in Spreadsheet
```bash
# Open in LibreOffice Calc
libreoffice --calc ai_mode_log.csv

# Or copy to Windows/Mac and open in Excel
```

### Quick Statistics (Last 24 Hours)
```bash
# Count adjustments in last 24 hours
tail -144 ai_mode_log.csv | grep -c "1" | head -1

# Average outdoor temperature (last 24h)
tail -144 ai_mode_log.csv | awk -F, '{sum+=$3; count++} END {print sum/count}'

# Average calculated flow temp (last 24h)
tail -144 ai_mode_log.csv | awk -F, '{sum+=$5; count++} END {print sum/count}'
```

## Troubleshooting

### AI Mode Not Adjusting
```bash
# Check if enabled
curl -s http://192.168.2.11:8002/ai-mode | grep enabled

# Check logs for errors
docker-compose logs --tail 100 heatpump-service | grep -i error

# Check last update time
curl -s http://192.168.2.11:8002/ai-mode | grep last_update
```

### Wrong Temperature Readings
```bash
# Check thermostat API directly
curl -s http://192.168.2.11:8001/api/v1/thermostat/status | python3 -m json.tool

# Check heat pump outdoor sensor
curl -s http://192.168.2.11:8002/status | grep outdoor_temperature
```

### Excessive Adjustments
```bash
# Check adjustment threshold (should be 2°C)
curl -s http://192.168.2.11:8002/ai-mode | grep adjustment_threshold

# View all adjustments today
docker-compose logs --since $(date +%Y-%m-%d) heatpump-service | grep "AI Mode: Adjusted"
```

## Production Readiness Checklist

Before merging to master and deploying to real hardware:

- [ ] AI Mode runs stable for 3-7 days without crashes
- [ ] Temperature calculations are accurate
- [ ] Heating curves select correctly based on target room temp
- [ ] Adjustments happen at reasonable intervals (not too frequent)
- [ ] Outdoor temperature cutoff works (≥18°C turns OFF)
- [ ] Fallback behavior works when thermostat unavailable
- [ ] No excessive logging or errors in logs
- [ ] CSV log analysis shows sensible patterns
- [ ] Mock server behavior matches expectations
- [ ] Ready to test with real LG R290 hardware

## Configuration Tweaks

### Change Update Interval (Edit service/heating_curve_config.json)
```json
"settings": {
  "update_interval_seconds": 600  // Change from 30 to 600 (10 minutes) for production
}
```

Then reload without restart:
```bash
curl -X POST http://192.168.2.11:8002/ai-mode/reload-config
```

### Change Adjustment Threshold
```json
"adjustment_threshold": 2  // Increase to 3 to reduce adjustments, decrease to 1 for more sensitive
```

### Tune Heating Curves
Edit the flow_temp values in each curve to match your system's needs.

## Support

For issues or questions:
- Check logs: `docker-compose logs heatpump-service`
- Review ARCHITECTURE.md for system design
- Check UML diagrams in UML/ directory
- Review CHANGELOG.md for version history
