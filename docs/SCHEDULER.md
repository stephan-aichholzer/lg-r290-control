# Scheduler - Time-Based Temperature Control

## Overview

The Scheduler provides automatic, time-based room temperature control by scheduling target temperatures at specific times throughout the week. It works silently in the background, calling the thermostat API to set mode and temperature at scheduled times.

**Key Features:**
- Week-based scheduling (different schedules for weekdays/weekends)
- Automatic mode management (forces AUTO mode at scheduled times)
- Respects manual ECO/OFF modes (schedule only affects AUTO/ON modes)
- Hot-reloadable configuration (no restart required)
- Vienna timezone support (CEST/CET with automatic DST)

## How It Works

### Behavior

1. **Schedule Checking**: Every 60 seconds, the scheduler checks if the current time matches a scheduled period
2. **Mode Check**: If match found, checks current thermostat mode:
   - **ECO or OFF**: Schedule is skipped (no change)
   - **AUTO or ON**: Schedule is applied
3. **Application**: Sets mode to AUTO and applies scheduled target temperature
4. **Reset Function**: Acts as a "resetter" - if user manually changes temperature, the next scheduled period will reset it back

### Example Timeline

```
Monday 05:00 → Scheduler sets AUTO mode, 22.2°C
       07:30 → User manually changes to ON mode, 24.0°C (allowed)
       09:00 → Scheduler resets to AUTO mode, 22.0°C
       15:00 → User changes to ECO mode (scheduler will not interfere)
       22:00 → Scheduler SKIPS (ECO mode active)
```

## Configuration

### File Location

`/lg_r290_control/service/schedule.json`

### JSON Format

```json
{
  "enabled": true,
  "schedules": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "periods": [
        {"time": "05:00", "target_temp": 22.2},
        {"time": "09:00", "target_temp": 22.0},
        {"time": "22:00", "target_temp": 21.0}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "06:00", "target_temp": 22.2},
        {"time": "23:00", "target_temp": 21.0}
      ]
    }
  ]
}
```

### Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Master enable/disable flag |
| `schedules` | array | Array of schedule objects |
| `days` | array | Day names (lowercase): `monday`, `tuesday`, etc. |
| `periods` | array | Array of time/temperature pairs |
| `time` | string | Time in HH:MM format (24-hour, local time) |
| `target_temp` | number | Target room temperature in °C |

### Timezone Configuration

Scheduler uses the `TZ` environment variable set in `docker-compose.yml`:

```yaml
environment:
  - TZ=Europe/Vienna
```

**Supported timezones**: Any valid TZ database timezone (e.g., `Europe/Berlin`, `America/New_York`)

**DST Handling**: Automatic - system handles daylight saving time transitions

## API Endpoints

### Get Scheduler Status

```http
GET /schedule
```

**Response:**
```json
{
  "enabled": true,
  "schedule_count": 2,
  "current_time": "2025-10-11 09:30:00",
  "current_day": "Saturday",
  "timezone": "CEST",
  "next_check": [9, 30]
}
```

### Reload Schedule Configuration

```http
POST /schedule/reload
```

Hot-reloads `schedule.json` without restarting the service.

**Response:**
```json
{
  "success": true,
  "enabled": true,
  "schedule_count": 2,
  "message": "Schedule reloaded successfully"
}
```

## Architecture

### Component Integration

```
┌─────────────────────────────────────────────────────┐
│  Scheduler (scheduler.py)                           │
│  ┌───────────────────────────────────────────────┐  │
│  │  Background Task (runs every 60 seconds)      │  │
│  │  ├─ Check current time                        │  │
│  │  ├─ Match against schedule.json               │  │
│  │  └─ If match → apply_schedule_action()        │  │
│  └───────────────────────────────────────────────┘  │
│                        │                             │
│                        ↓                             │
│  ┌───────────────────────────────────────────────┐  │
│  │  apply_schedule_action()                      │  │
│  │  ├─ GET /thermostat/config (check mode)      │  │
│  │  ├─ If mode is ECO/OFF → skip                │  │
│  │  └─ POST /thermostat/config (set AUTO+temp)  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
                         ↓ HTTP Request
┌─────────────────────────────────────────────────────┐
│  Thermostat API (iot-api:8000)                      │
│  - Updates mode and target_temp                     │
│  - Controls circulation pump                        │
└─────────────────────────────────────────────────────┘
```

### File Structure

```
service/
├── main.py                    # FastAPI app, scheduler initialization
├── scheduler.py               # Scheduler logic and background task
├── schedule.json              # Schedule configuration
└── Dockerfile                 # Includes schedule.json in container
```

### Initialization Flow

1. `main.py` reads `ENABLE_SCHEDULER` flag (line 38)
2. If enabled, creates `Scheduler` instance with thermostat API URL
3. `Scheduler.__init__()` loads `schedule.json`
4. `asyncio.create_task(scheduler.run())` starts background task
5. Background task runs continuously, checking every 60 seconds

## Use Cases

### Standard Weekday/Weekend Schedule

