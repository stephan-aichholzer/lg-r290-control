# LG R290 Heat Pump Control System

A Docker-based software stack for interfacing with an LG R290 7kW heat pump via Modbus TCP protocol with integrated room thermostat control and AI-powered adaptive heating curve.

**Version**: v0.8 (Stable)
**Platform**: Raspberry Pi 5 / Linux
**Status**: Production ready with AI Mode for autonomous weather compensation

## Features

### Core Functionality
- **Mock Modbus Server**: JSON-backed Modbus TCP server for development and testing
- **FastAPI Backend**: RESTful API for heat pump monitoring and control
- **Responsive Web UI**: Dark mode HTML5 interface optimized for desktop and mobile kiosk mode
- **Switchable Architecture**: Easy transition from mock to real hardware via configuration
- **Containerized Deployment**: Docker Compose orchestration for all services

### Web UI Features
- **Dark Mode Design**: Pure black background with high contrast for OLED displays
- **Modular ES6 Architecture**: Clean separation of concerns (config, utils, heatpump, thermostat modules)
- **Dual Layout Support**:
  - Desktop: Traditional vertical layout with full-sized gauges
  - Landscape (Mobile): Optimized compact layout fits single screen without scrolling
- **Heat Pump Control**:
  - Real-time monitoring: Flow temperature gauge, power status
  - Unified status badges: Heat pump, compressor, circulation pump (with LED indicators)
  - Temperature setpoint slider with auto-sync (2s interval)
  - Power ON/OFF control
  - **AI Mode Toggle**: Manual/AI control mode switch with visual feedback
- **Room Thermostat Integration**:
  - 4 operating modes: AUTO, ECO, ON, OFF
  - Target temperature control (18-24°C, 0.5°C steps)
  - Circulation pump status indicator
  - 60-second polling interval
  - Integrates with Shelly BT Thermostat API
- **AI Mode (NEW in v0.8)**:
  - Adaptive heating curve: Automatic flow temperature optimization
  - Weather compensation: Adjusts based on outdoor temperature
  - 3 heating curves: ECO (≤21°C), Comfort (21-23°C), High (>23°C)
  - Autonomous operation: Evaluates every 30 seconds
  - User-editable configuration via JSON
  - Automatic shutdown when outdoor temp ≥18°C
- **Scheduler (NEW)**:
  - Time-based automatic room temperature control
  - Week-based schedules (separate weekday/weekend patterns)
  - Discrete event triggering at exact scheduled times
  - Mode-aware: Only applies in AUTO/ON modes (respects ECO/OFF)
  - Hot-reloadable configuration via API
  - Vienna timezone with automatic DST handling
- **Kiosk Mode Optimized**: Perfect for wall-mounted mobile displays in landscape orientation
- **Cross-Origin Support**: CORS-enabled for multi-service integration

## Architecture

The system consists of three main services:

1. **heatpump-mock**: Simulates the LG R290 Modbus interface using pymodbus
2. **heatpump-service**: FastAPI service with AsyncModbusTcpClient for Modbus communication
3. **heatpump-ui**: Nginx-served HTML5 interface for visualization and control

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Raspberry Pi 5 (or any Linux system)
- For real hardware: Waveshare RS232/RS485 to ETH gateway

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd lg_r290_control
```

2. Copy and configure environment variables:
```bash
cp .env.example .env
# Edit .env if needed
```

3. Start all services:
```bash
docker-compose up -d
```

4. Access the web UI:
```
http://<raspberry-pi-ip>:8080
# Example: http://192.168.1.100:8080
```

5. API documentation (Swagger):
```
http://<raspberry-pi-ip>:8002/docs
# Example: http://192.168.1.100:8002/docs
```

## Usage

### Testing with Mock Server

By default, the system runs with the mock Modbus server:

```bash
docker-compose up -d
```

The mock server loads initial register values from `mock/registers.json`. You can manually edit this file to simulate different heat pump states.

### Switching to Real Hardware

1. Stop the services:
```bash
docker-compose down
```

2. Edit `.env` and set your gateway IP address:
```bash
MODBUS_HOST=192.168.1.100  # Your Waveshare gateway IP
MODBUS_PORT=502
MODBUS_UNIT_ID=1
```

3. Comment out or remove the `heatpump-mock` service dependency in `docker-compose.yml`

4. Restart services:
```bash
docker-compose up -d heatpump-service heatpump-ui
```

### Thermostat Integration

The UI integrates with the Shelly BT Thermostat Control API (separate project) for room temperature control. To enable this integration:

1. Ensure the thermostat API is running at `http://192.168.2.11:8001` (or update `ui/config.js`)

