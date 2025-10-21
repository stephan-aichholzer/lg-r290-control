# Architecture Documentation

## System Overview

The LG R290 Heat Pump Control System is a containerized, microservices-based architecture designed for monitoring and controlling an LG R290 7kW heat pump via Modbus TCP protocol. The system provides a clean separation of concerns with three main services that can run in development (mock) or production (real hardware) modes.

## Design Goals

1. **Testability**: Develop and test without physical hardware using a JSON-backed mock
2. **Modularity**: Clean separation between Modbus communication, business logic, and UI
3. **Maintainability**: Simple, well-documented codebase with standard technologies
4. **Portability**: Containerized deployment on Raspberry Pi or any Docker-capable platform
5. **Extensibility**: Easy to add new sensors, controls, and integrations

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Layer                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Web Browser (HTML5 + JavaScript)             │  │
│  │  - Gauges (Temperature visualization)                │  │
│  │  - Controls (ON/OFF, Temperature setpoint)           │  │
│  │  - Real-time status updates (2s polling)             │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP REST API
                            │ (Port 8080 → 80)
┌───────────────────────────▼─────────────────────────────────┐
│                     Presentation Layer                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           heatpump-ui (Nginx Container)              │  │
│  │  - Static file serving                               │  │
│  │  - Reverse proxy capability                          │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST API Calls
                            │ (Port 8000)
┌───────────────────────────▼─────────────────────────────────┐
│                      Application Layer                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      heatpump-service (FastAPI Container)            │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │         REST API Endpoints (main.py)            │ │  │
│  │  │  - GET /status: Current heat pump state         │ │  │
│  │  │  - POST /power: Power control                   │ │  │
│  │  │  - POST /setpoint: Temperature setpoint         │ │  │
│  │  │  - GET /health: Health check                    │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │                         │                             │  │
│  │  ┌─────────────────────▼───────────────────────────┐ │  │
│  │  │   HeatPumpModbusClient (modbus_client.py)       │ │  │
│  │  │  - AsyncModbusTcpClient wrapper                 │ │  │
│  │  │  - Register mapping and conversion              │ │  │
│  │  │  - Background polling (5s interval)             │ │  │
│  │  │  - Cached data store                            │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │ Modbus TCP
                            │ (Port 502/5020)
┌───────────────────────────▼─────────────────────────────────┐
│                     Modbus Protocol Layer                   │
│                                                             │
│  ┌────────────────────┐         ┌─────────────────────────┐│
│  │  heatpump-mock     │   OR    │  Real Hardware          ││
│  │  (pymodbus server) │         │  (Waveshare Gateway)    ││
│  │                    │         │                         ││
│  │  - Port 5020       │         │  - LG R290 Heat Pump    ││
│  │  - JSON backend    │         │  - RS485 Modbus         ││
│  │  - registers.json  │         │  - Port 502             ││
│  └────────────────────┘         └─────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Service Details

### 1. heatpump-mock (Mock Modbus Server)

**Purpose**: Simulate the LG R290 heat pump Modbus interface for development and testing.

**Technology**: Python 3.11, pymodbus 3.6.4

**Key Features**:
- Async Modbus TCP server (pymodbus `StartAsyncTcpServer`)
- JSON-backed register storage (`registers.json`)
- Supports all Modbus function codes: Coils, Discrete Inputs, Input Registers, Holding Registers
- Automatic persistence: Write operations update the JSON file
- Configurable device identification

**Data Flow**:
1. Loads initial register values from `registers.json` on startup
2. Serves Modbus requests on port 5020 (or 502)
3. Writes are synchronized back to JSON file for persistence
4. JSON file can be manually edited for testing different scenarios

**Files**:
- `mock/modbus_server.py`: Main server implementation
- `mock/registers.json`: Register definitions and values
- `mock/Dockerfile`: Container build configuration

**Configuration**:
- Port: 502 (internal), 5020 (external)
- Unit ID: 1
- Register file: `/app/registers.json` (mounted volume)

### 2. heatpump-service (FastAPI Backend)

**Purpose**: Provide REST API for heat pump monitoring and control, abstracting Modbus complexity.

**Technology**: Python 3.11, FastAPI 0.109, pymodbus 3.6.4

**Key Features**:
- Async REST API with automatic OpenAPI documentation
- Background polling task (configurable interval, default 5s)
- In-memory cache for fast response times
- Modbus connection management with reconnection logic
- Register value conversion (e.g., 0.1°C scaling)
- CORS enabled for web UI access
- AI Mode: Adaptive heating curve control with weather compensation
- Thermostat integration for room temperature feedback

**Data Flow**:
1. On startup: Connect to Modbus TCP server (mock or real)
2. Background task: Poll all configured registers every 5 seconds
3. Cache: Store latest values in memory
4. API requests: Serve cached data (fast, non-blocking)
5. Write operations: Direct Modbus write + immediate cache update

