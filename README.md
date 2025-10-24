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

Configuration is managed via environment variables in `docker-compose.yml` and `.env` file. Key settings include Modbus connection parameters, polling intervals, and thermostat API integration.

For complete environment variable reference and configuration examples, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### Modbus Registers

The LG R290 uses Modbus TCP for communication. Key control registers:

- **Coil 00001**: Power ON/OFF
- **Holding 40001**: Operating Mode (0=Cool, 3=Auto, 4=Heat)
- **Holding 40003**: Target Temperature (only used in Heat/Cool mode, 33-50°C)
- **Holding 40005**: Auto Mode Offset (only used in Auto mode, ±5K)

**Temperature Control Modes:**
- **Manual Mode (Heat/Cool)**: Direct flow temperature control via register 40003
- **Auto Mode**: LG's internal heating curve + offset adjustment via register 40005

For complete register mapping and detailed documentation, see [MODBUS.md](MODBUS.md).

## API Endpoints

Quick examples:

```bash
# Get status
curl http://localhost:8002/status

# Turn heat pump ON
curl -X POST http://localhost:8002/power -d '{"power_on": true}'

# Switch to LG Auto mode
curl -X POST http://localhost:8002/lg-mode -d '{"mode": 3}'

# Adjust Auto mode offset
curl -X POST http://localhost:8002/auto-mode-offset -d '{"offset": 2}'
```

**Interactive API Documentation**: http://localhost:8002/docs (Swagger UI)

For complete API reference with all endpoints, schemas, and examples, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

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

For comprehensive troubleshooting guides covering:
- Connection issues (Modbus, Docker, Network)
- Heat pump control problems
- Scheduler not working
- Hardware integration issues
- Diagnostic commands

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

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
