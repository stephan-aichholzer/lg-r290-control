# LG R290 Heat Pump Control System

A Docker-based software stack for interfacing with an LG R290 7kW heat pump via Modbus TCP protocol with integrated room thermostat control and direct LG mode control.

**Version**: v1.0 (Stable)
**Platform**: Raspberry Pi 5 / Linux
**Status**: Production ready with LG Auto mode and manual heating control

---

## Features

### Core Functionality
- **FastAPI Backend**: RESTful API for heat pump monitoring and control
- **Responsive Web UI**: Dark mode HTML5 interface optimized for desktop and mobile kiosk mode
- **Containerized Deployment**: Docker Compose orchestration
- **Production Ready**: Deployed on real LG R290 hardware via Modbus TCP

### Heat Pump Control
- **LG Mode Toggle**: Switch between LG Auto mode and Manual Heating mode
- **LG Auto Mode**: Uses LG's internal heating curve with adjustable offset (-5 to +5K)
- **Manual Heating Mode**: Direct flow temperature control (33-50°C) with slider
- **Power Control**: Turn heat pump ON/OFF via API and UI
- **Real-time Monitoring**: Flow temperature, return temperature, outdoor temperature, system status
- **Instant UI Response**: Mode sections appear immediately when switching modes

### Web UI Features
- **Dark Mode Design**: Pure black background with high contrast for OLED displays
- **Modular ES6 Architecture**: Clean separation of concerns (config, utils, heatpump, thermostat modules)
- **Dual Layout Support**:
  - Desktop: Traditional vertical layout with full-sized gauges
  - Landscape (Mobile): Optimized compact layout fits single screen without scrolling
- **Unified Status Badges**: Heat pump, compressor, circulation pump with LED indicators
- **Kiosk Mode Optimized**: Perfect for wall-mounted mobile displays in landscape orientation
- **Cross-Origin Support**: CORS-enabled for multi-service integration

