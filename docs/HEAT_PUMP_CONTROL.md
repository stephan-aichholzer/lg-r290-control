# Heat Pump Control - Manual Water Temperature Management

## Overview

The Heat Pump Control provides direct manual control over the LG R290 heat pump via Modbus TCP protocol. It allows users to monitor real-time status and adjust water flow temperature and power state through a web interface or REST API.

**Key Features:**
- Real-time status monitoring (temperatures, flow rate, pressure)
- Manual power control (ON/OFF)
- Water temperature setpoint adjustment (20-60°C)
- Modbus TCP communication (async, non-blocking)
- Background polling (every 5 seconds)
- Mock mode for development/testing
- Production mode for real hardware

## How It Works

### Communication Protocol

The system uses **Modbus TCP** to communicate with the heat pump:

1. **Connection**: Establishes async TCP connection to heat pump (or mock server)
2. **Polling**: Background task reads status every 5 seconds
3. **Caching**: Stores latest values for fast API responses
4. **Write Operations**: User commands (power, temperature) written via Modbus
5. **Verification**: Status polled immediately after write to confirm change

### Register Mapping

#### Coils (Read/Write - Digital Outputs)

| Address | Register | Description | Values |
|---------|----------|-------------|--------|
| 00001 | COIL_POWER | Heat pump enable/disable | 0=OFF, 1=ON |

#### Discrete Inputs (Read-Only - Digital Inputs)

| Address | Register | Description | Values |
|---------|----------|-------------|--------|
| 10002 | DISCRETE_WATER_PUMP | Water pump status | 0=OFF, 1=ON |
| 10004 | DISCRETE_COMPRESSOR | Compressor status | 0=OFF, 1=ON |
| 10014 | DISCRETE_ERROR | Error flag | 0=No error, 1=Error |

#### Input Registers (Read-Only - Analog Inputs)

| Address | Register | Description | Unit | Conversion |
|---------|----------|-------------|------|------------|
| 30001 | INPUT_ERROR_CODE | Error code | - | Direct |
| 30002 | INPUT_OPERATING_MODE | ODU operating cycle | - | Enum decode |
| 30003 | INPUT_RETURN_TEMP | Water inlet (return) temperature | °C | Value / 10 |
| 30004 | INPUT_FLOW_TEMP | Water outlet (flow) temperature | °C | Value / 10 |
| 30009 | INPUT_FLOW_RATE | Current flow rate | L/min | Value / 10 |
| 30013 | INPUT_OUTDOOR_TEMP | Outdoor air temperature | °C | Value / 10 |
| 30014 | INPUT_WATER_PRESSURE | Water pressure | bar | Value / 10 |

#### Holding Registers (Read/Write - Analog Outputs)

| Address | Register | Description | Unit | Conversion |
|---------|----------|-------------|------|------------|
| 40001 | HOLDING_OP_MODE | Operating mode | - | Enum |
| 40003 | HOLDING_TARGET_TEMP | Target temperature circuit 1 | °C | Value × 10 |

### Operating Modes

| Code | Mode | Description |
|------|------|-------------|
| 0 | Standby | Heat pump idle |
| 1 | Heating | Active heating cycle |
| 2 | Cooling | Active cooling cycle |
| 3 | Defrost | Defrost cycle |
| 4 | Hot Water | DHW mode |

## Configuration

### Environment Variables

Configured in `docker-compose.yml`:

```yaml
environment:
  - MODBUS_HOST=${MODBUS_HOST:-heatpump-mock}  # Modbus TCP host
  - MODBUS_PORT=${MODBUS_PORT:-502}            # Modbus TCP port
  - MODBUS_UNIT_ID=${MODBUS_UNIT_ID:-1}        # Modbus slave ID
  - POLL_INTERVAL=${POLL_INTERVAL:-5}          # Status polling interval (seconds)
```

### Development Mode (Mock)

Uses mock Modbus server for testing without hardware:

```yaml
MODBUS_HOST=heatpump-mock  # Docker container name
MODBUS_PORT=502            # Internal port
```

### Production Mode (Real Hardware)

Connects to real LG R290 via Waveshare gateway:

```yaml
MODBUS_HOST=192.168.2.100  # Heat pump IP address
MODBUS_PORT=502            # Standard Modbus port
```

## API Endpoints

### Get Heat Pump Status

```http
GET /status
```

**Response:**
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

### Set Power State

```http
POST /power
Content-Type: application/json

{
  "power_on": true
}
```

**Response:**
```json
{
  "status": "success",
  "power_on": true
}
```

### Set Temperature Setpoint

```http
POST /setpoint
Content-Type: application/json

{
  "temperature": 45.0
}
```

**Validation:**
- Range: 20.0 - 60.0°C
- Returns 400 error if out of range

