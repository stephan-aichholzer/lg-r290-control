# Deployment Guide

## Quick Start

```bash
# Clone repository
git clone https://github.com/stephan-aichholzer/lg-r290-control.git
cd lg-r290-control

docker-compose up -d

# Access UI
http://localhost:8080
```

## Docker Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| **heatpump-service** | lg_r290_service | 8002→8000 | FastAPI backend |
| **heatpump-ui** | lg_r290_ui | 8080→80 | Nginx web UI |

## Environment Variables

### Heat Pump Service

Configure in `docker-compose.yml` or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODBUS_HOST` | `192.168.2.10` | Modbus TCP host (container name or IP) |
| `MODBUS_PORT` | `502` | Modbus TCP port (8899 for Waveshare gateway) |
| `MODBUS_UNIT_ID` | `1` | Modbus slave/unit ID |
| `POLL_INTERVAL` | `5` | Status polling interval (seconds) |
| `THERMOSTAT_API_URL` | `http://iot-api:8000` | Thermostat API URL (container name for Docker) |
| `TZ` | `Europe/Vienna` | Timezone (for scheduler) |

### Example .env File

```bash
# Development (Mock)
MODBUS_HOST=192.168.2.10
MODBUS_PORT=502
THERMOSTAT_API_URL=http://iot-api:8000

# Production (Real Hardware)
# MODBUS_HOST=192.168.2.100
# MODBUS_PORT=502
# THERMOSTAT_API_URL=http://iot-api:8000

# Optional
POLL_INTERVAL=5
MODBUS_UNIT_ID=1
TZ=Europe/Vienna
```

## Deployment Modes

### Development Mode (Mock)

Use mock Modbus server for testing without hardware:

```yaml
# docker-compose.yml (default)
environment:
  - MODBUS_HOST=192.168.2.10  # Mock server
  - MODBUS_PORT=502
```

**Features:**
- JSON-backed registers (`mock/registers.json`)
- Edit JSON to simulate scenarios
- No hardware required

**Start:**
```bash
docker-compose up -d
```

### Production Mode (Real Hardware)

Connect to actual LG R290 heat pump:

```yaml
# docker-compose.yml or .env
environment:
  - MODBUS_HOST=192.168.2.100  # Heat pump IP
  - MODBUS_PORT=502
```

**Requirements:**
- LG R290 heat pump with RS485
- Waveshare RS485 to Ethernet gateway
- Network connectivity

**Start:**
```bash
# Build and start
docker-compose up -d

# Verify connection
curl http://localhost:8002/health
```

## Network Configuration

### Docker Networks

```yaml
networks:
  heatpump-net:
    driver: bridge              # Internal network
  shelly_bt_temp_default:
    external: true              # External reference to thermostat network
```

**Purpose:**
- `heatpump-net`: Internal communication (mock, service, UI)
- `shelly_bt_temp_default`: Cross-stack communication with thermostat

### External Network Setup

If thermostat integration is required:

```bash
# Verify thermostat network exists
docker network ls | grep shelly_bt_temp_default

# If not exists, create it first in thermostat project
cd /path/to/shelly_bt_temp
docker-compose up -d
```

## Port Mapping

| Internal Port | External Port | Service | Access |
|---------------|---------------|---------|--------|
| 502 | 5020 | Mock Modbus | `localhost:5020` |
| 8000 | 8002 | FastAPI | `http://localhost:8002` |
| 80 | 8080 | Web UI | `http://localhost:8080` |

**External access** uses mapped ports (5020, 8002, 8080).
**Internal** (container-to-container) uses internal ports (502, 8000, 80).

## Volume Mounts

### Mock Server

```yaml
volumes:
  - ./mock/registers.json:/app/registers.json
```

**Purpose**: Persist mock data between restarts.

### Service Configuration (Implicit)

Configuration files copied into container:
- `service/config.json` → `/app/config.json`
- `service/schedule.json` → `/app/schedule.json`

**To update**: Rebuild container after editing.

## Build and Start

### Initial Setup

```bash
# Build all images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Update After Code Changes

```bash
# Rebuild specific service
docker-compose build heatpump-service

# Restart service
docker-compose up -d heatpump-service

# Or restart all
docker-compose restart
```

### Stop Services

```bash
# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Hardware Setup

### Waveshare RS485 to Ethernet Gateway

**Connection:**
```
LG R290 Heat Pump
    ↕ RS485 (A+, B-)
Waveshare Gateway
    ↕ Ethernet (RJ45)
Network Switch/Router
    ↕
Raspberry Pi (Docker Host)
```

**Gateway Configuration:**
- IP Address: `192.168.2.100` (static recommended)
- Protocol: Modbus RTU → Modbus TCP
- Baud Rate: 9600
- Parity: None (N)
- Data Bits: 8
- Stop Bits: 1
- TCP Port: 502

### Raspberry Pi Requirements

**Minimum:**
- Raspberry Pi 4 (2GB RAM)
- 16GB SD card
- Raspbian OS (Debian-based)
- Docker + Docker Compose installed

**Recommended:**
- Raspberry Pi 4 (4GB+ RAM)
- 32GB SD card (for logs)
- Static IP address
- Reliable power supply

