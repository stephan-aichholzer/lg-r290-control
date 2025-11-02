# LG R290 Control System - UML Sequence Diagrams

This folder contains PlantUML sequence diagrams documenting all major use cases and data flows in the LG R290 Heat Pump Control System.

## Diagram Overview

### Architecture Diagrams (C4 Model)
| Diagram | Description | Type |
|---------|-------------|------|
| **00_context_diagram.puml** | System boundaries and external integrations | C4 Context |
| **00_component_diagram.puml** | Internal component architecture and data flows | C4 Component |

### Sequence Diagrams (Operational Flows)
| Diagram | Description | Key Actors |
|---------|-------------|------------|
| **01_manual_control.puml** | Manual temperature setpoint adjustment (Heating mode) | User, UI, API, Modbus, Heat Pump |
| **03_power_control.puml** | Heat pump power ON/OFF control | User, UI, API, Modbus |
| **04_startup_initialization.puml** | Docker Compose stack startup sequence | Docker, All Services |
| **05_thermostat_integration.puml** | Thermostat integration and cross-stack communication | UI, API, Thermostat, Sensor |
| **06_config_reload.puml** | Configuration hot-reload for schedule.json | Scheduler, Config |
| **07_error_handling.puml** | Error scenarios and recovery strategies | Monitor Daemon, All Services |
| **08_network_architecture.puml** | Docker network topology and communication paths (production) | All Services, Networks |
| **09_scheduler_control.puml** | Time-based automatic temperature scheduling | Scheduler, Thermostat API, schedule.json |
| **10_lg_auto_mode_offset.puml** | LG Auto mode temperature offset adjustment (±5K) | User, UI, API, Modbus, Heat Pump |
| **11_prometheus_metrics.puml** | Prometheus metrics integration and Grafana monitoring | Monitor Daemon, Prometheus, Grafana |
| **12_power_management.puml** | Automatic power control based on temperature thresholds | Power Manager, Thermostat API, Modbus |

### PNG Exports
All diagrams are also available as PNG images in the `png/` subfolder for easy viewing on GitHub.

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

### 2. System Context (`00_context_diagram.puml`)
**Scenario**: C4 System Context diagram showing boundaries
- External actors (User, LG R290 Heat Pump)
- External systems (Thermostat API, Prometheus/Grafana)
- System boundaries and integration points
- Communication protocols (Modbus TCP, HTTP REST)

**Key External Systems**:
- **shelly-blu-ht**: External thermostat project providing sensor data
- **Prometheus/Grafana**: Monitoring and visualization
- **LG R290**: Heat pump via Waveshare RS485-to-Ethernet gateway

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
- FastAPI service startup
- Modbus client connection to Waveshare gateway
- Configuration loading (config.json, schedule.json)
- Background tasks startup (polling, scheduler, power management)
- Prometheus metrics initialization
- UI container startup (Nginx)

**Components**:
- heatpump-service (FastAPI)
- heatpump-ui (Nginx static files)

**External Hardware**:
- LG R290 via Waveshare RS485-to-Ethernet gateway (192.168.2.10:8899)

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
**Scenario**: Reload schedule configuration without container restart
- User edits schedule.json (time-based schedules)
- POST request to /schedule/reload endpoint
- Scheduler validates and reloads configuration
- Changes take effect immediately
- No container restart required

**Key Endpoints**:
- `POST /schedule/reload` - Reload schedule.json

**Note**: LG Mode config (config.json) requires container rebuild for changes to take effect.

### 7. Error Handling (`07_error_handling.puml`)
**Scenario**: Various failure modes and recovery strategies
- Heat pump connection lost → retry automatically
- Thermostat API unavailable → use default offset (0K)
- Modbus write failure → retry next cycle
- Power control failure → skip adjustment
- Monitor daemon crash → supervision loop restarts

**Recovery Strategy**:
- Never crash entire service
- Log all errors with details
- Use fallback values when possible
- Automatic retry on next cycle
- Graceful degradation
- Health checks and auto-restart

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
- Flow rate and water pressure metrics
- Status metrics (power, compressor, pump, mode, errors)
- All metrics prefixed with `heatpump_`

**Network Integration**:
- lg_r290_service joins modbus_default network
- Prometheus uses Docker DNS: lg_r290_service:8000
- No port mapping needed (internal network)

### 12. Power Management (`12_power_management.puml`)
**Scenario**: Automatic heat pump power control based on outdoor and room temperature thresholds
- Background task checks every 5 minutes (configurable)
- Reads temperatures from configurable sensor sources
- Evaluates turn ON/OFF conditions with hysteresis
- Synchronizes thermostat mode (OFF when heat pump OFF, AUTO when ON)
- Prevents circulation pump waste

**Sensor Sources (configurable)**:
- `temp_indoor` - Shelly BLU indoor sensor
- `temp_outdoor` - Shelly BLU outdoor sensor (default)
- `temp_buffer` - Shelly BLU buffer tank sensor
- `temp_odu` - Heat pump ODU sensor (Modbus)

**Turn OFF Logic** (both conditions must be met):
- outdoor_temp ≥ 15.0°C
- room_temp ≥ 21.5°C

**Turn ON Logic** (both conditions must be met):
- outdoor_temp < 14.0°C
- room_temp < 21.5°C

**Key Features**:
- Hysteresis prevents rapid cycling (1°C gap)
- Flexible sensor selection via config.json
- Mode synchronization with thermostat
- Transparent logging with sensor names and values

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
docker run --rm -v $(pwd)/UML:/data plantuml/plantuml:latest -tpng -o png "/data/*.puml"

# Output: PNG files in UML/png/ directory
```

### Option 5: Pre-generated PNG Images
All diagrams are available as PNG images in the `png/` subfolder. These are updated whenever diagrams are modified and can be viewed directly on GitHub without any tools.

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

## Version

**Diagrams Version**: v1.1
**Last Updated**: 2025-11-02
**Corresponds to**: LG Mode Control system with Power Management and Prometheus integration

**Recent Updates**:
- Added C4 Context and Component diagrams (00_*)
- Added Power Management diagram (12_*)
- Updated Network Architecture diagram (removed mock server)
- Removed obsolete AI Mode diagram (02_*)
- Added PNG exports in `png/` subfolder
- Updated to reflect production deployment configuration
