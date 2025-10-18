# LG R290 Control System - UML Sequence Diagrams

This folder contains PlantUML sequence diagrams documenting all major use cases and data flows in the LG R290 Heat Pump Control System.

## Diagram Overview

| Diagram | Description | Key Actors |
|---------|-------------|------------|
| **01_manual_control.puml** | Manual temperature setpoint adjustment | User, UI, API, Modbus, Heat Pump |
| **02_ai_mode_control.puml** | AI Mode adaptive heating control loop | AI Controller, Heating Curve, Thermostat API |
| **03_power_control.puml** | Heat pump power ON/OFF control | User, UI, API, Modbus |
| **04_startup_initialization.puml** | Docker Compose stack startup sequence | Docker, All Services |
| **05_thermostat_integration.puml** | Thermostat integration and cross-stack communication | UI, API, Thermostat, Sensor |
| **06_config_reload.puml** | Hot-reload configuration without restart | Admin, API, Heating Curve |
| **07_error_handling.puml** | Error scenarios and recovery strategies | AI Controller, All Services |
| **08_network_architecture.puml** | Docker network topology and communication paths | All Services, Networks |
| **09_scheduler_control.puml** | Time-based automatic temperature scheduling | Scheduler, Thermostat API, schedule.json |
| **10_lg_auto_mode_offset.puml** | LG Auto mode temperature offset adjustment (±5K) | User, UI, API, Modbus, Heat Pump |
| **11_prometheus_metrics.puml** | Prometheus metrics integration and Grafana monitoring | Monitor Daemon, Prometheus, Grafana |

## Use Cases Covered

### 1. Manual Control (`01_manual_control.puml`)
**Scenario**: User manually adjusts temperature setpoint via web UI
- Initial page load and status display
- User drags slider to change temperature
- API writes to Modbus holding register
- Verification and continuous polling
- Slider auto-sync every 10 seconds

**Key Endpoints**:
- `GET /status` - Retrieve current device state
- `POST /setpoint` - Set target temperature

### 2. AI Mode Control (`02_ai_mode_control.puml`)
**Scenario**: Autonomous temperature optimization based on outdoor and room temperature
- User enables AI Mode toggle
- Background control loop (every 30 seconds)
- Read outdoor temp from heat pump
- Read target room temp from thermostat API
- Calculate optimal flow temperature using heating curves
- Adjust heat pump if needed (threshold: 2°C)
- Automatic shutdown when outdoor ≥18°C

**Key Endpoints**:
- `POST /ai-mode` - Enable/disable AI Mode
- `GET /ai-mode` - Get AI Mode status
- `GET /api/v1/thermostat/status` - Thermostat API (external)

### 3. Power Control (`03_power_control.puml`)
**Scenario**: User turns heat pump ON or OFF
- Optimistic UI update (immediate feedback)
- Modbus coil write (00001)
- Success/failure handling
- Status verification
- Background polling continues independently

**Key Endpoints**:
- `POST /power` - Turn heat pump ON/OFF

### 4. Startup Initialization (`04_startup_initialization.puml`)
**Scenario**: Docker Compose brings up entire stack
- Mock server initialization (pymodbus)
- FastAPI service startup
- Modbus client connection
- Heating curve configuration loading
- Adaptive controller initialization
- Background tasks startup (polling, AI control loop)
- UI container startup (Nginx)

**Components**:
- heatpump-mock (Modbus TCP server)
- heatpump-service (FastAPI)
- heatpump-ui (Nginx static files)

### 5. Thermostat Integration (`05_thermostat_integration.puml`)
**Scenario**: Cross-stack communication with external thermostat API
- Independent thermostat data flow (sensors → InfluxDB)
- Browser access to thermostat (direct HTTP, no Docker)
- User changes target temperature/mode
- AI Mode reads thermostat from backend (Docker network)
- Docker DNS resolution (container names)
- Network topology explanation

**Networks**:
- Browser → Thermostat: Direct LAN access
- Container → Thermostat: Via `shelly_bt_temp_default` external network

### 6. Configuration Hot-Reload (`06_config_reload.puml`)
**Scenario**: Admin updates heating curve configuration without restarting service
- Edit `heating_curve_config.json` on host
- File visible in container via volume mount
- API endpoint triggers reload
- Configuration validation
- New parameters take effect immediately
- No service interruption

**Key Endpoints**:
- `POST /ai-mode/reload-config` - Hot-reload configuration

### 7. Error Handling (`07_error_handling.puml`)
**Scenario**: Various failure modes and recovery strategies
- Heat pump connection lost → retry automatically
- Thermostat API unavailable → fallback to default (21°C)
- Invalid heating curve configuration → keep old config
- Modbus write failure → retry next cycle
- Power control failure → skip adjustment
- Control loop exceptions → graceful degradation

**Recovery Strategy**:
- Never crash entire service
- Log all errors with details
- Use fallback values when possible
- Automatic retry on next cycle
- Graceful degradation

### 8. Network Architecture (`08_network_architecture.puml`)
**Scenario**: Docker multi-stack communication topology
- Three separate Docker stacks (lg_r290_control, shelly_bt_temp, modbus)
- Internal bridge networks per stack
- External network reference pattern
- Container DNS resolution
- Port mapping (internal vs external)
- Browser access patterns
- Cross-stack communication

