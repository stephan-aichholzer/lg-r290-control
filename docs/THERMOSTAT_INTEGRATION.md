# Thermostat Integration - Room Temperature Control

## Overview

The thermostat integration connects the heat pump control system with an external thermostat service (`shelly_bt_temp` project) to control room temperature. The thermostat manages the circulation pump based on indoor temperature readings, creating a complete heating control system.

**Key Concept**: Heat pump heats water → Thermostat controls circulation pump → Room temperature regulated

## System Architecture

```
┌──────────────────────┐      ┌──────────────────────┐
│  Heat Pump Control   │      │  Thermostat Service  │
│  (lg_r290_control)   │      │  (shelly_bt_temp)    │
│                      │      │                      │
│  - Heat water        │◄────►│  - Read room temp    │
│  - AI Mode           │ HTTP │  - Control pump      │
│  - Scheduler         │      │  - Modes (AUTO/ECO)  │
└──────────────────────┘      └──────────────────────┘
         │                             │
         ↓                             ↓
  LG R290 Heat Pump          Circulation Pump + Sensors
  (Water heating)            (Room heating distribution)
```

## Integration Points

### 1. LG Auto Mode Offset Integration

The system adjusts LG Auto mode offset based on thermostat mode:

```python
# GET http://iot-api:8000/api/v1/thermostat/status
response = {
  "config": {"target_temp": 21.5, "mode": "AUTO"},
  "switch_state": true  # Pump running
}

# Auto mode offset adjustment based on mode:
# ECO → -2K (energy saving)
# AUTO → +2K (comfort)
# ON → +2K (comfort)
# OFF → -5K (minimal heating)
```

**Note**: This adjusts register 40005 (LG Auto mode offset) when LG mode is set to Auto (register 40001 = 3).

### 2. Scheduler Integration

Scheduler calls thermostat API to set room temperature at scheduled times:

```python
# GET current config (check mode)
GET http://iot-api:8000/api/v1/thermostat/config

# POST new config (set AUTO + temp)
POST http://iot-api:8000/api/v1/thermostat/config
{
  "mode": "AUTO",
  "target_temp": 22.2,
  "eco_temp": 19.0,
  "hysteresis": 0.1,
  ...
}
```

**Mode Behavior**:
- AUTO/ON modes: Scheduler applies
- ECO/OFF modes: Scheduler skips (respects user choice)

### 3. UI Display Integration

Thermostat module in UI (`ui/thermostat.js`) displays room temperature and provides controls:

```javascript
// Poll thermostat status every 60 seconds
GET http://192.168.2.11:8001/api/v1/thermostat/status

// Update UI display
- Indoor temperature (from Shelly BT sensor)
- Outdoor temperature (from Shelly outdoor sensor)
- Pump status (ON/OFF indicator)
- Target temperature (user setpoint)
- Mode buttons (AUTO, ECO, ON, OFF)
```

## Thermostat API Endpoints

### Get Status

```http
GET /api/v1/thermostat/status
```

**Response:**
```json
{
  "config": {
    "mode": "AUTO",
    "target_temp": 22.0,
    "eco_temp": 19.0
  },
  "switch_state": true,
  "all_temps": {
    "temp_indoor": 21.5,
    "temp_outdoor": 11.7
  },
  "active_target": 22.0
}
```

### Get Configuration

```http
GET /api/v1/thermostat/config
```

**Response:**
```json
{
  "mode": "AUTO",
  "target_temp": 22.0,
  "eco_temp": 19.0,
  "hysteresis": 0.1,
  "min_on_time": 40,
  "min_off_time": 10,
  "temp_sample_count": 4,
  "control_interval": 60
}
```

### Set Configuration

```http
POST /api/v1/thermostat/config
Content-Type: application/json

{
  "mode": "AUTO",
  "target_temp": 22.5,
  "eco_temp": 19.0,
  "hysteresis": 0.1,
  "min_on_time": 40,
  "min_off_time": 10,
  "temp_sample_count": 4,
  "control_interval": 60
}
```

## Thermostat Modes

| Mode | Description | Pump Control |
|------|-------------|--------------|
| **AUTO** | Automatic based on temperature | ON if temp < (target - hysteresis)<br>OFF if temp ≥ target |
| **ECO** | Energy saving mode | Uses eco_temp instead of target_temp |
| **ON** | Force pump ON | Always ON (ignores temperature) |
| **OFF** | System disabled | Always OFF |

## Network Configuration

### Docker Network Setup

Both projects share a Docker network for communication:

**lg_r290_control/docker-compose.yml:**
```yaml
services:
  heatpump-service:
    environment:
      - THERMOSTAT_API_URL=http://iot-api:8000  # Container name
    networks:
      - heatpump-net
      - shelly_bt_temp_default  # External network reference

networks:
  shelly_bt_temp_default:
    external: true  # Reference to thermostat network
```

**shelly_bt_temp/docker-compose.yml:**
```yaml
services:
  api:
    container_name: iot-api
    networks:
      - default  # Creates shelly_bt_temp_default network
```

### Access Patterns

**Browser → Thermostat:**
- Direct LAN access: `http://192.168.2.11:8001`
- No Docker network needed

