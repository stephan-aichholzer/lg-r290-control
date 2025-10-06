# LG R290 Heat Pump Control System

A Docker-based software stack for interfacing with an LG R290 7kW heat pump via Modbus TCP protocol.

**Version**: v0.4 (Stable)
**Platform**: Raspberry Pi 5 / Linux
**Status**: Production ready for kiosk deployment

## Features

### Core Functionality
- **Mock Modbus Server**: JSON-backed Modbus TCP server for development and testing
- **FastAPI Backend**: RESTful API for heat pump monitoring and control
- **Responsive Web UI**: Dark mode HTML5 interface optimized for desktop and mobile kiosk mode
- **Switchable Architecture**: Easy transition from mock to real hardware via configuration
- **Containerized Deployment**: Docker Compose orchestration for all services

### Web UI Features
- **Dark Mode Design**: Pure black background with high contrast for OLED displays
- **Dual Layout Support**:
  - Desktop: Traditional vertical layout with full-sized gauges
  - Landscape (Mobile): Optimized 2×2 table layout with 50% larger gauges
- **Real-time Monitoring**: Temperature gauges, flow rate, pressure, operating mode
- **Real-time Synchronization**: All values including temperature slider update automatically (2s interval)
- **Control Interface**: Power ON/OFF, temperature setpoint slider with external change detection
- **Kiosk Mode Ready**: Perfect for wall-mounted displays - slider syncs even when changed via LG app
- **Network Access**: Dynamic hostname detection works from any device on local network

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

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `heatpump-mock` | Modbus TCP host (container name or IP) |
| `MODBUS_PORT` | `502` | Modbus TCP port |
| `MODBUS_UNIT_ID` | `1` | Modbus slave/unit ID |
| `POLL_INTERVAL` | `5` | Polling interval in seconds |

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
    └── app.js
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

### v0.4 - Current (2025-10-06)

**Status**: Production ready for kiosk deployment

**Latest Features:**
- ✅ Real-time slider synchronization for kiosk mode
- ✅ Temperature slider updates automatically when changed externally
- ✅ Complete register monitoring (target temp, water pump status)
- ✅ Optimized 2×2 landscape layout with 50% larger gauges
- ✅ Touch and mouse event support for mobile and desktop
- ✅ Debug logging for troubleshooting

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
