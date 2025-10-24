# LG R290 Heat Pump Control System

A Docker-based software stack for interfacing with an LG R290 7kW heat pump via Modbus TCP protocol with integrated room thermostat control and direct LG mode control.

**Version**: v1.0 (Stable)
**Platform**: Raspberry Pi 5 / Linux
**Status**: Production ready with LG Auto mode and manual heating control

## Features

### Core Functionality
- **FastAPI Backend**: RESTful API for heat pump monitoring and control
- **Responsive Web UI**: Dark mode HTML5 interface optimized for desktop and mobile kiosk mode
- **Containerized Deployment**: Docker Compose orchestration
- **Production Ready**: Deployed on real LG R290 hardware via Modbus TCP

### Web UI Features
- **Dark Mode Design**: Pure black background with high contrast for OLED displays
- **Modular ES6 Architecture**: Clean separation of concerns (config, utils, heatpump, thermostat modules)
- **Dual Layout Support**:
  - Desktop: Traditional vertical layout with full-sized gauges
  - Landscape (Mobile): Optimized compact layout fits single screen without scrolling
- **Heat Pump Control**:
  - Real-time monitoring: Flow temperature gauge, power status
  - Unified status badges: Heat pump, compressor, circulation pump (with LED indicators)
  - **LG Mode Toggle**: Switch between LG Auto mode and Manual Heating mode
  - **LG Auto Mode**: Uses LG's internal heating curve with adjustable offset (-5 to +5K)
  - **Manual Heating Mode**: Direct flow temperature control (33-50°C) with slider
  - Instant UI response: Sections appear immediately when switching modes
  - Power ON/OFF control (read-only mode for safety)
- **External Thermostat Integration** (via separate shelly_bt_temp project):
  - Reads thermostat mode via API (ECO/AUTO/ON/OFF)
  - Automatic LG offset adjustment based on thermostat mode
  - No GUI controls (thermostat has its own UI)
  - Backend-only integration for offset synchronization
- **Kiosk Mode Optimized**: Perfect for wall-mounted mobile displays in landscape orientation
- **Cross-Origin Support**: CORS-enabled for multi-service integration

## Architecture

The system consists of two main services:

1. **heatpump-service**: FastAPI service with AsyncModbusTcpClient for Modbus communication
2. **heatpump-ui**: Nginx-served HTML5 interface for visualization and control

Connects to real LG R290 hardware via Waveshare RS485-to-Ethernet gateway.

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

### Production Deployment

The system is deployed in production and connects to real LG R290 hardware:

1. Configure `.env` with your Waveshare gateway settings:
```bash
MODBUS_HOST=192.168.2.10    # Your Waveshare gateway IP
MODBUS_PORT=8899            # Gateway Modbus port
MODBUS_UNIT_ID=5            # LG heat pump device ID
```

2. Start services:
```bash
docker-compose up -d
```

### Thermostat Integration

This project integrates with the **shelly_bt_temp** project (separate repository) via API:

**What this project does**:
- Reads thermostat mode from external API (`http://iot-api:8000`)
- Automatically adjusts LG Auto mode offset based on thermostat mode
- Backend-only integration (no thermostat GUI in this project)

**Configuration**:
```bash
# In docker-compose.yml
THERMOSTAT_API_URL=http://iot-api:8000  # Container name on Docker network
```

**Offset Mapping** (configured in `service/config.json`):
- ECO mode → -2K offset (energy saving)
- AUTO mode → +2K offset (comfort)
- ON mode → +2K offset (comfort)
- OFF mode → -5K offset (minimal heating)

**Note**: The thermostat UI and control is handled by the shelly_bt_temp project, not this one.

### LG Mode Configuration

The system supports two operating modes (`service/config.json`):

**LG Auto Mode Offset** - Adjusts LG's heating curve based on thermostat mode:
```json
{
  "lg_auto_offset": {
    "enabled": true,
    "thermostat_mode_mappings": {
      "ECO": -2,    // -2K offset in ECO mode (energy saving)
      "AUTO": 2,    // +2K offset in AUTO mode (comfort)
      "ON": 2,      // +2K offset in ON mode (comfort)
      "OFF": -5     // -5K offset in OFF mode (minimal heating)
    },
    "settings": {
      "default_offset": 0,
      "min_offset": -5,
      "max_offset": 5
    }
  }
}
```

**Manual Heating Mode Settings** - Default temperature when switching to manual control:
```json
{
  "lg_heating_mode": {
    "default_flow_temperature": 40.0,  // Default when entering manual mode
    "min_temperature": 33.0,           // Minimum allowed
    "max_temperature": 50.0            // Maximum allowed
  }
}
```