### Docker Installation (Raspberry Pi)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose

# Reboot
sudo reboot
```

## Service Management

### SystemD Service (Auto-start)

Create `/etc/systemd/system/lg-r290-control.service`:

```ini
[Unit]
Description=LG R290 Heat Pump Control
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/lg-r290-control
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=pi

[Install]
WantedBy=multi-user.target
```

**Enable:**
```bash
sudo systemctl enable lg-r290-control.service
sudo systemctl start lg-r290-control.service
```

### Commands

```bash
# Status
docker-compose ps
docker-compose logs heatpump-service

# Restart
docker-compose restart

# Update
cd /home/pi/lg-r290-control
git pull
docker-compose build
docker-compose up -d
```

## Monitoring

### Health Checks

```bash
# Service health
curl http://localhost:8002/health

# AI Mode status
curl http://localhost:8002/ai-mode

# Scheduler status
curl http://localhost:8002/schedule

# Heat pump status
curl http://localhost:8002/status
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker logs lg_r290_service --tail 100 -f

# Search logs
docker logs lg_r290_service | grep "error\|ERROR"
```

## Backup and Restore

### Backup Configuration

```bash
# Backup config files
tar -czf lg-r290-backup.tar.gz \
  service/config.json \
  service/schedule.json \
  mock/registers.json \
  .env \
  docker-compose.yml
```

### Restore

```bash
# Extract backup
tar -xzf lg-r290-backup.tar.gz

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker status
sudo systemctl status docker

# Check logs
docker-compose logs

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Network Issues

```bash
# List networks
docker network ls

# Inspect network
docker network inspect shelly_bt_temp_default

# Test connectivity from container
docker exec lg_r290_service ping iot-api
docker exec lg_r290_service curl http://iot-api:8000/api/v1/thermostat/status
```

### Port Conflicts

```bash
# Check if ports are in use
sudo netstat -tlnp | grep -E "8080|8002|5020"

# Change ports in docker-compose.yml
ports:
  - "8081:80"  # Changed from 8080
```

### Modbus Connection Failed

**Check:**
1. Heat pump IP address reachable: `ping 192.168.2.100`
2. Modbus port open: `telnet 192.168.2.100 502`
3. Gateway configuration correct
4. Firewall not blocking port 502

**Logs:**
```bash
docker logs lg_r290_service | grep "modbus\|connection"
```

## Security Considerations

### Network Security

- **Firewall**: Restrict access to ports 8080, 8002
- **Local Network**: Keep on isolated VLAN if possible
- **No Internet Exposure**: Services should not be exposed to internet

### Docker Security

```bash
# Run containers as non-root user
user: "1000:1000"

# Read-only root filesystem (where possible)
read_only: true
```

### Configuration Security

- Store `.env` file outside repository
- Don't commit sensitive data to git
- Use `.gitignore` for local configs

## Performance Tuning

### Polling Intervals

Adjust based on system load:

```yaml
# Faster updates (higher load)
POLL_INTERVAL=2

# Slower updates (lower load)
POLL_INTERVAL=10
```

### Resource Limits

```yaml
services:
  heatpump-service:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

## Upgrading

```bash
# Pull latest changes
git pull origin master

# Rebuild images
docker-compose build

# Restart with new images
docker-compose up -d

# View logs to verify
docker-compose logs -f
```

## Logging & Monitoring

### Log Management Script

The `./logs.sh` script provides convenient log management:

```bash
./logs.sh              # Tail all logs
./logs.sh tail service # Tail API only
./logs.sh dump         # Dump all to console
./logs.sh save         # Save to timestamped folder
./logs.sh errors       # Show only errors/warnings
./logs.sh search "AI"  # Search for pattern
./logs.sh stats        # Show statistics
./logs.sh help         # Show help
```

### Live Monitoring Script

The `./monitor.sh` script provides live monitoring dashboard:

```bash
./monitor.sh           # Full dashboard (refreshes every 5s)
./monitor.sh temps     # Temperature monitoring
./monitor.sh ai        # AI Mode status
./monitor.sh once      # One-time snapshot
./monitor.sh containers# Container status
./monitor.sh help      # Show help
```

### Common Usage

```bash
# Check what's happening
./monitor.sh once

# Watch logs live
./logs.sh tail service

# Find issues
./logs.sh errors

# Search for something
./logs.sh search "temperature"
./logs.sh search "Modbus"

# Save logs for analysis
./logs.sh save

# Monitor temperatures
./monitor.sh temps
```

### Traditional Docker Commands

```bash
docker-compose ps              # Container status
docker-compose logs -f         # Follow all logs
docker stats                   # Resource usage
docker-compose restart         # Restart services
```

### Log Levels

- **INFO** - Normal operations
- **WARNING** - Recoverable issues
- **ERROR** - Failures
- **DEBUG** - Detailed info (set LOG_LEVEL=DEBUG)

---

## Related Documentation

- [Scheduler](SCHEDULER.md) - Configure schedules
- [Heat Pump Control](HEAT_PUMP_CONTROL.md) - Modbus setup
- [Thermostat Integration](THERMOSTAT_INTEGRATION.md) - Network configuration
- [API Reference](API_REFERENCE.md) - API endpoints
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