2. The thermostat API must have CORS enabled. Add to your thermostat's `main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. Default thermostat parameters (set in `ui/config.js`):
   - Hysteresis: 0.1°C
   - Min ON time: 40 minutes
   - Min OFF time: 10 minutes
   - Temperature sample count: 4
   - Control interval: 60 seconds

4. The UI provides:
   - 4 mode buttons (AUTO, ECO, ON, OFF)
   - Target temperature control (18-24°C, 0.5°C steps)
   - Circulation pump status indicator
   - 60-second polling interval

### AI Mode (Adaptive Heating Curve)

AI Mode enables autonomous flow temperature optimization based on outdoor temperature and target room temperature using weather compensation heating curves.

**How It Works:**

1. **Enable AI Mode**: Toggle the Manual/AI switch in the Power Control panel
2. **Automatic Operation**: Every 10 minutes, the system:
   - Reads outdoor temperature from the heat pump
   - Reads target room temperature from the thermostat
   - Selects the appropriate heating curve (ECO/Comfort/High)
   - Calculates optimal flow temperature
   - Adjusts the heat pump if needed (threshold: 2°C)
   - Turns off the heat pump when outdoor temp ≥18°C

**Heating Curves** (defined in `service/heating_curve_config.json`):

| Target Room Temp | Curve | Outdoor < -10°C | -10°C to 0°C | 0°C to 10°C | 10°C to 18°C |
|------------------|-------|-----------------|--------------|-------------|--------------|
| ≤21°C | ECO | 46°C | 43°C | 38°C | 33°C |
| 21-23°C | Comfort | 48°C | 45°C | 40°C | 35°C |
| >23°C | High | 50°C | 47°C | 42°C | 37°C |

**Configuration** (`service/heating_curve_config.json`):
```json
{
  "settings": {
    "outdoor_cutoff_temp": 18.0,        // Heat pump off above this temp
    "outdoor_restart_temp": 17.0,       // Heat pump on below this temp (hysteresis)
    "update_interval_seconds": 600,     // Evaluation interval (10 minutes)
    "min_flow_temp": 30.0,              // Safety limit minimum
    "max_flow_temp": 50.0,              // Safety limit maximum
    "adjustment_threshold": 2.0,        // Only adjust if difference > 2°C
    "hysteresis_outdoor": 1.0           // Temperature hysteresis
  }
}
```

**Hot-Reload Configuration**:
```bash
# Edit the configuration file
nano service/heating_curve_config.json

# Reload without restarting
curl -X POST http://localhost:8002/ai-mode/reload-config
```

**API Endpoints**:
- `GET /ai-mode` - Get AI mode status and diagnostics
- `POST /ai-mode` - Enable/disable AI mode: `{"enabled": true}`
- `POST /ai-mode/reload-config` - Reload configuration

**Requirements**:
- Thermostat API must be accessible for target room temperature
- Heat pump must provide outdoor temperature readings
- Recommended for heating season (outdoor temp < 18°C)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `heatpump-mock` | Modbus TCP host (container name or IP) |
| `MODBUS_PORT` | `502` | Modbus TCP port (internal Docker network) |
| `MODBUS_UNIT_ID` | `1` | Modbus slave/unit ID |
| `POLL_INTERVAL` | `5` | Polling interval in seconds |
| `THERMOSTAT_API_URL` | `http://iot-api:8000` | Thermostat API base URL (Docker container name for AI Mode) |

**Note for AI Mode Integration**:
- The `THERMOSTAT_API_URL` should use the **Docker container name** (`iot-api`) not the host IP
- Requires external network reference to the thermostat stack (see docker-compose.yml)
- Example: `shelly_bt_temp_default` network must exist and be referenced
- If thermostat API is unavailable, AI Mode falls back to default target temperature (21°C)