**API Endpoints**:

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| GET | `/status` | Current heat pump state | - | HeatPumpStatus |
| POST | `/power` | Power control | PowerControl | Status message |
| POST | `/setpoint` | Set target temperature | TemperatureSetpoint | Status message |
| GET | `/health` | Health check | - | Health status |
| GET | `/registers/raw` | Raw register data (debug) | - | Raw values |
| GET | `/ai-mode` | AI mode status and diagnostics | - | AI mode status |
| POST | `/ai-mode` | Enable/disable AI mode | AIModeControl | Status message |
| POST | `/ai-mode/reload-config` | Hot-reload heating curve config | - | Status message |

**Files**:
- `service/main.py`: FastAPI application and endpoints
- `service/modbus_client.py`: Modbus TCP client wrapper
- `service/heating_curve.py`: Heating curve configuration and calculation
- `service/adaptive_controller.py`: AI mode autonomous control loop
- `service/config.json`: Heating curve configuration (user-editable)
- `service/Dockerfile`: Container build configuration

**Configuration** (Environment Variables):
- `MODBUS_HOST`: Modbus server address (default: `heatpump-mock`)
- `MODBUS_PORT`: Modbus TCP port (default: `502`)
- `MODBUS_UNIT_ID`: Modbus unit/slave ID (default: `1`)
- `POLL_INTERVAL`: Polling interval in seconds (default: `5`)
- `THERMOSTAT_API_URL`: External thermostat API URL (default: `http://192.168.2.11:8001`)

### 3. heatpump-ui (Web Interface)

**Purpose**: User-friendly web interface for monitoring and controlling the heat pump.

**Technology**: HTML5, CSS3, Vanilla JavaScript, Nginx

**Key Features**:
- Responsive design (mobile and desktop)
- Real-time updates (2-second polling)
- Visual gauges for temperature monitoring
- Interactive controls (buttons, sliders)
- Connection status indicator
- Error notifications

**UI Components**:

1. **Header**
   - Title and connection status badge

2. **Power Control**
   - ON/OFF buttons
   - Status indicators (power, compressor)

3. **Temperature Gauges** (SVG-based)
   - Flow temperature (0-80°C)
   - Return temperature (0-80°C)
   - Outdoor temperature (-20-40°C)
   - Color-coded (blue/orange/red based on value)

4. **System Metrics**
   - Flow rate (L/min)
   - Water pressure (bar)
   - Operating mode

5. **Temperature Setpoint Control**
   - Slider (20-60°C, 0.5°C steps)
   - Set button with confirmation

6. **Error Display**
   - Conditional display on error
   - Error code and message

**Data Flow**:
1. JavaScript polls `/status` endpoint every 2 seconds
2. Update UI elements with new data
3. User interactions trigger POST requests
4. Immediate UI feedback + data refresh

**Files**:
- `ui/index.html`: HTML structure
- `ui/style.css`: Styling and responsive design
- `ui/app.js`: Application entry point
- `ui/config.js`: Configuration module (API URLs, polling intervals, thermostat defaults)
- `ui/utils.js`: Utility functions (API requests, gauge rendering, connection status)
- `ui/heatpump.js`: Heat pump control module (power, setpoint, AI mode)
- `ui/thermostat.js`: Thermostat control module (modes, temperature adjustment)
- `ui/Dockerfile`: Nginx container configuration

### 4. AI Mode (Adaptive Heating Curve)

**Purpose**: Autonomous flow temperature optimization based on outdoor temperature and target room temperature using weather compensation heating curves.

**Technology**: Python 3.11, httpx (for thermostat API integration)

**Key Features**:
- Three heating curves: ECO (≤21°C), Comfort (21-23°C), High (>23°C)
- Weather compensation: Adjusts flow temperature based on outdoor conditions
- Thermostat integration: Uses target room temperature to select appropriate curve
- JSON-based configuration: User-editable heating curves and parameters
- Hot-reload capability: Update configuration without service restart
- Autonomous operation: Runs every 10 minutes when enabled
- Safety features: Min/max temperature limits, hysteresis, adjustment thresholds
- UI integration: Manual/AI toggle switch with slider disable when AI active

**Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│              Adaptive Controller (Background Task)          │
│                                                             │
│  Every 10 minutes (when AI Mode enabled):                  │
│                                                             │
│  1. Read outdoor temperature ──────► Modbus (Heat Pump)   │
│                                                             │
│  2. Read target room temperature ──► HTTP (Thermostat API) │
│                                                             │
│  3. Select heating curve ──────────► heating_curve.py      │
│     - ECO: target ≤ 21°C                                    │
│     - Comfort: 21°C < target ≤ 23°C                         │
│     - High: target > 23°C                                   │
│                                                             │
│  4. Calculate optimal flow temp ───► Based on outdoor temp  │
│     - Outdoor < -10°C: 46-50°C (curve dependent)            │
│     - Outdoor < 0°C: 43-47°C                                │
│     - Outdoor < 10°C: 38-42°C                               │
│     - Outdoor < 18°C: 33-37°C                               │
│     - Outdoor ≥ 18°C: Heat pump OFF                         │
│                                                             │
│  5. Adjust if needed ──────────────► Modbus write           │
│     - Only if |current - optimal| > 2°C (threshold)         │
│     - Apply safety limits (30-50°C)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Configuration** (`config.json`):
```json
{
  "heating_curves": {
    "eco": { "target_temp_range": [0, 21.0], "curve": [...] },
    "comfort": { "target_temp_range": [21.0, 23.0], "curve": [...] },
    "high": { "target_temp_range": [23.0, 999], "curve": [...] }
  },
  "settings": {
    "outdoor_cutoff_temp": 18.0,
    "outdoor_restart_temp": 17.0,
    "update_interval_seconds": 600,
    "min_flow_temp": 30.0,
    "max_flow_temp": 50.0,
    "adjustment_threshold": 2.0,
    "hysteresis_outdoor": 1.0
  }
}
```

**Data Flow**:
1. User toggles AI mode via UI switch
2. POST `/ai-mode` enables adaptive controller
3. Background loop wakes every 10 minutes
4. Fetches outdoor temp (from heat pump) and target room temp (from thermostat)
5. Calculates optimal flow temperature using heating curves
6. Writes new setpoint to heat pump if adjustment needed
7. UI polls `/ai-mode` status to display diagnostics

**UI Components**:
- Manual/AI toggle switch (in Power Control panel)
- Status text: "Manual Control" / "AI Mode Active"
- Temperature slider: Disabled when AI mode active
- Visual feedback: Green text when AI active, gray when manual

## Modbus Register Mapping

### Register Types and Addressing

| Type | Function Code | Modbus Addr | API Addr | R/W | Description |
|------|---------------|-------------|----------|-----|-------------|
| Coil | 0x01 | 00001 | 0 | R/W | Power ON/OFF |
| Discrete | 0x02 | 10001-10017 | 0-16 | R | Status flags |
| Input | 0x03 | 30001-30014 | 0-13 | R | Sensor readings |
| Holding | 0x04 | 40001-40025 | 0-24 | R/W | Configuration |

### Key Registers (Initial Implementation)

**Control Registers**:
- Coil 0 (00001): Enable/Disable (Heating/Cooling)
- Holding 2 (40003): Target Temperature Circuit 1 (0.1°C × 10)

**Status Registers**:
- Discrete 3 (10004): Compressor Status (0=OFF, 1=ON)
- Discrete 13 (10014): Error Flag

**Sensor Registers**:
- Input 0 (30001): Error Code
- Input 1 (30002): Operating Mode (0=Standby, 1=Cooling, 2=Heating)
- Input 2 (30003): Return Temperature / Inlet (0.1°C × 10) - colder water from system
- Input 3 (30004): Flow Temperature / Outlet (0.1°C × 10) - hotter water to system
- Input 8 (30009): Flow Rate (0.1 LPM × 10)
- Input 12 (30013): Outdoor Temperature (0.1°C × 10)
- Input 13 (30014): Water Pressure (0.1 bar × 10)

## Deployment

### Docker Compose Network

All services run on a custom bridge network (`heatpump-net`):

- Enables service discovery by name (e.g., `heatpump-mock`, `heatpump-service`)
- Isolated from host network for security
- Port mapping only where external access is needed

### Port Mapping

| Service | Internal Port | External Port | Purpose |
|---------|---------------|---------------|---------|
| heatpump-mock | 502 | 5020 | Modbus TCP (mock) |
| heatpump-service | 8000 | 8000 | REST API |
| heatpump-ui | 80 | 8080 | Web UI |

### Volume Mounts

- `./mock/registers.json` → `/app/registers.json`: Persistent register state

## Development vs. Production Mode

### Development Mode (Default)

```yaml
MODBUS_HOST=heatpump-mock
MODBUS_PORT=502
```

- All three services run
- Mock server simulates heat pump
- Edit `registers.json` to test different scenarios
- No physical hardware required

### Production Mode

```yaml
MODBUS_HOST=192.168.1.100  # Waveshare gateway IP
MODBUS_PORT=502
```

- Only `heatpump-service` and `heatpump-ui` run
- Remove/comment `heatpump-mock` from docker-compose
- Connect to real LG R290 via Waveshare RS485 gateway

## Data Flow Examples

### Example 1: UI Requests Status

