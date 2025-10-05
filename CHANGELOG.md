# Changelog

All notable changes to this project will be documented in this file.

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
