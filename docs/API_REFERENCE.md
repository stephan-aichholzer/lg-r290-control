# API Reference

## Interactive Documentation

The complete API reference is available via OpenAPI/Swagger:

### **Live Interactive Docs**
- **Swagger UI**: http://localhost:8002/docs
  - Try endpoints directly in browser
  - See request/response examples
  - Test with "Try it out" button
  - Complete descriptions and examples

### **OpenAPI Specification**
- **File**: [`openapi.yaml`](./openapi.yaml)
- **Format**: OpenAPI 3.1.0
- **Use with**: Postman, Insomnia, API clients, code generators

---

## Quick Examples

### Get Heat Pump Status
```bash
curl http://localhost:8002/status
```

### Turn Heat Pump ON
```bash
curl -X POST http://localhost:8002/power \
  -H "Content-Type: application/json" \
  -d '{"power_on": true}'
```

### Set Flow Temperature (Manual Heating Mode)
```bash
curl -X POST http://localhost:8002/setpoint \
  -H "Content-Type: application/json" \
  -d '{"temperature": 35.0}'
```

### Set LG Mode (Auto/Heating)
```bash
# Switch to LG Auto mode
curl -X POST http://localhost:8002/lg-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": 3}'

# Switch to Manual Heating mode
curl -X POST http://localhost:8002/lg-mode \
  -H "Content-Type: application/json" \
  -d '{"mode": 4}'
```

### Adjust Auto Mode Offset
```bash
curl -X POST http://localhost:8002/auto-mode-offset \
  -H "Content-Type: application/json" \
  -d '{"offset": 2}'
```

### Get Scheduler Status
```bash
curl http://localhost:8002/schedule
```

---

## API Endpoints Overview

| Endpoint | Method | Description | Tag |
|----------|--------|-------------|-----|
| `/` | GET | API information | System |
| `/health` | GET | Health check | System |
| `/status` | GET | Heat pump status | Heat Pump |
| `/power` | POST | Control power ON/OFF | Heat Pump |
| `/setpoint` | POST | Set flow temperature | Heat Pump |
| `/lg-mode` | POST | Set LG mode (Auto=3, Heating=4) | Heat Pump |
| `/auto-mode-offset` | POST | Adjust Auto mode offset (±5K) | Heat Pump |
| `/registers/raw` | GET | Raw Modbus registers | Debug |
| `/schedule` | GET | Get scheduler status | Scheduler |
| `/schedule/reload` | POST | Reload schedule config | Scheduler |

---

## API Tags

Endpoints are organized by tags:
- **System**: Service health and info
- **Heat Pump**: Direct heat pump control (Manual and LG Auto modes)
- **Scheduler**: Time-based scheduling
- **Debug**: Low-level debugging tools

---

## Common Workflows

### 1. Monitor System
```bash
# Check health
curl http://localhost:8002/health

# Get current status (includes mode, offset, temperatures)
curl http://localhost:8002/status
```

### 2. LG Auto Mode Control
```bash
# Switch to LG Auto mode
curl -X POST http://localhost:8002/lg-mode \
  -d '{"mode": 3}'

# Adjust offset to make it warmer
curl -X POST http://localhost:8002/auto-mode-offset \
  -d '{"offset": 2}'

# LG heat pump now controls flow temp using:
# - Internal heating curve
# - Outdoor temperature
# - +2K offset adjustment
```

### 3. Manual Heating Mode
```bash
# Switch to Manual Heating mode
curl -X POST http://localhost:8002/lg-mode \
  -d '{"mode": 4}'

# Set specific flow temperature
curl -X POST http://localhost:8002/setpoint \
  -d '{"temperature": 40.0}'
```

### 4. Configuration Management
```bash
# Reload schedule (no restart needed)
curl -X POST http://localhost:8002/schedule/reload
```

---

## Response Format

All endpoints return JSON:

**Success Response:**
```json
{
  "status": "success",
  ...
}
```

**Error Response:**
```json
{
  "detail": "Error message"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (Modbus disconnected) |

---

## Architecture

```
┌─────────────┐     Modbus TCP      ┌──────────────┐
│  LG R290    │◄────────────────────┤   Service    │
│  Heat Pump  │                     │   (FastAPI)  │
└─────────────┘                     └──────┬───────┘
                                          │
                                          │ REST API
                                          │
┌──────────────┐                     ┌────▼────────┐
│  Thermostat  │◄────────────────────┤     UI      │
│ (Shelly BT)  │     REST API        │   (nginx)   │
└──────────────┘                     └─────────────┘
```

---

## More Information

For detailed endpoint descriptions, request/response schemas, and examples:

→ **Visit http://localhost:8002/docs**

For feature-specific documentation:
- [Scheduler Documentation](./SCHEDULER.md)
- [Heat Pump Control](./HEAT_PUMP_CONTROL.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Thermostat Integration](./THERMOSTAT_INTEGRATION.md)
