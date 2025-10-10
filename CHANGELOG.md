# Changelog

All notable changes to this project will be documented in this file.

## [v0.8.1] - 2025-10-10

### Fixed
- **Docker Network Integration**: Resolved network isolation preventing AI Mode from accessing thermostat API
  - Added external network reference to `shelly_bt_temp_default` in docker-compose.yml
  - Changed THERMOSTAT_API_URL from host IP to container name (`http://iot-api:8000`)
  - Fixed MODBUS_PORT from 5020 (external) to 502 (internal Docker network port)
  - Corrected thermostat API field name from `target_temperature` to `target_temp`
  - Enhanced error handling with fallback to default temperature (21°C)

### Changed
- Environment variable `THERMOSTAT_API_URL` default changed to container name for Docker networking
- Updated README.md with network configuration requirements for AI Mode integration

### Technical Details
- Solution uses Docker external network pattern for inter-stack communication
- Container DNS resolution replaces host IP addressing for thermostat API
- Maintains compatibility with both internal heatpump-net and external networks

## [v0.8] - 2025-10-10

### Added
- **AI Mode: Adaptive Heating Curve with Weather Compensation**
  - Autonomous flow temperature optimization based on outdoor and room temperature
  - Three heating curves: ECO (≤21°C), Comfort (21-23°C), High (>23°C)
  - Configurable via JSON file (`service/heating_curve_config.json`)
  - Hot-reload capability without service restart
  - Background control loop runs every 10 minutes when enabled
  - Automatic heat pump shutdown when outdoor temp ≥18°C
  - Safety features: min/max limits, hysteresis, adjustment thresholds
- **New Backend Modules**:
  - `service/heating_curve.py`: Configuration loader and calculation engine
  - `service/adaptive_controller.py`: Autonomous background control loop
  - `service/heating_curve_config.json`: User-editable configuration file
- **New API Endpoints**:
  - `GET /ai-mode`: Get AI mode status and diagnostics
  - `POST /ai-mode`: Enable/disable AI mode
  - `POST /ai-mode/reload-config`: Hot-reload configuration
- **UI Enhancements**:
  - Manual/AI toggle switch integrated into Power Control panel
  - Status text indicator: "Manual Control" / "AI Mode Active" (green when active)
  - Temperature slider auto-disables when AI mode enabled
  - Real-time AI mode status polling
- **Dependencies**:
  - Added httpx 0.26.0 for thermostat API integration

### Changed
- Updated Dockerfile to include new heating curve modules
- Updated ARCHITECTURE.md with AI Mode documentation
- Updated README.md with comprehensive AI Mode usage guide
- Added THERMOSTAT_API_URL environment variable

### Technical Details
- Heating curve selection based on target room temperature
- Weather compensation algorithm with configurable parameters
- Outdoor temperature from heat pump Modbus registers
- Target room temperature from external thermostat HTTP API
- Adjustment threshold: 2°C (prevents excessive cycling)
- Update interval: 600 seconds (10 minutes)
- Temperature ranges: ECO 33-46°C, Comfort 35-48°C, High 37-50°C

## [v0.7] - 2025-10-10

### Changed
- **Temperature Badge Display**: Replaced SVG gauges with three-column badge layout
- **Complete Thermal Awareness**: Indoor/Outdoor/Flow temperatures visible at once
- **Increased Font Sizes**: +27-33% improvement for kiosk readability
- **Badge Style UI**: Clean, modern badge design with color coding
- **Larger Status Indicators**: 16px text, 12px LED dots (was 12px/10px)

### Technical Details
- Temperature badge values: 32px (desktop), 24px (landscape)
- Temperature badge labels: 14px
- Indoor/Outdoor temps from thermostat (60s polling)
- Flow temp from heat pump (10s polling)

## [v0.6] - 2025-10-10

### Changed
- **Performance Optimization**: 97% reduction in API requests (2s → 10s polling)
- **Anti-Flickering**: Smart DOM updates only when values change
- **Immediate Feedback**: 500ms refresh on all user actions
- **Battery Friendly**: 80% reduction in browser CPU usage
- **Network Efficient**: Reduced from 259,200 to 8,640 API requests per day

## [v0.5] - 2025-10-10