**Scenario**: Warmer in the morning, cooler at night, different timing on weekends

```json
{
  "enabled": true,
  "schedules": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "periods": [
        {"time": "05:00", "target_temp": 22.2},
        {"time": "09:00", "target_temp": 22.0},
        {"time": "22:00", "target_temp": 21.0}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "06:00", "target_temp": 22.2},
        {"time": "23:00", "target_temp": 21.0}
      ]
    }
  ]
}
```

### Energy Saving Schedule

**Scenario**: Lower temperature during work hours

```json
{
  "enabled": true,
  "schedules": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "periods": [
        {"time": "06:00", "target_temp": 22.0},
        {"time": "08:00", "target_temp": 20.0},
        {"time": "17:00", "target_temp": 22.0},
        {"time": "23:00", "target_temp": 21.0}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "08:00", "target_temp": 22.0},
        {"time": "23:00", "target_temp": 21.0}
      ]
    }
  ]
}
```

## Disabling the Scheduler

### Method 1: Configuration File

Set `enabled: false` in `schedule.json`:

```json
{
  "enabled": false,
  "schedules": [...]
}
```

Then reload: `curl -X POST http://localhost:8002/schedule/reload`

### Method 2: Code-Level Disable

Edit `service/main.py` line 38:

```python
ENABLE_SCHEDULER = False  # Disables scheduler entirely
```

Then rebuild: `docker-compose build heatpump-service && docker-compose up -d heatpump-service`

## Troubleshooting

### Schedule not triggering

**Check scheduler status:**
```bash
curl http://localhost:8002/schedule | jq .
```

**Verify:**
- `enabled: true`
- `current_time` matches expected timezone
- `current_day` is correct

**Check logs:**
```bash
docker logs lg_r290_service | grep scheduler
```

Look for:
- `Schedule loaded: enabled=True`
- `Scheduler check:` messages (every 60 seconds)
- `Schedule match:` when trigger occurs

### Schedule triggers but temperature doesn't change

**Verify current mode:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status | jq .config.mode
```

If mode is `ECO` or `OFF`, scheduler will skip (this is expected behavior).

**Check logs for:**
```
Schedule skipped: current mode is ECO (only AUTO/ON are affected)
```

### Timezone issues

**Verify container timezone:**
```bash
docker exec lg_r290_service date
```

Should show CEST/CET time, not UTC.

**Check TZ environment variable:**
```bash
docker exec lg_r290_service printenv TZ
```

Should output: `Europe/Vienna`

### Hot reload not working

**After editing `schedule.json` on host**, the file inside the container is NOT automatically updated. You must:

1. **Rebuild container** to copy new schedule.json:
   ```bash
   docker-compose build heatpump-service
   docker-compose up -d heatpump-service
   ```

2. **OR use hot reload API** (only reloads existing file inside container):
   ```bash
   curl -X POST http://localhost:8002/schedule/reload
   ```

## Implementation Details

### Deduplication Logic

Scheduler uses `last_check_minute` to ensure each scheduled time only triggers once:

```python
current_minute = (now.hour, now.minute)  # e.g., (9, 30)
if current_minute == self.last_check_minute:
    return  # Skip, already processed this minute
```

### Schedule Matching

```python
current_day = now.strftime('%A').lower()  # "saturday"
current_time = now.strftime('%H:%M')      # "09:30"

for schedule in schedules:
    if current_day in schedule['days']:
        for period in schedule['periods']:
            if period['time'] == current_time:
                # MATCH!
```

### Mode Checking (Option A)

Scheduler checks mode **before** applying:

```python
response = await client.get(f"{thermostat_api_url}/api/v1/thermostat/config")
current_config = response.json()
current_mode = current_config.get('mode', 'OFF')

if current_mode not in ['AUTO', 'ON']:
    logger.info(f"Schedule skipped: current mode is {current_mode}")
    return False
```

## Logging

Scheduler logs are prefixed with `scheduler`:

**INFO Level:**
```
2025-10-11 09:30:00 - scheduler - INFO - Schedule loaded: enabled=True, 2 schedule(s)
2025-10-11 09:30:00 - scheduler - INFO - Scheduler started
2025-10-11 09:42:00 - scheduler - INFO - Schedule match: saturday 09:42 → 23.5°C
2025-10-11 09:42:00 - scheduler - INFO - ✓ Schedule applied: mode=AUTO, target_temp=23.5°C
```

**DEBUG Level** (enable in main.py):
```
2025-10-11 09:30:00 - scheduler - DEBUG - Scheduler check: 2025-10-11 09:30:00 (Saturday)
2025-10-11 09:30:00 - scheduler - DEBUG - No schedule match for Saturday 09:30
```

## Related Documentation

- [Thermostat Integration](THERMOSTAT_INTEGRATION.md) - Room temperature control
- [Heat Pump Control](HEAT_PUMP_CONTROL.md) - LG Mode control (water temp)
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Deployment](DEPLOYMENT.md) - Docker setup and environment variables