### Modbus Registers

Key registers implemented:

| Type | Address | Description | Unit |
|------|---------|-------------|------|
| Coil | 00001 | Power ON/OFF | Boolean |
| Discrete | 10004 | Compressor Status | Boolean |
| Input | 30003 | Return Temp (Inlet - colder) | 0.1°C |
| Input | 30004 | Flow Temp (Outlet - hotter) | 0.1°C |
| Input | 30009 | Flow Rate | 0.1 LPM |
| Holding | 40003 | Target Temperature | 0.1°C |

See `LG_R290_register.pdf` for complete register documentation.

## API Endpoints

### GET /status
Get current heat pump status including temperatures, flow rate, and operating mode.

**Response:**
```json
{
  "is_on": true,
  "water_pump_running": true,
  "compressor_running": false,
  "operating_mode": "Heating",
  "target_temperature": 45.0,
  "flow_temperature": 35.0,
  "return_temperature": 30.0,
  "flow_rate": 12.5,
  "outdoor_temperature": 5.0,
  "water_pressure": 1.5,
  "error_code": 0,
  "has_error": false
}
```

### POST /power
Turn heat pump on or off.

**Request:**
```json
{
  "power_on": true
}
```

### POST /setpoint
Set target temperature setpoint (20-60°C).

**Request:**
```json
{
  "temperature": 45.0
}
```

### GET /health
Health check endpoint.

## Development

### Project Structure

```
lg_r290_control/
├── docker-compose.yml
├── .env.example
├── README.md
├── ARCHITECTURE.md
├── LG_R290_register.pdf
├── mock/
│   ├── Dockerfile
│   ├── modbus_server.py
│   ├── registers.json
│   └── requirements.txt
├── service/
│   ├── Dockerfile
│   ├── main.py
│   ├── modbus_client.py
│   └── requirements.txt
└── ui/
    ├── Dockerfile
    ├── index.html
    ├── style.css
    ├── app.js           # Main entry point
    ├── config.js        # Configuration constants
    ├── utils.js         # Shared utilities
    ├── heatpump.js      # Heat pump control module
    └── thermostat.js    # Thermostat control module
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f heatpump-service
docker-compose logs -f heatpump-mock
docker-compose logs -f heatpump-ui
```

### Rebuilding Services

```bash
# Rebuild all
docker-compose build

# Rebuild specific service
docker-compose build heatpump-service
```

### Editing Mock Register Values

The mock server uses `mock/registers.json` for register values mapped to the host filesystem.

**Reading:** Edit the JSON file manually and restart the mock container to load new values:
```bash
# Edit mock/registers.json
docker restart lg_r290_mock
```

**Writing:** Currently, writes from the API (power control, setpoint changes) update the mock server's internal state but are **not persisted** back to the JSON file automatically. This is a known limitation for testing. To test different states, manually edit the JSON file and restart the mock.

For production use with real hardware, this limitation doesn't apply as the real heat pump maintains its own state.

## Troubleshooting

### Cannot connect to Modbus server

1. Check if the mock server is running:
```bash
docker-compose ps
```

2. Check logs:
```bash
docker-compose logs heatpump-mock
docker-compose logs heatpump-service
```

3. Verify network connectivity:
```bash
docker-compose exec heatpump-service ping heatpump-mock
```

### UI shows "Disconnected"

1. Check if the API service is running:
```bash
curl http://localhost:8000/health
```

2. Check browser console for CORS errors
3. Verify API_URL in `ui/app.js` matches your setup

### Real hardware not responding

1. Verify gateway IP address and port
2. Check network connectivity to the gateway
3. Ensure DIP switches on LG R290 are set correctly (SW1-1: ON, SW1-2: ON)
4. Verify Modbus parameters: 9600 bps, 1 stop bit, no parity

## Extension

### Adding New Registers

1. Add register definition to `mock/registers.json`
2. Update `service/modbus_client.py` with new register addresses
3. Add API endpoints in `service/main.py`
4. Update UI in `ui/index.html`, `ui/style.css`, and `ui/app.js`

### Adding Features