### Thermostat Integration
External integration with **[shelly-blu-ht](https://github.com/stephan-aichholzer/shelly-blu-ht)** project (separate repository) via API:
- Reads thermostat mode via API (ECO/AUTO/ON/OFF)
- Automatically adjusts LG offset based on thermostat mode
- Backend-only integration (no thermostat GUI in this project)
- Offset synchronization for comfort vs efficiency balance

---

## Architecture

The system consists of two Docker services:

1. **heatpump-service**: FastAPI service with AsyncModbusTcpClient for Modbus communication
2. **heatpump-ui**: Nginx-served HTML5 interface for visualization and control

The system connects to the LG R290 heat pump via a Waveshare RS485-to-Ethernet gateway using Modbus TCP protocol.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

---

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
# Edit .env if needed (see Configuration section)
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

---

## Configuration

### Environment Variables

Configuration is managed via environment variables in `docker-compose.yml` and `.env` file.

**Key settings:**
- `MODBUS_HOST` - Waveshare gateway IP address
- `MODBUS_PORT` - Modbus TCP port (8899 for Waveshare)
- `MODBUS_UNIT_ID` - LG heat pump Modbus device ID (typically 5 or 7)
- `POLL_INTERVAL` - Polling interval in seconds (default: 20)
- `THERMOSTAT_API_URL` - Thermostat API URL (optional, for thermostat integration)

**Example `.env` for production:**
```bash
MODBUS_HOST=192.168.2.10       # Your Waveshare gateway IP
MODBUS_PORT=8899               # Waveshare gateway port
MODBUS_UNIT_ID=7               # LG heat pump device ID (check your installation)
POLL_INTERVAL=20               # Polling interval to maintain external control
THERMOSTAT_API_URL=http://iot-api:8000  # Optional thermostat integration
```

For complete configuration reference, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

### LG Mode Configuration

The system supports two operating modes configured in `service/config.json`:

**1. LG Auto Mode Offset** - Adjusts LG's heating curve:
```json
{
  "lg_auto_offset": {
    "enabled": true,
    "thermostat_mode_mappings": {
      "ECO": -2,    // Energy saving
      "AUTO": 2,    // Comfort
      "ON": 2,      // Comfort
      "OFF": -5     // Minimal heating
    },
    "settings": {
      "default_offset": 0,
      "min_offset": -5,
      "max_offset": 5
    }
  }
}
```

**2. Manual Heating Mode Settings** - Default temperature when switching to manual:
```json
{
  "lg_heating_mode": {
    "default_flow_temperature": 40.0,
    "min_temperature": 33.0,
    "max_temperature": 50.0
  }
}
```

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

---

## API Endpoints

Quick examples:

```bash
# Get current status
curl http://localhost:8002/status

# Turn heat pump ON
curl -X POST http://localhost:8002/power \
  -H "Content-Type: application/json" \
  -d '{"power_on": true}'

# Switch to LG Auto mode
curl -X POST http://localhost:8002/lg-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": 3}'

# Adjust Auto mode offset
curl -X POST http://localhost:8002/auto-mode-offset \
  -H "Content-Type: application/json" \
  -d '{"offset": 2}'

# Set flow temperature (Manual Heating mode only)
curl -X POST http://localhost:8002/setpoint \
  -H "Content-Type: application/json" \
  -d '{"temperature": 40.0}'
```

**Interactive API Documentation**: http://localhost:8002/docs (Swagger UI)

For complete API reference with all endpoints, schemas, and examples, see [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

---

## Usage

### Deployment

1. Configure `.env` with your Waveshare gateway settings:
```bash
MODBUS_HOST=192.168.2.10
MODBUS_PORT=8899
MODBUS_UNIT_ID=7
POLL_INTERVAL=20
```

2. Start services:
```bash
docker-compose up -d
```

### Thermostat Integration

This project integrates with the **[shelly-blu-ht](https://github.com/stephan-aichholzer/shelly-blu-ht)** project (separate repository) via API:

**What this project does**:
- Reads thermostat mode from external API
- Automatically adjusts LG Auto mode offset based on thermostat mode
- Backend-only integration (no thermostat GUI in this project)

**Configuration**:
```bash
# In docker-compose.yml or .env
THERMOSTAT_API_URL=http://iot-api:8000  # Docker container name
```

**Offset Mapping** (configured in `service/config.json`):
- ECO mode → -2K offset (energy saving)
- AUTO mode → +2K offset (comfort)
- ON mode → +2K offset (comfort)
- OFF mode → -5K offset (minimal heating)

**Note**: The thermostat UI and control is handled by the [shelly-blu-ht](https://github.com/stephan-aichholzer/shelly-blu-ht) project, not this one.

For detailed setup instructions, see [docs/THERMOSTAT_INTEGRATION.md](docs/THERMOSTAT_INTEGRATION.md).

---

## Project Structure

```
lg_r290_control/
├── docker-compose.yml          # Service orchestration
├── .env.example                # Configuration template
├── README.md                   # This file
├── CHANGELOG.md                # Version history
├── ARCHITECTURE.md             # System architecture
├── MODBUS.md                   # Register reference
├── service/                    # FastAPI backend
│   ├── Dockerfile
│   ├── main.py                 # API endpoints
│   ├── config.json             # LG mode configuration
│   ├── schedule.json           # Scheduler configuration
│   └── requirements.txt
├── ui/                         # Web interface
│   ├── Dockerfile
│   ├── index.html
│   ├── static/
│   │   ├── style.css
│   │   ├── config.js           # API configuration
│   │   ├── utils.js            # Shared utilities
│   │   ├── heatpump.js         # Heat pump control
│   │   └── thermostat.js       # Thermostat display
│   └── nginx.conf
└── docs/                       # Documentation
    ├── API_REFERENCE.md
    ├── DEPLOYMENT.md
    ├── HEAT_PUMP_CONTROL.md
    ├── SCHEDULER.md
    ├── THERMOSTAT_INTEGRATION.md
    ├── TROUBLESHOOTING.md
    ├── PYMODBUS_OPTIMIZATION.md
    └── DEVELOPMENT_JOURNEY.md
```

---

## Development

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

# Restart after rebuild
docker-compose up -d
```

### Adding New Features

The system is designed for easy extension:

- **Additional sensors/actuators**: Update `lg_r290_modbus.py`, add API endpoints, update UI
- **Data logging**: Add time-series database (InfluxDB, PostgreSQL)
- **Notifications**: Integrate MQTT or webhook notifications
- **Home automation**: Add MQTT bridge for Home Assistant integration

For detailed extension guide, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Troubleshooting

For comprehensive troubleshooting guides covering:
- Connection issues (Modbus, Docker, Network)
- Heat pump control problems
- Scheduler not working
- Hardware integration issues
- Diagnostic commands

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

**Quick diagnostics:**
```bash
# Check service health
curl http://localhost:8002/health

# View logs
docker-compose logs --tail=50

# Check current status
curl http://localhost:8002/status | jq .
```

---

## Documentation

Comprehensive documentation is available in the `docs/` directory:

### Feature Documentation
- **[Scheduler](docs/SCHEDULER.md)** - Time-based automatic temperature and offset scheduling
- **[Heat Pump Control](docs/HEAT_PUMP_CONTROL.md)** - LG Mode Modbus TCP control
- **[Thermostat Integration](docs/THERMOSTAT_INTEGRATION.md)** - External API integration

### System Documentation
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Docker setup and configuration
- **[API Reference](docs/API_REFERENCE.md)** - Complete REST API documentation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Architecture & Development
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture overview
- **[MODBUS.md](MODBUS.md)** - Complete register reference
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[Development Journey](docs/DEVELOPMENT_JOURNEY.md)** - Implementation story and lessons learned
- **[UML Diagrams](UML/)** - Sequence diagrams for major flows

---

## Hardware Requirements

### For Development
- Docker and Docker Compose
- Any Linux system or Raspberry Pi

### For Production
- Raspberry Pi 4/5 (4GB+ RAM recommended)
- LG R290 7kW heat pump (or compatible LG Therma V model)
- Waveshare RS232/RS485 to Ethernet gateway
- Shielded twisted pair cable for RS-485
- Network connectivity

### LG Heat Pump Configuration
- DIP switches SW1-1 and SW1-2 set to **ON** (enables Modbus)
- Device ID configured (typically 5 or 7, check manual)
- RS-485 connection on terminals 21 (A+) and 22 (B-)

For detailed hardware setup, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## References

- **pymodbus Documentation**: https://pymodbus.readthedocs.io/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Related project**: [shelly_bt_temp](../shelly_bt_temp) - Thermostat control system

---

## Support

For issues or questions:
1. Check the [Documentation](#documentation) section above
2. Review [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
3. Check logs: `docker-compose logs -f`
4. Verify configuration in `.env` file
5. Ensure DIP switches on LG R290 are set correctly (SW1-1: ON, SW1-2: ON)

---

## Current Version

**v1.0** (2025-10-21) - Production ready with LG Auto mode and manual heating control

Key features:
- ✅ LG Mode Control (Auto/Manual Heating toggle)
- ✅ LG Auto Mode with offset adjustment (±5K)
- ✅ Manual Heating Mode with direct temperature control
- ✅ Thermostat integration with automatic offset adjustment
- ✅ Scheduler support for time-based automation
- ✅ Production-ready Modbus communication with retry logic
- ✅ Responsive dark mode UI optimized for kiosk displays

For detailed version history and release notes, see [CHANGELOG.md](CHANGELOG.md).