**Container → Thermostat:**
- Docker DNS: `http://iot-api:8000`
- Via `shelly_bt_temp_default` network

## Configuration

### Environment Variable

Set in `docker-compose.yml`:

```yaml
THERMOSTAT_API_URL=${THERMOSTAT_API_URL:-http://iot-api:8000}
```

**Development (Docker)**: `http://iot-api:8000`
**External access**: `http://192.168.2.11:8001`

### UI Configuration

Set in `ui/config.js`:

```javascript
THERMOSTAT_API_URL: `http://192.168.2.11:8001`,  // Browser uses host IP
THERMOSTAT_UPDATE_INTERVAL: 60000,  // 60 seconds
```

## Temperature Sources

### Indoor Temperature
- **Source**: Shelly BLU Button1 (Bluetooth sensor)
- **Used by**: Thermostat (pump control), UI display
- **Update**: Every few seconds via BLE

### Outdoor Temperature
- **Source**: Shelly Plus Add-On with DS18B20 sensor
- **Used by**: AI Mode (heating curve), Scheduler (display), UI display
- **Update**: Every few seconds via Shelly API

### Flow Temperature (Heat Pump)
- **Source**: LG R290 heat pump Modbus register
- **Used by**: Heat pump control, AI Mode
- **Update**: Every 5 seconds via Modbus polling

## Pump Control Logic

Thermostat evaluates conditions every 60 seconds:

```python
if mode == "OFF":
    pump = OFF
elif mode == "ON":
    pump = ON
elif mode in ["AUTO", "ECO"]:
    target = eco_temp if mode == "ECO" else target_temp
    avg_temp = average(last 4 indoor readings)

    if pump == OFF:
        if avg_temp < (target - hysteresis):
            if off_time >= min_off_time:
                pump = ON
    elif pump == ON:
        if avg_temp >= target:
            if on_time >= min_on_time:
                pump = OFF
```

**Parameters:**
- `hysteresis`: 0.1°C (prevents rapid cycling)
- `min_on_time`: 40 minutes (pump protection)
- `min_off_time`: 10 minutes (pump protection)
- `temp_sample_count`: 4 (averaging for stability)

## Common Scenarios

### Heating Cycle

```
1. Indoor: 20.5°C, Target: 22.0°C, Mode: AUTO
2. Thermostat: temp < (target - hysteresis) → Turn pump ON
3. Heat pump: Water at 40°C flows through radiators
4. Indoor rises: 20.5°C → 21.0°C → 21.5°C → 22.0°C
5. Thermostat: temp ≥ target → Turn pump OFF
6. Indoor gradually drops
7. Cycle repeats
```

### Scheduler Override

```
Time: 22:00
1. User manually set target: 24.0°C
2. Pump running to reach 24°C
3. Scheduler triggers: Set AUTO mode, target 21.0°C
4. Thermostat updates: target = 21.0°C
5. Indoor currently: 22.5°C > target (21.0°C)
6. Pump turns OFF (target reached)
```

### LG Auto Mode with Thermostat

```
Outdoor: 5°C, Thermostat Mode: AUTO
1. System detects thermostat mode: AUTO
2. Sets LG Auto mode offset: +2K (from config)
3. LG heat pump calculates base flow temp from outdoor temp
4. Applies offset: final temp = base + 2K
5. Thermostat independently controls pump based on room temp
6. Result: LG heating curve + offset adjustment + room temp control
```

## Troubleshooting

### Thermostat API Unreachable from Container

**Check network:**
```bash
docker network ls | grep shelly_bt_temp_default
docker network inspect shelly_bt_temp_default
```

**Test connection:**
```bash
docker exec lg_r290_service curl http://iot-api:8000/api/v1/thermostat/status
```

**Solution**: Verify `shelly_bt_temp_default` network exists and is external in docker-compose.yml.

### Auto Mode Offset Not Applying

**Symptom**: Offset doesn't change based on thermostat mode

**Check thermostat:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status
```

**Common causes**:
- Thermostat service not running
- Network configuration incorrect
- Wrong THERMOSTAT_API_URL
- LG mode not set to Auto (register 40001 must be 3)

**Result**: System uses default offset (0K) until thermostat connection restored.

### Pump Not Responding to Temperature Changes

**Check thermostat mode:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status | jq .config.mode
```

**Verify:**
- Mode is AUTO or ECO (not OFF or ON)
- Indoor temperature sensor working
- Pump minimum on/off times respected

### Scheduler Not Applying to Thermostat

**Check current mode:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/config | jq .mode
```

**If ECO or OFF**: Scheduler respects these modes and skips (by design).

**Check scheduler logs:**
```bash
docker logs lg_r290_service | grep scheduler
```

Look for: "Schedule skipped: current mode is ECO"

## Related Documentation

- [Scheduler](SCHEDULER.md) - Time-based room temperature scheduling
- [Heat Pump Control](HEAT_PUMP_CONTROL.md) - LG Mode water temperature control
- [Deployment](DEPLOYMENT.md) - Docker network setup
- [API Reference](API_REFERENCE.md) - Complete API documentation