**Networks**:
- `heatpump-net` (bridge, internal)
- `shelly_bt_temp_default` (bridge, external reference)
- `modbus_default` (bridge, internal)

### 9. Scheduler Control (`09_scheduler_control.puml`)
**Scenario**: Automatic time-based room temperature scheduling
- Background task checking every 60 seconds
- Load schedule from `schedule.json` (weekday/weekend periods)
- Match current time against scheduled periods
- Mode checking (skip if ECO/OFF, apply if AUTO/ON)
- Force mode to AUTO and set scheduled target temperature
- Manual override allowed (reset at next scheduled time)
- Hot-reload configuration via API
- Timezone support (Vienna CEST/CET with DST)

**Key Endpoints**:
- `GET /schedule` - Get scheduler status and current time
- `POST /schedule/reload` - Hot-reload schedule.json

**Key Features**:
- Discrete events at exact times (not continuous)
- Respects user ECO/OFF modes (acts as "resetter")
- Deduplication to prevent multiple triggers per minute
- Vienna timezone with automatic DST handling

### 10. LG Auto Mode Offset (`10_lg_auto_mode_offset.puml`)
**Scenario**: Fine-tune LG's automatic temperature calculation without manual mode
- User adjusts offset via UI slider (+/- buttons)
- Write to Modbus holding register 40005 (±5K range)
- Two's complement encoding for negative values
- Only active when LG mode (40001) = Auto (3)
- Monitor daemon reads offset every 30 seconds
- UI displays "Auto +2K" or "Auto -1K"

**Key Endpoints**:
- `POST /auto-mode-offset` - Set offset (-5 to +5K)
- `GET /status` - Includes auto_mode_offset field

**How LG Auto Mode Works**:
- LG calculates base flow temp from internal heating curve
- Applies offset: final_temp = base_temp + offset
- Example: 40°C base + (-1K) = 39°C final
- Ignored in manual Heat/Cool modes

### 11. Prometheus Metrics Integration (`11_prometheus_metrics.puml`)
**Scenario**: Export heat pump metrics to Prometheus for Grafana visualization
- Monitor daemon writes status.json every 30 seconds
- Background metrics updater reads status.json
- Updates Prometheus Gauges (temperature, power, state)
- Prometheus scrapes /metrics endpoint every 30s
- Grafana visualizes time-series data
- Cross-correlation with WAGO energy meter

**Key Endpoints**:
- `GET /metrics` - Prometheus exposition format

**Metrics Exported**:
- Temperature metrics (flow, return, outdoor, target, delta)
- Status metrics (power, compressor, pump, mode, errors)
- All metrics prefixed with `heatpump_`

**Network Integration**:
- lg_r290_service joins modbus_default network
- Prometheus uses Docker DNS: lg_r290_service:8000
- No port mapping needed (internal network)

## How to View Diagrams

### Option 1: PlantUML Online Server
Visit: http://www.plantuml.com/plantuml/uml/

Paste the contents of any `.puml` file.

### Option 2: VS Code Extension
Install: [PlantUML Extension](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)

Open any `.puml` file and press `Alt+D` to preview.

### Option 3: Command Line (Generate PNG)
```bash
# Install PlantUML
sudo apt install plantuml

# Generate PNG for single diagram
plantuml UML/01_manual_control.puml

# Generate all diagrams
plantuml UML/*.puml

# Output will be: UML/01_manual_control.png, etc.
```

### Option 4: Docker (No Installation)
```bash
# Generate PNG using Docker
docker run -v $(pwd)/UML:/data plantuml/plantuml:latest -tpng /data/*.puml

# Output: PNG files in UML/ directory
```

## Key Concepts Illustrated

### Docker Networking
- **Bridge Networks**: Isolated container networks
- **External Networks**: Reference to networks from other stacks
- **Container Name Resolution**: Docker DNS for inter-container communication
- **Port Mapping**: Internal ports (502, 8000) vs external ports (5020, 8002, 8080)

### Async Architecture
- **Background Tasks**: asyncio tasks for polling and AI control
- **Non-blocking**: Multiple concurrent operations
- **Event Loop**: Continuous operation without blocking API

### Error Resilience
- **Graceful Degradation**: Continue operation with fallback values
- **Automatic Retry**: Reconnection and retry on failures
- **No Crash Policy**: Catch all exceptions, log, continue

### API Patterns
- **RESTful Endpoints**: Standard HTTP methods (GET, POST)
- **Status Polling**: Regular status checks every 10s (UI) / 5s (backend)
- **Immediate Refresh**: 500ms verification after user actions
- **Optimistic UI**: Show change immediately, verify after

## Diagram Conventions

- **alt/else**: Alternative flows (success/failure)
- **opt**: Optional steps (only if condition met)
- **loop**: Repeating sequences (polling, background tasks)
- **note**: Additional explanations and context
- **activate/deactivate**: Component lifecycle
- **dotted lines**: Asynchronous or indirect communication

## Related Documentation

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture overview
- [README.md](../README.md) - User guide and setup instructions
- [CHANGELOG.md](../CHANGELOG.md) - Version history and changes

## Version

**Diagrams Version**: v0.9.0
**Last Updated**: 2025-10-18
**Corresponds to**: Prometheus metrics integration and LG Auto mode offset support
