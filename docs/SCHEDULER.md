# Scheduler - Time-Based Temperature Control

## Overview

The Scheduler provides automatic, time-based room temperature control by scheduling target temperatures at specific times throughout the week. It works silently in the background, calling the thermostat API to set mode and temperature, and the heat pump API to set LG Auto mode offset at scheduled times.

**Key Features:**
- Week-based scheduling (different schedules for weekdays/weekends)
- **LG Auto Mode Offset Scheduling**: Automatically adjust heat pump flow temperature response at different times
- Automatic mode management (forces AUTO mode at scheduled times)
- Respects manual ECO/OFF modes (schedule only affects AUTO/ON modes)
- Hot-reloadable configuration (via volume mount - restart only)
- Vienna timezone support (CEST/CET with automatic DST)

## How It Works

### Behavior

1. **Schedule Checking**: Every 60 seconds, the scheduler checks if the current time matches a scheduled period
2. **Mode Check**: If match found, checks current thermostat mode:
   - **ECO or OFF**: Schedule is skipped (no change)
   - **AUTO or ON**: Schedule is applied
3. **Application**:
   - Sets thermostat mode to AUTO and applies scheduled target temperature
   - Sets heat pump LG Auto mode offset (adjusts flow temperature response)
4. **Reset Function**: Acts as a "resetter" - if user manually changes temperature or offset, the next scheduled period will reset it back

### LG Auto Mode Offset Scheduling

The scheduler can automatically adjust the heat pump's flow temperature response at different times of day. This allows you to:

- **Morning (05:00)**: Set higher offset (+3K) for faster heating and warm radiators
- **Daytime (09:00)**: Set neutral offset (0K) for efficient steady-state operation
- **Evening (17:00)**: Set moderate offset (+1K) for gentle evening comfort
- **Night (22:00)**: Set lower offset (-1K) for minimal flow temperature

**How it works:**
- Offset range: -5K to +5K (integer values)
- Higher offset (+3K) = Higher flow temperature = Faster room heating
- Lower offset (-1K) = Lower flow temperature = More efficient operation
- Offset is **only active** when heat pump is in LG Auto mode (register 40001 = 3)

### Example Timeline

```
Monday 05:00 → Scheduler sets AUTO mode, 22.2°C, offset +3K (fast warm-up)
       07:30 → User manually changes to ON mode, 24.0°C (allowed)
       09:00 → Scheduler resets to AUTO mode, 22.0°C, offset 0K (relaxed)
       15:00 → User changes to ECO mode (scheduler will not interfere)
       17:00 → Scheduler SKIPS (ECO mode active, offset not changed)
       22:00 → User returns to AUTO mode
       22:00 → Scheduler sets 21.5°C, offset -1K (efficient night heating)
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
        {"time": "05:00", "target_temp": 22.2, "auto_offset": 3},
        {"time": "09:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "17:00", "target_temp": 22.0, "auto_offset": 1},
        {"time": "22:00", "target_temp": 21.0, "auto_offset": -1}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "06:00", "target_temp": 22.2, "auto_offset": 3},
        {"time": "10:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "23:00", "target_temp": 21.0, "auto_offset": -1}
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
| `periods` | array | Array of time/temperature/offset tuples |
| `time` | string | Time in HH:MM format (24-hour, local time) |
| `target_temp` | number | Target room temperature in °C |
| `auto_offset` | integer | LG Auto mode offset in Kelvin (-5 to +5) |

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
│  │  ├─ POST /thermostat/config (set AUTO+temp)  │  │
│  │  └─ POST /auto-mode-offset (set offset)      │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
┌──────────────────────┐  ┌─────────────────────────┐
│  Thermostat API      │  │  Heat Pump API          │
│  (iot-api:8000)      │  │  (localhost:8000)       │
│  - Updates mode      │  │  - Sets LG Auto offset  │
│  - Sets target_temp  │  │  - Register 40005       │
│  - Controls pump     │  │  - Adjusts flow temp    │
└──────────────────────┘  └─────────────────────────┘
```

### File Structure

```
service/
├── main.py                    # FastAPI app, scheduler initialization
├── scheduler.py               # Scheduler logic and background task
├── schedule.json              # Schedule configuration (volume-mounted)
└── Dockerfile                 # Builds service image

docker-compose.yml             # Includes schedule.json volume mount
```

### Initialization Flow

1. `main.py` reads `ENABLE_SCHEDULER` flag (line 45)
2. If enabled, creates `Scheduler` instance with thermostat API URL and heat pump API URL
3. `Scheduler.__init__()` loads `schedule.json` from volume mount
4. `asyncio.create_task(scheduler.run())` starts background task
5. Background task runs continuously, checking every 60 seconds
6. When match found, calls both thermostat API and heat pump API

## Use Cases

### Comfort-Optimized Schedule (Recommended)

**Scenario**: Fast warm-up in the morning, efficient operation during the day, gentle evening, economical night

```json
{
  "enabled": true,
  "schedules": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "periods": [
        {"time": "05:00", "target_temp": 22.2, "auto_offset": 3},
        {"time": "09:00", "target_temp": 21.5, "auto_offset": 0},
        {"time": "17:00", "target_temp": 22.0, "auto_offset": 1},
        {"time": "22:00", "target_temp": 21.5, "auto_offset": -1}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "05:00", "target_temp": 22.2, "auto_offset": 3},
        {"time": "10:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "23:00", "target_temp": 21.5, "auto_offset": -1}
      ]
    }
  ]
}
```

**Benefits:**
- **05:00**: +3K offset = High flow temp = Fast heating + warm radiators (comfort priority)
- **09:00/10:00**: 0K offset = Normal flow temp = Efficient steady-state (energy priority)
- **17:00**: +1K offset = Moderate flow temp = Gentle evening boost (comfort)
- **22:00/23:00**: -1K offset = Low flow temp = Minimal heating for sleep (energy priority)

### Maximum Efficiency Schedule

**Scenario**: Prioritize energy efficiency over fast response times

```json
{
  "enabled": true,
  "schedules": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "periods": [
        {"time": "06:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "08:00", "target_temp": 20.0, "auto_offset": -2},
        {"time": "17:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "23:00", "target_temp": 21.0, "auto_offset": -1}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "periods": [
        {"time": "08:00", "target_temp": 22.0, "auto_offset": 0},
        {"time": "23:00", "target_temp": 21.0, "auto_offset": -1}
      ]
    }
  ]
}
```

**Benefits:**
- Lower flow temperatures throughout the day = Better heat pump COP
- Minimal offset adjustments = Predictable, efficient operation
- Suitable for well-insulated homes with low heating demand

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

**After editing `schedule.json` on host**, the file is volume-mounted so changes are immediately available to the container. You must **restart the service** to reload the configuration:

```bash
docker-compose restart heatpump-service
```

The configuration is read once at startup, so a restart is required to apply changes.

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
2025-10-24 05:00:48 - scheduler - INFO - Schedule loaded: enabled=True, 2 schedule(s)
2025-10-24 05:00:48 - scheduler - INFO - Scheduler started
2025-10-24 05:00:48 - scheduler - INFO - Schedule match: friday 05:00 → 22.2°C, auto_offset: +3K
2025-10-24 05:00:48 - scheduler - INFO - ✓ Schedule applied: mode=AUTO, target_temp=22.2°C
2025-10-24 05:00:48 - scheduler - INFO - Setting LG Auto mode offset to +3K via heat pump API
2025-10-24 05:00:54 - scheduler - INFO - ✓ LG Auto mode offset set to +3K
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