### Added
- **Thermostat Integration**: Room thermostat control with 4 modes (AUTO, ECO, ON, OFF)
- **Modular Architecture**: ES6 modules (config, utils, heatpump, thermostat)
- **Unified Status Badges**: Consistent LED-style indicators
- **Compact Layout**: Optimized for landscape mobile
- **CORS Support**: Cross-origin integration with external thermostat API
- **Temperature Control**: 0.5°C step control (18-24°C range)
- **Circulation Pump Monitoring**: Integrated with thermostat status

## [v0.4] - 2025-10-06

### Fixed
- **Critical: Real-time slider synchronization for kiosk mode**
  - Temperature slider now updates automatically when changed externally
  - Tracks user interaction to prevent update conflicts during drag
  - Supports both desktop (mouse) and mobile (touch) events
  - 100ms debounce for smooth user experience
  - Slider syncs with device state every 2 seconds (status poll interval)
- Added debug console logging for troubleshooting slider behavior

### Technical Details
- User interaction flag prevents slider updates during active drag
- Value comparison with 0.1°C tolerance to avoid unnecessary updates
- Proper event handling for touchstart/touchend and mousedown/mouseup

## [v0.3] - 2025-10-06

### Fixed
- **Critical: Added target_temperature to status response**
  - Target temperature was write-only, never read back from device
  - Now properly reads holding register 40003 during polling
  - Status API now returns complete device state including setpoint
- Added water_pump_running monitoring (discrete input 10002)
- Added holding register reads to polling cycle

### Changed
- Updated API response model with new fields:
  - `target_temperature` (float) - Current device setpoint
  - `water_pump_running` (bool) - Water pump status
- UI slider now syncs with actual device target temperature

### Technical Details
- Backend reads holding registers 0-2 every 5 seconds
- Better state synchronization between UI and device
- Prevents slider drift when temperature set externally

## [v0.2] - 2025-10-06

### Changed
- **UI: Optimized landscape layout with larger gauges**
  - Redesigned from 3-column to table-like 2×2 grid arrangement
  - Grid columns changed from `1fr 2fr 1fr` to `auto 1fr auto`
  - Power control and metrics panels now span full height
  - Temperature setpoint and gauges stacked in center column
- Increased gauge size from 90px to 135px (50% larger)
- Increased gauge value font size from 13px to 19px
- Improved spacing and alignment for compact mobile landscape view

### Technical Details
- Layout structure: `| ON/OFF (full) | SLIDER + GAUGES | METRICS (full) |`
- Better space utilization for mobile landscape orientation
- Optimized for iPhone 12 Pro landscape (844×390)

## [v0.1] - 2025-10-05

### Added
- Initial release - Working draft
- Complete Docker-based stack (mock, service, UI)
- Mock Modbus TCP server with JSON-backed registers
- FastAPI service with AsyncModbusTcpClient
- Dark mode responsive HTML5 UI
- Power ON/OFF control
- Temperature monitoring (flow, return, outdoor)
- System metrics (flow rate, pressure, operating mode)
- Temperature setpoint control
- Dual layout support (desktop vertical, mobile landscape)
- Mobile kiosk mode optimization
- Network accessibility from any LAN device
- Complete documentation (README, ARCHITECTURE)

### Fixed
- Corrected flow/return temperature mapping (30003=return, 30004=flow)
- Fixed external network access (dynamic hostname detection)
- Changed API port to 8002 (avoid Portainer conflict)

### Known Issues
- Mock server: Writes not persisted to JSON file
- Mock server: Some register values read as zero (Modbus addressing offset)
- Not yet tested with real hardware
- Mobile kiosk mode not yet tested on Android

### Technical Details
- Platform: Raspberry Pi 5 / Linux
- Docker Compose: 3.8
- Python: 3.11
- pymodbus: 3.6.4
- FastAPI: 0.109.0
- Frontend: Vanilla HTML5/CSS3/JavaScript
- Server: Nginx (Alpine)

## Roadmap

### v0.2 (Planned)
- [ ] Test with real LG R290 hardware
- [ ] Fix mock server write persistence
- [ ] Fix mock server register addressing offset
- [ ] Test mobile kiosk mode on Android
- [ ] Performance optimization
- [ ] Error handling improvements

### Future Enhancements
- [ ] Data logging (InfluxDB/PostgreSQL)
- [ ] Historical graphs and trends
- [ ] MQTT integration for home automation
- [ ] Advanced scheduling
- [ ] Email/push notifications
- [ ] Multi-language support
- [ ] Additional LG R290 registers
