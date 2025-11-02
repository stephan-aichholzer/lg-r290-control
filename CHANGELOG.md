# Changelog

All notable changes to the LG R290 Heat Pump Control System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v1.1] - 2025-11-02

**Status**: Power Management and Enhanced Monitoring

### Added

**Power Management:**
- Automatic heat pump ON/OFF based on outdoor and room temperature thresholds
- Configurable sensor sources: Choose between Shelly BLU sensors (temp_indoor, temp_outdoor, temp_buffer) or heat pump ODU sensor (temp_odu)
- Thermostat mode synchronization: Automatically sets thermostat to OFF/AUTO with power state changes
- Hysteresis to prevent rapid cycling (1°C gap between ON/OFF thresholds)
- Configurable check interval (default: 5 minutes)
- Transparent logging with sensor names and values

**Monitoring:**
- Flow rate monitoring (L/min) added to Prometheus metrics
- Water pressure monitoring (bar) added to Prometheus metrics
- Enhanced metrics export for Grafana visualization
- All metrics prefixed with `heatpump_`

**Scheduling:**
- Friday-specific schedule support
- Separate scheduling configuration for different weekdays

**Documentation:**
- Complete documentation update for power management and Prometheus features
- New C4 architecture diagrams (context and component)
- New power management sequence diagram
- Updated network architecture diagram (production deployment, removed mock server)
- 13 PNG diagram exports for GitHub viewing
- Updated UML README to v1.1

### Changed
- Network architecture updated to reflect production deployment (no mock server)
- Power manager now supports configurable sensor sources via config.json

### Fixed
- Separate ERROR and WARNING logs from monitor.log
- Improved rotating logs implementation

---

## [v1.0] - 2025-10-21

**Status**: Production ready with LG Auto mode and manual heating control

### Added

**LG Mode Control:**
- Simple toggle between Auto and Manual Heating modes
- LG Auto Mode: Uses LG's internal heating curve with adjustable offset (-5 to +5K)
- Manual Heating Mode: Direct flow temperature control (33-50°C)
- Instant UI response: Mode sections appear immediately (no 30s poll wait)
- Auto startup: Always starts in LG Auto mode on service restart
- Default temperature: Automatically sets 40°C when switching to manual mode

**Thermostat Integration:**
- Offset automatically adjusts based on ECO/AUTO/ON/OFF modes
- JSON configuration: User-editable offset mappings and default temperature
- Backend-only integration with shelly_bt_temp project

**UI/UX Improvements:**
- Safe GUI reload: Page refresh never triggers unwanted mode changes
- Mode logging: All mode changes logged with emoji for easy tracking
- LG Auto toggle switch in Power Control panel
- Status indicator: "Manual Heating" / "LG Auto Mode"
- Instant section switching (offset controls ↔ temperature slider)
- Temperature slider shows default 40°C when entering manual mode
- Status polling syncs mode from backend (safe page reloads)

**Backend:**
- New API endpoints: `/lg-mode` (POST), `/auto-mode-offset` (POST), `/lg-auto-offset-config` (GET)
- Startup function: Automatically sets LG Auto mode on service start
- Config-driven: Default temperatures and offset mappings in `config.json`

### Changed
- Clean architecture: Removed 582 lines of dead-end code (net: -323 lines)
- Improved error handling and retry logic

---

## [v0.7] - 2025-10-10

**Status**: Production ready for wall-mounted kiosk deployment

### Added

**Temperature Display:**
- Temperature Badge Display: Three-column layout (Indoor/Outdoor/Flow)
- Complete thermal awareness: All sensor temperatures visible at a glance
- Badge style UI: Replaced SVG gauges with clean, modern badges
- Color coding: Flow temp in red, ambient temps in white

**UI Enhancements:**
- Increased font sizes: +27-33% for kiosk readability (2-3m viewing distance)
- Larger status indicators: 16px text, 12px LED dots (was 12px/10px)
- Perfect visibility from across the room

**Temperature Display Sizes:**
- Indoor: 32px values from thermostat sensors (60s polling)
- Outdoor: 32px values from thermostat sensors (60s polling)
- Flow: 32px values from heat pump (10s polling)
- Landscape: 24px values (still highly readable)

**Font Size Improvements:**
- Temperature badge labels: 11px → 14px (+27%)
- Temperature badge values: 24px → 32px (+33%)
- Status badge text: 12px → 16px (+33%)
- Status LED dots: 10px → 12px (+20%)

---

## [v0.6] - 2025-10-10

### Added
- Performance optimization: 97% reduction in API requests (2s → 10s polling)
- Anti-flickering: Smart DOM updates only when values change
- Immediate feedback: 500ms refresh on all user actions
- Battery friendly: 80% reduction in browser CPU usage
- Network efficient: Reduced from 259,200 to 8,640 API requests per day

---

## [v0.5] - 2025-10-10

### Added

**Thermostat Integration:**
- Room thermostat control with 4 modes (AUTO, ECO, ON, OFF)
- Temperature control: 0.5°C step control (18-24°C range)
- Circulation pump monitoring: Integrated with thermostat status

**Architecture:**
- Modular architecture: ES6 modules (config, utils, heatpump, thermostat)
- Unified status badges: Consistent LED-style indicators for all three statuses
- CORS support: Cross-origin integration with external thermostat API

**UI:**
- Compact layout: Optimized for landscape mobile - fits without scrolling

---

## [v0.4] - 2025-10-06

### Added

**Kiosk Mode:**
- Real-time slider synchronization for kiosk mode
- Temperature slider updates automatically when changed externally
- Perfect for wall-mounted tablets/phones
- Auto-updates every 2 seconds including slider position
- Syncs with external changes (LG app, terminal, other clients)
- Smooth user interaction without update conflicts

**Monitoring:**
- Complete register monitoring (target temp, water pump status)
- Optimized 2×2 landscape layout with 50% larger gauges
- Touch and mouse event support for mobile and desktop

**System:**
- Complete Docker stack with mock server, API, and UI
- Power ON/OFF control with status feedback
- Temperature monitoring (flow, return, outdoor, target)
- System metrics (flow rate, pressure, operating mode, pump status)
- Temperature setpoint control with real-time sync
- Dark mode responsive UI optimized for kiosk displays
- Network-accessible from any device on LAN
- All registers properly read and monitored

---

## [v0.3] - 2025-10-05

### Added
- Production deployment on real LG R290 hardware via Waveshare RS485-to-Ethernet gateway
- Multi-day stable operation verified
- All register readings confirmed with actual heat pump
- Production kiosk deployment complete
- Prometheus metrics integration active

**Hardware Integration:**
- Real hardware via Modbus TCP (no mock server needed in production)
- Waveshare gateway at 192.168.2.10:8899
- LG R290 device ID: 5
- Production monitoring and health checks

---

## [v0.2] - 2025-10-04

### Added
- Mock Modbus server for development/testing
- FastAPI backend with async Modbus client
- Basic web UI with temperature gauges
- Docker Compose orchestration

---

## [v0.1] - 2025-10-03

### Added
- Initial project setup
- Modbus register discovery
- Basic proof-of-concept scripts
- Documentation started