**Key API Endpoints**:
- `GET /status` - Get heat pump status (includes current mode and temperatures)
- `POST /lg-mode` - Switch modes: `{"mode": 3}` (Auto) or `{"mode": 4}` (Heating)
- `POST /auto-mode-offset` - Set offset: `{"offset": 2}` (range: -5 to +5)
- `POST /setpoint` - Set flow temperature: `{"temperature": 40.0}` (only in Heating mode)

**Startup Behavior**:
- Heat pump always starts in **LG Auto Mode (3)** on service startup
- Offset automatically synced based on current thermostat mode
- Ensures consistent behavior after power outages or restarts

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `heatpump-mock` | Modbus TCP host (container name or IP) |
| `MODBUS_PORT` | `502` | Modbus TCP port (internal Docker network) |
| `MODBUS_UNIT_ID` | `1` | Modbus slave/unit ID |
| `POLL_INTERVAL` | `5` | Polling interval in seconds |
| `THERMOSTAT_API_URL` | `http://iot-api:8000` | Thermostat API base URL (Docker container name for AI Mode) |

**Note for Thermostat Integration**:
- The `THERMOSTAT_API_URL` should use the **Docker container name** (`iot-api`) not the host IP
- Requires external network reference to the thermostat stack (see docker-compose.yml)
- Example: `shelly_bt_temp_default` network must exist and be referenced
- If thermostat API is unavailable, system uses default offset (0K)

### Modbus Registers

Key registers implemented:

| Type | Address | Description | Unit | Notes |
|------|---------|-------------|------|-------|
| Coil | 00001 | Power ON/OFF | Boolean | - |
| Discrete | 10004 | Compressor Status | Boolean | - |
| Input | 30003 | Return Temp (Inlet - colder) | 0.1°C | - |
| Input | 30004 | Flow Temp (Outlet - hotter) | 0.1°C | - |
| Input | 30009 | Flow Rate | 0.1 LPM | - |
| Holding | 40001 | Operating Mode Setting | Enum | 0=Cool, 3=Auto, 4=Heat |
| Holding | 40003 | Target Temperature | 0.1°C | **Only used in Heat/Cool mode** |
| Holding | 40005 | Auto Mode Offset | 1K | **Only used in Auto mode** (±5K) |

**Important: Temperature Control Modes**

The heat pump has two distinct temperature control mechanisms:

1. **Manual Mode (Heat/Cool)**: Register 40001 = 0 (Cool) or 4 (Heat)
   - Flow temperature is controlled by **register 40003** (Target Temperature)
   - User sets explicit target flow temperature (33-50°C)
   - Register 40005 (Auto Mode Offset) is ignored

2. **Auto Mode**: Register 40001 = 3 (Auto)
   - Flow temperature is calculated by LG's internal heating curve
   - Calculation uses outdoor temperature + **register 40005** (Auto Mode Offset)
   - Register 40003 (Target Temperature) is **ignored/unused**
   - Offset allows fine-tuning: -5K (colder) to +5K (warmer)

The UI automatically switches between showing the temperature slider (Manual mode) and the offset display (Auto mode).

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
├── service/
│   ├── Dockerfile
│   ├── main.py
│   ├── config.json          # LG mode configuration
│   ├── schedule.json        # Scheduler configuration
│   └── requirements.txt
└── ui/
    ├── Dockerfile
    ├── index.html
    ├── static/
    │   ├── style.css
    │   ├── config.js        # API endpoints
    │   ├── utils.js         # Shared utilities
    │   ├── heatpump.js      # Heat pump control
    │   └── thermostat.js    # Thermostat display
    └── nginx.conf
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f heatpump-service
docker-compose logs -f heatpump-ui
```

### Rebuilding Services

```bash
# Rebuild all
docker-compose build

