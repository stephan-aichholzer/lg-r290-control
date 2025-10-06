# Changelog

All notable changes to this project will be documented in this file.

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