```
1. Browser → GET http://localhost:8000/status
2. FastAPI → Return cached data (no Modbus call needed)
3. Browser → Update UI elements
   - Set gauge values
   - Update text fields
   - Set colors/styles
```

### Example 2: User Turns Heat Pump ON

```
1. Browser → POST http://localhost:8000/power {"power_on": true}
2. FastAPI → await client.write_coil(0, True, slave=1)
3. Modbus Server → Update coil register
4. Mock → Save to registers.json
5. FastAPI → Update cache immediately
6. FastAPI → Return success response
7. Browser → Poll status (500ms later)
8. Browser → Update power status to "ON"
```

### Example 3: Background Polling

```
Every 5 seconds:
1. FastAPI background task → Read all configured registers
2. Modbus Server → Return current values
3. FastAPI → Update in-memory cache
4. UI (next poll) → Receive updated values
```

## Extension Points

### Adding New Sensors/Actuators

1. **Update Mock** (`mock/registers.json`):
   ```json
   "input_registers": {
     "30015": {
       "address": 14,
       "description": "New Sensor",
       "value": 123,
       "unit": "units"
     }
   }
   ```

2. **Update Modbus Client** (`service/modbus_client.py`):
   ```python
   INPUT_NEW_SENSOR = 14  # 30015

   # In _update_cached_data():
   self._cached_data['new_sensor'] = input_result.registers[self.INPUT_NEW_SENSOR]
   ```

3. **Update API** (`service/main.py`):
   ```python
   class HeatPumpStatus(BaseModel):
       new_sensor: int
   ```

4. **Update UI** (`ui/index.html`, `ui/app.js`):
   - Add HTML element
   - Update in JavaScript `updateUI()` function

### Adding Data Logging

Add a time-series database service to docker-compose:

```yaml
services:
  influxdb:
    image: influxdb:2.7
    volumes:
      - influxdb-data:/var/lib/influxdb2
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
```

Modify `service/main.py` to write to InfluxDB in the polling loop.

### Adding MQTT Integration

Add MQTT broker and publish status updates:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
```

Add MQTT client to `service/modbus_client.py` to publish status updates.

### Adding Home Assistant Integration

Use MQTT discovery or REST API integration:

```yaml
# configuration.yaml
sensor:
  - platform: rest
    resource: http://192.168.1.100:8000/status
    name: Heat Pump Flow Temperature
    value_template: '{{ value_json.flow_temperature }}'
```

## Security Considerations

### Current State (Development Focus)
- No authentication/authorization
- CORS enabled for all origins
- Suitable for trusted local networks only

### Production Recommendations
1. Add API authentication (JWT tokens, API keys)
2. Enable HTTPS (TLS/SSL certificates)
3. Restrict CORS to specific origins
4. Firewall rules (only allow local network access)
5. Read-only vs. read-write user roles
6. Rate limiting on API endpoints

## Performance Characteristics

- **API Response Time**: < 10ms (cached data)
- **Modbus Polling Cycle**: 5 seconds (configurable)
- **UI Update Rate**: 2 seconds
- **Modbus Transaction Time**: ~50-100ms per request
- **Memory Usage**: ~50MB per service
- **CPU Usage**: Minimal (< 5% on Raspberry Pi 5)

## Error Handling

### Connection Failures
- Modbus client: Automatic reconnection on disconnect
- UI: Display "Disconnected" status, continue polling
- API: Return 503 Service Unavailable

### Invalid Requests
- API validates input (Pydantic models)
- Temperature range: 20-60°C enforced
- Returns 400 Bad Request with error details

### Hardware Errors
- Error codes from heat pump displayed in UI
- Logged to service logs for debugging
- No automatic recovery (requires manual intervention)

## Logging

All services log to stdout (Docker logs):

```bash
# View logs
docker-compose logs -f [service-name]

# Log levels
- INFO: Normal operations, status updates
- WARNING: Recoverable issues
- ERROR: Failures, exceptions
- DEBUG: Detailed Modbus communication (set LOG_LEVEL=DEBUG)
```

## Testing Strategy

1. **Unit Tests**: Test Modbus client and API endpoints independently
2. **Integration Tests**: Test full stack with mock server
3. **Manual Testing**: Edit `registers.json` to simulate edge cases
4. **Load Testing**: Verify performance under continuous polling
5. **Hardware Testing**: Final validation with real LG R290

## Future Enhancements

- [ ] Historical data logging and visualization
- [ ] Advanced scheduling (time-based, outdoor temp-based)
- [ ] Multi-zone support (Circuit 2 integration)
- [ ] Energy consumption tracking
- [ ] Mobile app (React Native or PWA)
- [ ] Alert notifications (email, SMS, push)
- [ ] Integration with weather APIs
- [ ] Machine learning for optimization
- [ ] Multi-language support in UI