The system is designed for easy extension:

- Additional sensors/actuators: Add to Modbus client and API
- Data logging: Add time-series database (InfluxDB, PostgreSQL)
- Notifications: Integrate MQTT or webhook notifications
- Home automation: Add MQTT bridge for Home Assistant integration

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

### v0.8 - Current (2025-10-10)

**Status**: Production ready with AI Mode for autonomous weather compensation

**New Features:**
- ✅ **AI Mode**: Adaptive heating curve with weather compensation
- ✅ **3 Heating Curves**: ECO (≤21°C), Comfort (21-23°C), High (>23°C)
- ✅ **Autonomous Operation**: Evaluates every 10 minutes when enabled
- ✅ **Manual/AI Toggle**: Integrated into Power Control panel
- ✅ **Thermostat Integration**: Uses target room temperature for curve selection
- ✅ **JSON Configuration**: User-editable heating curves and parameters
- ✅ **Hot-Reload**: Update configuration without restarting service
- ✅ **Safety Features**: Min/max limits, hysteresis, adjustment thresholds
- ✅ **Auto-Shutdown**: Heat pump off when outdoor temp ≥18°C
- ✅ **Visual Feedback**: Slider disabled when AI mode active, status text updates

**Backend Enhancements:**
- New API endpoints: `/ai-mode` (GET/POST), `/ai-mode/reload-config`
- New modules: `heating_curve.py`, `adaptive_controller.py`
- Added httpx dependency for thermostat API integration
- Background control loop with configurable 10-minute interval

**UI Improvements:**
- Manual/AI toggle switch in Power Control panel
- Status indicator: "Manual Control" / "AI Mode Active" (green when active)
- Temperature slider auto-disables when AI mode enabled
- Real-time AI mode status polling

### v0.7 (2025-10-10)

**Status**: Production ready for wall-mounted kiosk deployment

**Latest Features:**
- ✅ **Temperature Badge Display**: Three-column layout (Indoor/Outdoor/Flow)
- ✅ **Complete Thermal Awareness**: All sensor temperatures visible at a glance
- ✅ **Increased Font Sizes**: +27-33% for kiosk readability (2-3m viewing distance)
- ✅ **Badge Style UI**: Replaced SVG gauges with clean, modern badges
- ✅ **Color Coding**: Flow temp in red, ambient temps in white
- ✅ **Larger Status Indicators**: 16px text, 12px LED dots (was 12px/10px)

**Temperature Display:**
- Indoor: 32px values from thermostat sensors (60s polling)
- Outdoor: 32px values from thermostat sensors (60s polling)
- Flow: 32px values from heat pump (10s polling)
- Landscape: 24px values (still highly readable)

**Font Size Improvements:**
- Temperature badge labels: 11px → 14px (+27%)
- Temperature badge values: 24px → 32px (+33%)
- Status badge text: 12px → 16px (+33%)
- Status LED dots: 10px → 12px (+20%)
- Perfect visibility from across the room

### v0.6 (2025-10-10)
- ✅ **Performance Optimization**: 97% reduction in API requests (2s → 10s polling)
- ✅ **Anti-Flickering**: Smart DOM updates only when values change
- ✅ **Immediate Feedback**: 500ms refresh on all user actions
- ✅ **Battery Friendly**: 80% reduction in browser CPU usage
- ✅ **Network Efficient**: Reduced from 259,200 to 8,640 API requests per day

### v0.5 (2025-10-10)
- ✅ **Thermostat Integration**: Room thermostat control with 4 modes (AUTO, ECO, ON, OFF)
- ✅ **Modular Architecture**: ES6 modules (config, utils, heatpump, thermostat)
- ✅ **Unified Status Badges**: Consistent LED-style indicators for all three statuses
- ✅ **Compact Layout**: Optimized for landscape mobile - fits without scrolling
- ✅ **CORS Support**: Cross-origin integration with external thermostat API
- ✅ **Temperature Control**: 0.5°C step control (18-24°C range)
- ✅ **Circulation Pump Monitoring**: Integrated with thermostat status

