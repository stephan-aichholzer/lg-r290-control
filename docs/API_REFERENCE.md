# API Reference

Complete REST API documentation for LG R290 Heat Pump Control System.

**Base URL**: `http://localhost:8002` (or your deployment address)

---

## Heat Pump Control

### Get Status

Get current heat pump status and sensor readings.

```http
GET /status
```

**Response:** `200 OK`
```json
{
  "is_on": true,
  "water_pump_running": true,
  "compressor_running": true,
  "operating_mode": "Heating",
  "target_temperature": 40.0,
  "flow_temperature": 45.0,
  "return_temperature": 30.0,
  "flow_rate": 12.5,
  "outdoor_temperature": 5.0,
  "water_pressure": 1.5,
  "error_code": 0,
  "has_error": false
}
```

### Set Power

Turn heat pump ON or OFF.

```http
POST /power
Content-Type: application/json

{
  "power_on": true
}
```

**Response:** `200 OK`
```json
{
  "status": "success",
  "power_on": true
}
```

**Errors:**
- `503` - Modbus not connected
- `500` - Write failed

### Set Temperature Setpoint

Set target water temperature.

```http
POST /setpoint
Content-Type: application/json

{
  "temperature": 45.0
}
```

**Validation:**
- Min: 20.0°C
- Max: 60.0°C

**Response:** `200 OK`
```json
{
  "status": "success",
  "target_temperature": 45.0
}
```

**Errors:**
- `400` - Temperature out of range
- `503` - Modbus not connected
- `500` - Write failed

### Health Check

Check service and Modbus connection health.

```http
GET /health
```

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "modbus_connected": true
}
```

**Response:** `503 Service Unavailable`
```json
{
  "detail": "Modbus connection not available"
}
```

### Get Raw Registers (Debug)

Get raw Modbus register values.

```http
GET /registers/raw
```

**Response:** `200 OK`
```json
{
  "coils": {
    "00001": true
  },
  "discrete_inputs": {
    "10002": true,
    "10004": true,
    "10014": false
  },
  "input_registers": {
    "30001": 0,
    "30002": 1,
    "30003": 300,
    "30004": 450,
    "30009": 125,
    "30013": 50,
    "30014": 15
  },
  "holding_registers": {
    "40001": 4,
    "40003": 400
  }
}
```

---

## AI Mode (Adaptive Heating)

### Get AI Mode Status

Get current AI Mode status and calculated values.

```http
GET /ai-mode
```

**Response:** `200 OK`
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

### Enable/Disable AI Mode

Toggle AI Mode on or off.

```http
POST /ai-mode
Content-Type: application/json

{
  "enabled": true
}
```

**Response:** `200 OK`
```json
{
  "status": "success",
  "ai_mode": true,
  "message": "AI Mode enabled"
}
```

### Reload Heating Curve Configuration

Hot-reload `heating_curve_config.json` without restart.

```http
POST /ai-mode/reload-config
```

**Response:** `200 OK`
```json
{
  "status": "success",
  "config_changed": true,
  "message": "Configuration reloaded successfully"
}
```

---

## Scheduler

### Get Scheduler Status

Get current scheduler status and time information.

```http
GET /schedule
```

**Response:** `200 OK`
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

**Response when disabled:** `200 OK`
```json
{
  "enabled": false,
  "message": "Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
}
```

### Reload Schedule Configuration

Hot-reload `schedule.json` without restart.

```http
POST /schedule/reload
```

**Response:** `200 OK`
```json
{
  "success": true,
  "enabled": true,
  "schedule_count": 2,
  "message": "Schedule reloaded successfully"
}
```

**Errors:**
- `503` - Scheduler disabled or not initialized

---

## Thermostat Integration (External API)

**Base URL**: `http://192.168.2.11:8001` (or your thermostat address)

### Get Thermostat Status

```http
GET /api/v1/thermostat/status
```

**Response:** `200 OK`
```json
{
  "config": {
    "mode": "AUTO",
    "target_temp": 22.0,
    "eco_temp": 19.0,
    "hysteresis": 0.1,
    "min_on_time": 40,
    "min_off_time": 10,
    "temp_sample_count": 4,
    "control_interval": 60
  },
  "switch_state": true,
  "all_temps": {
    "temp_indoor": 21.5,
    "temp_outdoor": 11.7
  },
  "active_target": 22.0
}
```

### Get Thermostat Configuration

```http
GET /api/v1/thermostat/config
```

**Response:** `200 OK`
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

### Set Thermostat Configuration

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

**Response:** `200 OK`
```json
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

---

## Common Response Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid input (temperature out of range, etc.) |
| `500` | Internal Server Error | Modbus write failed, unexpected error |
| `503` | Service Unavailable | Modbus not connected, service not initialized |

---

## Error Response Format

All errors follow this format:

```json
{
  "detail": "Error message describing the problem"
}
```

**Examples:**

```json
{
  "detail": "Temperature must be between 20.0 and 60.0°C"
}
```

```json
{
  "detail": "Modbus client not initialized"
}
```

```json
{
  "detail": "Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
}
```

---

## Usage Examples

### cURL

**Get status:**
```bash
curl http://localhost:8002/status | jq .
```

**Turn heat pump ON:**
```bash
curl -X POST http://localhost:8002/power \
  -H "Content-Type: application/json" \
  -d '{"power_on": true}'
```

**Set temperature:**
```bash
curl -X POST http://localhost:8002/setpoint \
  -H "Content-Type: application/json" \
  -d '{"temperature": 45.0}'
```

**Enable AI Mode:**
```bash
curl -X POST http://localhost:8002/ai-mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

**Reload schedule:**
```bash
curl -X POST http://localhost:8002/schedule/reload
```

### JavaScript (Fetch API)

**Get status:**
```javascript
const response = await fetch('http://localhost:8002/status');
const data = await response.json();
console.log(data.flow_temperature);
```

**Set power:**
```javascript
await fetch('http://localhost:8002/power', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({power_on: true})
});
```

### Python (requests)

**Get status:**
```python
import requests

response = requests.get('http://localhost:8002/status')
data = response.json()
print(f"Flow temp: {data['flow_temperature']}°C")
```

**Set temperature:**
```python
response = requests.post(
    'http://localhost:8002/setpoint',
    json={'temperature': 45.0}
)
print(response.json())
```

---

## Rate Limiting

No rate limiting currently implemented. Recommended client-side limits:

- Status polling: Every 10 seconds
- Write operations: Debounce user input (2 seconds)
- Configuration reloads: Manual only (not automated)

---

## CORS

CORS enabled for all origins:

```python
allow_origins=["*"]
```

Suitable for local network deployment. Restrict in production if needed.

---

## WebSocket Support

Not currently implemented. All communication via REST/HTTP polling.

---

## Related Documentation

- [Heat Pump Control](HEAT_PUMP_CONTROL.md) - Detailed Modbus register mapping
- [AI Mode](AI_MODE.md) - AI Mode configuration and behavior
- [Scheduler](SCHEDULER.md) - Schedule configuration format
- [Thermostat Integration](THERMOSTAT_INTEGRATION.md) - External thermostat API details
- [Deployment](DEPLOYMENT.md) - Environment variables and setup
