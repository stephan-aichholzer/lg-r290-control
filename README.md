# LG R290 Heat Pump Control System

A Docker-based software stack for interfacing with an LG R290 7kW heat pump via Modbus TCP protocol.

## Features

- **Mock Modbus Server**: JSON-backed Modbus TCP server for development and testing
- **FastAPI Backend**: RESTful API for heat pump monitoring and control
- **HTML5 Web UI**: Responsive dashboard with gauges, sliders, and real-time monitoring
- **Switchable Architecture**: Easy transition from mock to real hardware
- **Containerized Deployment**: Docker Compose orchestration for all services

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
http://localhost:8080
```

5. API documentation (Swagger):
```
http://localhost:8000/docs
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
| Input | 30003 | Flow Temperature | 0.1°C |
| Input | 30004 | Return Temperature | 0.1°C |
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
  "compressor_running": false,
  "operating_mode": "Heating",
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

The mock server uses `mock/registers.json` for register values. Edit this file while the container is running, and changes will be reflected immediately (for reads). For writes, the mock server will update this file automatically.

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

## License

This project is provided as-is for interfacing with LG R290 heat pumps.

## References

- LG R290 Modbus Register Documentation: `LG_R290_register.pdf`
- pymodbus Documentation: https://pymodbus.readthedocs.io/
- FastAPI Documentation: https://fastapi.tiangolo.com/
