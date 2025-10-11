# AI Mode - Adaptive Heating Curve Control

## Overview

AI Mode provides autonomous water temperature optimization for the heat pump based on outdoor temperature and target room temperature. It uses weather compensation curves to calculate the optimal flow temperature, adjusting the heat pump automatically every 30 seconds.

**Key Features:**
- Autonomous operation (no user intervention required)
- Weather compensation based on outdoor temperature
- Three heating curves (ECO, Comfort, High Demand)
- Integration with thermostat for target room temperature
- Automatic shutdown when outdoor temp ≥ 18°C
- Hot-reloadable configuration
- Graceful fallback if thermostat unavailable

## How It Works

### Control Loop

AI Mode runs continuously in the background (every 30 seconds):

1. **Read Outdoor Temperature**: From heat pump outdoor sensor (via Modbus)
2. **Read Target Room Temperature**: From thermostat API (if available, else use default 21°C)
3. **Select Heating Curve**: Based on target room temperature
   - ECO: ≤21°C
   - Comfort: 21-23°C
   - High Demand: >23°C
4. **Calculate Flow Temperature**: Lookup flow temp based on outdoor temp range
5. **Apply Adjustment**: Set heat pump target temperature if difference ≥ 2°C

### Weather Compensation Logic

The system adjusts water flow temperature based on outdoor conditions:

**Colder outside → Hotter water needed**
- -10°C outdoor → 48°C flow (Comfort curve)
- 0°C outdoor → 45°C flow
- 10°C outdoor → 40°C flow

**Warmer outside → Cooler water sufficient**
- 18°C outdoor → Heat pump turns OFF (cutoff)

### Example Calculation

**Conditions:**
- Outdoor temperature: 5°C
- Target room temperature: 21.5°C (from thermostat)

**Process:**
1. Select **Comfort Mode** curve (21-23°C range)
2. Find outdoor range: 0-10°C → 40°C flow temp
3. Current heat pump target: 38°C
4. Difference: |40 - 38| = 2°C (≥ threshold)
5. **Action**: Adjust heat pump to 40°C

## Configuration

### File Location

`/lg_r290_control/service/heating_curve_config.json`

### Heating Curves

Three preconfigured curves optimize for different comfort levels:

#### ECO Mode (≤21°C)
```json
{
  "name": "ECO Mode (≤21°C)",
  "target_temp_range": [0, 21],
  "curve": [
    {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 46},
    {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 43},
    {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 38},
    {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 33}
  ]
}
```

#### Comfort Mode (21-23°C)
```json
{
  "name": "Comfort Mode (21-23°C)",
  "target_temp_range": [21, 23],
  "curve": [
    {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 48},
    {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 45},
    {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 40},
    {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 35}
  ]
}
```

#### High Demand (>23°C)
```json
{
  "name": "High Demand (>23°C)",
  "target_temp_range": [23, 999],
  "curve": [
    {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 50},
    {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 47},
    {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 42},
    {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 37}
  ]
}
```

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `outdoor_cutoff_temp` | 18°C | Heat pump turns OFF above this temperature |
| `outdoor_restart_temp` | 17°C | Heat pump restarts below this temperature |
| `update_interval_seconds` | 30 | How often AI Mode checks and adjusts |
| `min_flow_temp` | 30°C | Minimum allowed flow temperature |
| `max_flow_temp` | 50°C | Maximum allowed flow temperature |
| `adjustment_threshold` | 2°C | Only adjust if difference ≥ this value |
| `hysteresis_outdoor` | 1°C | Prevents rapid ON/OFF cycling |
| `default_target_room_temp` | 21°C | Used if thermostat unavailable |

## API Endpoints

### Enable/Disable AI Mode

```http
POST /ai-mode
Content-Type: application/json

{
  "enabled": true
}
```

**Response:**
```json
{
  "status": "success",
  "ai_mode": true,
  "message": "AI Mode enabled"
}
```

### Get AI Mode Status

```http
GET /ai-mode
```

**Response:**
```json
{
  "enabled": true,
  "last_update": "2025-10-11T10:30:00",
  "outdoor_temperature": 5.0,
  "target_room_temperature": 21.5,
  "calculated_flow_temperature": 40.0,
  "current_flow_temperature": 38.0,
  "heating_curve": "Comfort Mode (21-23°C)",
  "adjustment_needed": true,
  "adjustment_reason": "Difference 2°C (threshold: 2°C)"
}
```

### Reload Configuration

```http
POST /ai-mode/reload-config
```

Hot-reloads `heating_curve_config.json` without restarting service.

**Response:**
```json
{
  "status": "success",
  "config_changed": true,
  "message": "Configuration reloaded successfully"
}
```

## Architecture

### Component Interaction