**Response:**
```json
{
  "status": "success",
  "target_temperature": 45.0
}
```

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "modbus_connected": true
}
```

Returns 503 if Modbus not connected.

### Get Raw Registers (Debug)

```http
GET /registers/raw
```

**Response:**
```json
{
  "coils": {"00001": true},
  "discrete_inputs": {"10002": true, "10004": true, "10014": false},
  "input_registers": {
    "30001": 0,
    "30002": 1,
    "30003": 300,
    "30004": 450,
    ...
  },
  "holding_registers": {
    "40001": 4,
    "40003": 400
  }
}
```

## Architecture

### Component Structure

```
┌─────────────────────────────────────────────────────────┐
│  main.py (FastAPI Application)                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  REST API Endpoints                               │  │
│  │  - GET /status                                    │  │
│  │  - POST /power                                    │  │
│  │  - POST /setpoint                                 │  │
│  │  - GET /health                                    │  │
│  └───────────────────────────────────────────────────┘  │
│                        │                                 │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  modbus_client.py (HeatPumpModbusClient)         │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Background Polling Task (every 5s)         │ │  │
│  │  │  - Read coils (power state)                 │ │  │
│  │  │  - Read discrete inputs (pump, compressor)  │ │  │
│  │  │  - Read input registers (temps, flow, etc)  │ │  │
│  │  │  - Read holding registers (mode, target)    │ │  │
│  │  │  - Update cached data                       │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Write Operations                           │ │  │
│  │  │  - write_coil() - Power ON/OFF             │ │  │
│  │  │  - write_register() - Set temperature      │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────┐ │  │
│  │  │  Cached Data Store                          │ │  │
│  │  │  - Fast API responses (no Modbus delay)    │ │  │
│  │  │  - Async lock for thread safety            │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │ Modbus TCP
                            ↓
┌─────────────────────────────────────────────────────────┐
│  Heat Pump / Mock Server                                │
│  - Modbus TCP Server (port 502)                         │
│  - LG R290 7kW Heat Pump                                │
│  - Waveshare RS485 to Ethernet Gateway                  │
└─────────────────────────────────────────────────────────┘
```

### Initialization Flow

1. `main.py` reads environment variables on startup
2. Creates `HeatPumpModbusClient` instance
3. `await modbus_client.connect()` establishes Modbus TCP connection
4. `modbus_client.start_polling()` starts background polling task
5. Background task runs every 5 seconds, updating cached data
6. API endpoints use cached data for fast responses

### Write Operation Flow

1. User clicks power button or adjusts temperature slider
2. UI sends POST request to API
3. API calls `modbus_client.set_power()` or `set_target_temperature()`
4. Modbus client writes to coil/register
5. Write acknowledged by heat pump
6. API triggers immediate status update (500ms delay)
7. UI polls status and updates display

## User Interface

### Dashboard Display

**Temperature Gauges:**
- Flow Temperature (30-80°C range)
- Return Temperature (20-70°C range)
- Outdoor Temperature (-20-40°C range)

**Status Indicators:**
- Heat Pump: ON/OFF (green dot)
- Compressor: ON/OFF (green dot)
- Circulation Pump: ON/OFF (green dot)

**Controls:**
- Power Switch: Toggle heat pump ON/OFF
- Temperature Slider: Adjust target water temperature (33-50°C)
  - Disabled when AI Mode active
  - Real-time value display

### Polling Behavior

**UI → API:**
- Status updates every 10 seconds
- Immediate refresh 500ms after user action

**API → Heat Pump:**
- Background polling every 5 seconds
- Immediate read after write operations

## Use Cases

### Manual Temperature Adjustment

**Scenario**: User wants warmer water

```
1. User drags slider to 45°C
2. UI updates display immediately (optimistic)
3. POST /setpoint {"temperature": 45.0}
4. API writes to register 40003 (value: 450)
5. Heat pump acknowledges write
6. API returns success
7. After 500ms, UI polls GET /status
8. Confirms target_temperature: 45.0
```

### Power Control

**Scenario**: User turns heat pump ON

```
1. User clicks power switch to ON
2. UI updates switch state (optimistic)
3. POST /power {"power_on": true}
4. API writes to coil 00001 (value: 1)
5. Heat pump powers on
6. API returns success
7. After 500ms, UI polls GET /status
8. Confirms is_on: true, compressor_running: true
```

### Status Monitoring

**Scenario**: User monitors heat pump operation

```
Every 10 seconds:
1. UI polls GET /status
2. API returns cached data (fast, no Modbus delay)
3. UI updates:
   - Temperature gauges
   - Status dots
   - Flow rate, pressure