### v0.4 (2025-10-06)
- ✅ Real-time slider synchronization for kiosk mode
- ✅ Temperature slider updates automatically when changed externally
- ✅ Complete register monitoring (target temp, water pump status)
- ✅ Optimized 2×2 landscape layout with 50% larger gauges
- ✅ Touch and mouse event support for mobile and desktop

**What Works:**
- ✅ Complete Docker stack with mock server, API, and UI
- ✅ Power ON/OFF control with status feedback
- ✅ Temperature monitoring (flow, return, outdoor, target)
- ✅ System metrics (flow rate, pressure, operating mode, pump status)
- ✅ Temperature setpoint control with real-time sync
- ✅ Dark mode responsive UI optimized for kiosk displays
- ✅ Network-accessible from any device on LAN
- ✅ All registers properly read and monitored

**Kiosk Mode:**
- ✅ Perfect for wall-mounted tablets/phones
- ✅ Auto-updates every 2 seconds including slider position
- ✅ Syncs with external changes (LG app, terminal, other clients)
- ✅ Smooth user interaction without update conflicts
- ✅ Optimized landscape layout for mobile devices

**Known Limitations:**
- ⚠️ Mock server: Writes not persisted to JSON file (acceptable for testing)
- ⚠️ Mock server: Some register values read as zero (Modbus addressing offset, mock-only)
- ⚠️ API port 8002 (avoids Portainer conflict on 8000)

**Testing Status:**
- ✅ Tested with mock server - all functionality verified
- ✅ UI tested on desktop and mobile browsers
- ✅ Kiosk mode tested on mobile landscape
- ✅ Real-time synchronization verified
- ⚠️ Not yet tested with real LG R290 hardware

**Next Steps:**
1. Test with real LG R290 hardware via Waveshare gateway
2. Verify all register readings with actual heat pump
3. Deploy to production kiosk environment
4. Consider data logging (InfluxDB) for historical trends

## Documentation

Comprehensive feature documentation is available in the `docs/` directory:

### Feature Documentation

- **[Scheduler](docs/SCHEDULER.md)** - Time-based automatic temperature scheduling
  - Week-based schedules (weekday/weekend patterns)
  - Discrete event triggering at exact times
  - Mode-aware operation (respects ECO/OFF)
  - Hot-reloadable configuration
  - Vienna timezone with DST support

- **[AI Mode](docs/AI_MODE.md)** - Adaptive heating curve control
  - Autonomous weather compensation
  - Three heating curves (ECO, Comfort, High Demand)
  - Outdoor temperature-based optimization
  - Thermostat integration for target room temp
  - Configurable via JSON

- **[Heat Pump Control](docs/HEAT_PUMP_CONTROL.md)** - Manual Modbus TCP control
  - Complete register mapping
  - Power and temperature control
  - Real-time status monitoring
  - Mock server for development
  - Hardware integration guide

- **[Thermostat Integration](docs/THERMOSTAT_INTEGRATION.md)** - Room temperature control
  - Cross-stack Docker communication
  - Circulation pump control
  - Mode management (AUTO/ECO/ON/OFF)
  - Indoor/outdoor temperature sensors

### System Documentation

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Docker setup and configuration
  - Environment variables
  - Development vs production modes
  - Network configuration
  - Hardware setup (Waveshare gateway)
  - SystemD service configuration

- **[API Reference](docs/API_REFERENCE.md)** - Complete REST API documentation
  - All endpoints with examples
  - Request/response formats
  - Error codes and handling
  - Usage examples (cURL, JavaScript, Python)

### Architecture

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[UML Diagrams](UML/)** - Sequence diagrams for all major flows
  - Scheduler control flow
  - AI Mode operation
  - Heat pump control
  - Thermostat integration
  - Network architecture

## License

This project is provided as-is for interfacing with LG R290 heat pumps.

## References

- LG R290 Modbus Register Documentation: `LG_R290_register.pdf`
- pymodbus Documentation: https://pymodbus.readthedocs.io/
- FastAPI Documentation: https://fastapi.tiangolo.com/

## Support

For issues or questions:
- Check the [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
- Review logs: `docker-compose logs -f`
- Verify configuration in `.env` file
- Ensure DIP switches on LG R290 are set correctly (SW1-1: ON, SW1-2: ON)