```
┌─────────────────────────────────────────────────────────┐
│  adaptive_controller.py (AI Mode)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Background Task (every 30 seconds)               │  │
│  │  ├─ Get outdoor temp (heat pump sensor)          │  │
│  │  ├─ Get target room temp (thermostat API)        │  │
│  │  ├─ Select heating curve                         │  │
│  │  ├─ Calculate optimal flow temp                  │  │
│  │  └─ Adjust heat pump if needed                   │  │
│  └───────────────────────────────────────────────────┘  │
│                        │                                 │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  heating_curve.py                                 │  │
│  │  - Load heating_curve_config.json                │  │
│  │  - Select curve based on target temp             │  │
│  │  - Lookup flow temp for outdoor temp range       │  │
│  │  - Apply safety limits (30-50°C)                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────┬──────────────────────────┐
│  Heat Pump                   │  Thermostat API          │
│  (Modbus TCP)                │  (iot-api:8000)          │
│  - Read outdoor temp         │  - Read target room temp │
│  - Set flow temperature      │  - Control pump ON/OFF   │
└──────────────────────────────┴──────────────────────────┘
```

### Data Sources

1. **Outdoor Temperature**: Read from heat pump outdoor sensor via Modbus
   - Primary source for weather compensation
   - Updated every 5 seconds by Modbus polling

2. **Target Room Temperature**: Read from thermostat API via HTTP
   - User's desired room temperature
   - Determines which heating curve to use
   - Fallback: 21°C if thermostat unavailable

3. **Current Flow Temperature**: Read from heat pump via Modbus
   - Used to calculate adjustment needed
   - Compared against calculated optimal temperature

### Initialization Flow

1. `main.py` creates `AdaptiveController` instance on startup
2. `AdaptiveController.__init__()` loads `heating_curve_config.json`
3. `start()` creates background asyncio task
4. Task runs continuously every 30 seconds

## Use Cases

### Standard Operation

**Scenario**: AI Mode enabled, thermostat available

```
Time: 10:00
Outdoor: 5°C
Target Room: 21.5°C (from thermostat)
Current Flow: 38°C

AI Mode:
  → Select Comfort curve (21-23°C)
  → Lookup outdoor 5°C: 0-10°C range → 40°C
  → Difference: |40 - 38| = 2°C (≥ threshold)
  → Adjust heat pump to 40°C
  → Log: "AI Mode: Adjusted flow temperature 38°C → 40°C"
```

### Thermostat Unavailable

**Scenario**: AI Mode enabled, thermostat offline

```
Time: 10:00
Outdoor: 5°C
Target Room: 21°C (fallback default)
Current Flow: 38°C

AI Mode:
  → Select ECO curve (≤21°C)
  → Lookup outdoor 5°C: 0-10°C range → 38°C
  → Difference: |38 - 38| = 0°C (< threshold)
  → No adjustment needed
  → Log: "No adjustment needed (diff < 2°C threshold)"
```

### Warm Weather Shutdown

**Scenario**: Outdoor temperature rises above 18°C

```
Time: 14:00
Outdoor: 19°C (≥ cutoff)
Current: Heat pump ON

AI Mode:
  → Outdoor temp ≥ 18°C (cutoff)
  → Turn heat pump OFF
  → Log: "Outdoor temp ≥18°C - Turning heat pump OFF"
```

### Cold Weather Restart

**Scenario**: Outdoor temperature drops below 17°C

```
Time: 02:00
Outdoor: 16°C (≤ restart temp)
Current: Heat pump OFF

AI Mode:
  → Outdoor temp ≤ 17°C (restart)
  → Calculate optimal flow temp: 40°C
  → Turn heat pump ON
  → Set flow temperature: 40°C
  → Wait 2 seconds (power-on delay)
  → Log: "Heat pump restarted - outdoor temp dropped to 16°C"
```

## User Interface Integration

### AI Mode Toggle

When AI Mode is enabled via UI:
1. Temperature slider becomes **disabled** (greyed out)
2. Status text changes to **"AI Mode Active"** (orange)
3. AI Mode controls water temperature automatically
4. User can still turn heat pump OFF via power switch

### Manual Override

If user wants manual control:
1. Disable AI Mode via toggle
2. Temperature slider becomes **enabled**
3. Status text changes to **"Manual Control"**
4. User can set water temperature manually

## Disabling AI Mode

### Method 1: UI Toggle

Use the AI Mode switch in the web interface.

### Method 2: API