# Rebuild specific service
docker-compose build heatpump-service
```

## Troubleshooting

### Cannot connect to Modbus gateway

1. Check if services are running:
```bash
docker-compose ps
```

2. Check logs:
```bash
docker-compose logs heatpump-service
```

3. Verify gateway is reachable:
```bash
ping 192.168.2.10  # Your gateway IP
```

4. Check Modbus port (should be 8899 for Waveshare)

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

1. Update `lg_r290_modbus.py` with new register addresses
2. Add API endpoints in `service/main.py`
3. Update UI in `ui/index.html` and `ui/static/*.js`

### Adding Features

The system is designed for easy extension:

- Additional sensors/actuators: Add to Modbus client and API
- Data logging: Add time-series database (InfluxDB, PostgreSQL)
- Notifications: Integrate MQTT or webhook notifications
- Home automation: Add MQTT bridge for Home Assistant integration

## Version History

### v1.0 - Current (2025-10-21)

**Status**: Production ready with LG Auto mode and manual heating control

**Key Features (v1.0):**
- ✅ **LG Mode Control**: Simple toggle between Auto and Manual Heating modes
- ✅ **LG Auto Mode**: Uses LG's internal heating curve with adjustable offset (-5 to +5K)
- ✅ **Manual Heating Mode**: Direct flow temperature control (33-50°C)
- ✅ **Instant UI Response**: Mode sections appear immediately (no 30s poll wait)
- ✅ **Auto Startup**: Always starts in LG Auto mode on service restart
- ✅ **Default Temperature**: Automatically sets 40°C when switching to manual mode
- ✅ **Thermostat Integration**: Offset automatically adjusts based on ECO/AUTO/ON/OFF modes
- ✅ **JSON Configuration**: User-editable offset mappings and default temperature
- ✅ **Safe GUI Reload**: Page refresh never triggers unwanted mode changes
- ✅ **Mode Logging**: All mode changes logged with emoji for easy tracking

**Backend Enhancements:**
- New API endpoints: `/lg-mode` (POST), `/auto-mode-offset` (POST), `/lg-auto-offset-config` (GET)
- Startup function: Automatically sets LG Auto mode on service start
- Config-driven: Default temperatures and offset mappings in `config.json`
- Clean architecture: Removed 582 lines of dead-end code (net: -323 lines)
**UI Improvements:**
- LG Auto toggle switch in Power Control panel
- Status indicator: "Manual Heating" / "LG Auto Mode"
- Instant section switching (offset controls ↔ temperature slider)
- Temperature slider shows default 40°C when entering manual mode
- Status polling syncs mode from backend (safe page reloads)

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

**Production Status:**
- ✅ Deployed on real LG R290 hardware via Waveshare RS485-to-Ethernet gateway
- ✅ Multi-day stable operation verified
- ✅ All register readings confirmed with actual heat pump
- ✅ Production kiosk deployment complete
- ✅ Prometheus metrics integration active

**System Architecture:**
- Real hardware via Modbus TCP (no mock server)
- Waveshare gateway at 192.168.2.10:8899
- LG R290 device ID: 5
- Production monitoring and health checks

## Documentation

Comprehensive feature documentation is available in the `docs/` directory:

### Feature Documentation

- **[Scheduler](docs/SCHEDULER.md)** - Time-based automatic room temperature and heat pump offset scheduling
  - Week-based schedules (weekday/weekend patterns)
  - **LG Auto Mode Offset Scheduling**: Automatically adjust flow temperature response at different times
  - Discrete event triggering at exact times
  - Mode-aware operation (respects ECO/OFF)
  - Volume-mounted configuration (restart to apply changes)
  - Vienna timezone with DST support
  - **Note**: Scheduler controls both thermostat (shelly_bt_temp project) and heat pump offset (this project)

- **[Heat Pump Control](docs/HEAT_PUMP_CONTROL.md)** - LG Mode Modbus TCP control
  - Complete register mapping
  - LG Auto mode with offset control
  - Manual Heating mode with temperature control
  - Real-time status monitoring
  - Hardware integration guide

- **[Thermostat Integration](docs/THERMOSTAT_INTEGRATION.md)** - External API integration
  - Cross-stack Docker communication with shelly_bt_temp project
  - Automatic LG offset adjustment based on thermostat mode
  - Backend-only integration (no thermostat UI in this project)

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
- **[UML Diagrams](UML/)** - Sequence diagrams for major flows
  - Scheduler control flow
  - LG Mode control
  - Heat pump control
  - Thermostat integration
  - Network architecture
  - Prometheus metrics

## License

This project is provided as-is for interfacing with LG R290 heat pumps.

## References

- pymodbus Documentation: https://pymodbus.readthedocs.io/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Related project: [shelly_bt_temp](../shelly_bt_temp) - Thermostat control system

## Support

For issues or questions:
- Check the [ARCHITECTURE.md](ARCHITECTURE.md) for system design details
- Review logs: `docker-compose logs -f`
- Verify configuration in `.env` file
- Ensure DIP switches on LG R290 are set correctly (SW1-1: ON, SW1-2: ON)