Background (every 5 seconds):
1. Modbus client polls heat pump
2. Updates cached data
3. UI sees fresh data on next poll
```

## Mock Server

### Purpose

Enables development and testing without physical hardware.

### Features

- **JSON-backed registers**: Edit `mock/registers.json` to simulate scenarios
- **Full Modbus support**: Coils, discrete inputs, input registers, holding registers
- **Persistence**: Writes update JSON file automatically
- **Realistic behavior**: Simulates heat pump responses

### Configuration

**mock/registers.json:**
```json
{
  "coils": {"00001": false},
  "discrete_inputs": {
    "10002": false,
    "10004": false,
    "10014": false
  },
  "input_registers": {
    "30001": 0,
    "30002": 0,
    "30003": 300,
    "30004": 450,
    "30009": 125,
    "30013": 50,
    "30014": 15
  },
  "holding_registers": {
    "40001": 4,
    "40003": 350
  }
}
```

### Testing Scenarios

**Simulate heating mode:**
```json
{
  "coils": {"00001": true},
  "discrete_inputs": {"10002": true, "10004": true},
  "input_registers": {
    "30002": 1,    // Heating mode
    "30003": 350,  // Return 35°C
    "30004": 450,  // Flow 45°C
    ...
  }
}
```

**Simulate error:**
```json
{
  "discrete_inputs": {"10014": true},  // Error flag
  "input_registers": {"30001": 15}     // Error code 15
}
```

## Troubleshooting

### Connection Issues

**Symptom**: `GET /health` returns 503

**Check Modbus connection:**
```bash
docker logs lg_r290_service | grep "modbus_client"
```

**Look for:**
```
Connected to Modbus TCP at heatpump-mock:502
```

**If connection fails:**
- Verify MODBUS_HOST is reachable
- Check MODBUS_PORT is correct
- Test network: `docker exec lg_r290_service ping heatpump-mock`
- Check mock server: `docker ps | grep mock`

### Write Operations Failing

**Symptom**: POST /power or /setpoint returns 500 error

**Check logs:**
```bash
docker logs lg_r290_service | grep "error\|Error"
```

**Common causes:**
- Modbus not connected
- Heat pump not responding
- Register address incorrect
- Value out of range

**Verify with raw registers:**
```bash
curl http://localhost:8002/registers/raw | jq .
```

### Temperature Not Changing

**Symptom**: Slider moves but temperature stays same

**Check:**
1. AI Mode is disabled (slider should be enabled)
2. Target temperature vs actual flow temperature
3. Heat pump must be ON to heat water
4. Compressor must run to reach temperature

**Monitor status:**
```bash
watch -n 2 'curl -s http://localhost:8002/status | jq .'
```

### Polling Stopped

**Symptom**: Status not updating

**Check background task:**
```bash
docker logs lg_r290_service | grep "polling" | tail -20
```

**Should see:**
```
Started polling task (interval: 5s)
Read input registers: [...]
Read holding registers: [...]
```

**If stopped, restart service:**
```bash
docker-compose restart heatpump-service
```

## Performance Considerations

### Polling Interval

Default: 5 seconds

**Increase** (e.g., 10s) to reduce Modbus traffic:
```yaml
POLL_INTERVAL=10
```

**Decrease** (e.g., 2s) for faster updates:
```yaml
POLL_INTERVAL=2
```

**Trade-off**: Lower interval = more responsive but higher network load

### Cached Data

All API responses use cached data from last poll:
- **Advantage**: Fast responses (no Modbus delay)
- **Limitation**: Data up to 5 seconds old

**Immediate refresh** after write operations (500ms delay).

### Connection Timeout

Default: 10 seconds

Modbus operations timeout after 10s to prevent hanging.

## Safety Features

1. **Temperature Limits**: 20-60°C enforced by API
2. **Connection Recovery**: Automatic reconnection on disconnect
3. **Error Handling**: All Modbus errors caught and logged
4. **Async Lock**: Prevents concurrent Modbus operations
5. **Cache Updates**: Immediate cache update after successful write
6. **Graceful Shutdown**: Clean disconnection on service stop

## Hardware Integration

### Waveshare RS485 to Ethernet Gateway

**Connection:**
```
LG R290 Heat Pump (RS485)
    ↕ (Modbus RTU)
Waveshare Gateway
    ↕ (Ethernet)
Raspberry Pi / Server (Modbus TCP)
```

**Gateway Configuration:**
- Protocol: Modbus RTU to TCP
- Baud rate: 9600 (typical for LG)
- Parity: None
- Data bits: 8
- Stop bits: 1
- TCP port: 502

### Register Verification

Before production use, verify register addresses with heat pump manual:

```bash
# Read all input registers
curl http://localhost:8002/registers/raw | jq '.input_registers'

# Test power control (OFF then ON)
curl -X POST http://localhost:8002/power -H "Content-Type: application/json" -d '{"power_on": false}'
sleep 5
curl -X POST http://localhost:8002/power -H "Content-Type: application/json" -d '{"power_on": true}'

# Monitor status
curl http://localhost:8002/status | jq .
```

## Related Documentation

- [AI Mode](AI_MODE.md) - Adaptive heating curve control (automatic)
- [Scheduler](SCHEDULER.md) - Time-based room temperature scheduling
- [Thermostat Integration](THERMOSTAT_INTEGRATION.md) - Room temperature control
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Deployment](DEPLOYMENT.md) - Docker setup and environment variables