```bash
curl -X POST http://localhost:8002/ai-mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Method 3: Code-Level Disable

Edit `service/main.py` and comment out AI Mode initialization:

```python
# # Initialize adaptive controller
# logger.info("Initializing adaptive controller (AI Mode)")
# adaptive_controller = AdaptiveController(modbus_client, thermostat_api_url)
# adaptive_controller.start()
```

Then rebuild: `docker-compose build heatpump-service && docker-compose up -d`

## Adjusting Heating Curves

To customize heating curves for your climate:

1. Edit `service/heating_curve_config.json`
2. Adjust `flow_temp` values in each curve
3. Reload via API: `curl -X POST http://localhost:8002/ai-mode/reload-config`
4. Monitor performance and fine-tune

**Example**: Make ECO mode more aggressive in cold weather:

```json
{
  "outdoor_min": -10,
  "outdoor_max": 0,
  "flow_temp": 45  // Changed from 43°C
}
```

## Troubleshooting

### AI Mode not adjusting temperature

**Check AI Mode status:**
```bash
curl http://localhost:8002/ai-mode | jq .
```

**Verify:**
- `enabled: true`
- `outdoor_temperature` is reading correctly
- `calculated_flow_temperature` makes sense
- `adjustment_needed: true` if temps differ

**Check logs:**
```bash
docker logs lg_r290_service | grep "adaptive_controller\|AI Mode"
```

Look for:
- `Adaptive controller started`
- `AI Mode: Adjusted flow temperature...`
- Error messages

### Thermostat integration not working

**Test thermostat API:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status | jq .
```

**From inside container:**
```bash
docker exec lg_r290_service curl http://iot-api:8000/api/v1/thermostat/status
```

**If fails:**
- Check Docker network: `docker network ls | grep shelly_bt_temp_default`
- Verify thermostat service is running: `docker ps | grep iot-api`
- Check THERMOSTAT_API_URL env variable

**AI Mode will use fallback (21°C) if thermostat unavailable.**

### Heat pump not responding to adjustments

**Check Modbus connection:**
```bash
curl http://localhost:8002/health | jq .
```

Should show: `"modbus_connected": true`

**Check logs:**
```bash
docker logs lg_r290_service | grep "modbus_client"
```

**Verify adjustment threshold:**
If calculated temp is only 1°C different, no adjustment happens (threshold is 2°C).

### Heating curve selection incorrect

**Check target room temperature:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status | jq .config.target_temp
```

**Curve selection:**
- ≤21°C → ECO
- 21-23°C → Comfort
- >23°C → High Demand

**If using fallback (21°C), curve will be ECO.**

## Performance Tuning

### Adjustment Threshold

Default: 2°C - Only adjust if calculated temp differs by ≥2°C

**Increase** (e.g., 3°C) to reduce adjustments:
```json
"adjustment_threshold": 3
```

**Decrease** (e.g., 1°C) for tighter control:
```json
"adjustment_threshold": 1
```

### Update Interval

Default: 30 seconds

**Increase** (e.g., 60s) to reduce Modbus traffic:
```json
"update_interval_seconds": 60
```

**Decrease** (e.g., 15s) for faster response:
```json
"update_interval_seconds": 15
```

### Cutoff Temperature

Default: 18°C - Heat pump turns OFF above this

**Adjust for climate:**
```json
"outdoor_cutoff_temp": 16  // Turn off at 16°C instead
```

## Logging

AI Mode logs are prefixed with `adaptive_controller`:

**INFO Level:**
```
2025-10-11 10:30:00 - adaptive_controller - INFO - Adaptive controller started
2025-10-11 10:30:30 - adaptive_controller - INFO - AI Mode: Adjusted flow temperature 38°C → 40°C
2025-10-11 14:00:00 - adaptive_controller - INFO - Outdoor temp ≥18°C - Turning heat pump OFF
```

**DEBUG Level** (enable in main.py):
```
2025-10-11 10:30:00 - heating_curve - DEBUG - Selected curve: Comfort Mode (21-23°C)
2025-10-11 10:30:00 - heating_curve - DEBUG - Outdoor 5.0°C in range 0-10°C → flow 40°C
```

## Safety Features

1. **Temperature Limits**: Flow temp clamped to 30-50°C (hardware safe range)
2. **Graceful Fallback**: Uses default 21°C if thermostat unavailable
3. **No Crash Policy**: Exceptions caught and logged, AI Mode continues
4. **Hysteresis**: Prevents rapid ON/OFF cycling at cutoff temperature
5. **Power-On Delay**: Waits 2 seconds after turning heat pump ON before adjusting

## Related Documentation

- [Scheduler](SCHEDULER.md) - Time-based room temperature scheduling
- [Heat Pump Control](HEAT_PUMP_CONTROL.md) - Manual water temperature control
- [Thermostat Integration](THERMOSTAT_INTEGRATION.md) - Room temperature control
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Deployment](DEPLOYMENT.md) - Docker setup and environment variables
