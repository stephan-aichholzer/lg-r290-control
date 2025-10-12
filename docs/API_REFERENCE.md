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

### Set Flow Temperature (Manual Mode)
```bash
curl -X POST http://localhost:8002/setpoint \
  -H "Content-Type: application/json" \
  -d '{"temperature": 35.0}'
```

### Enable AI Mode
```bash
curl -X POST http://localhost:8002/ai-mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Get AI Mode Status
```bash
curl http://localhost:8002/ai-mode
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
| `/registers/raw` | GET | Raw Modbus registers | Debug |
| `/ai-mode` | GET | Get AI Mode status | AI Mode |
| `/ai-mode` | POST | Enable/disable AI Mode | AI Mode |
| `/ai-mode/reload-config` | POST | Reload heating curves | AI Mode |
| `/schedule` | GET | Get scheduler status | Scheduler |
| `/schedule/reload` | POST | Reload schedule config | Scheduler |

---

## API Tags

Endpoints are organized by tags:
- **System**: Service health and info
- **Heat Pump**: Direct heat pump control
- **AI Mode**: Automatic flow temperature control
- **Scheduler**: Time-based scheduling
- **Debug**: Low-level debugging tools

---

## Common Workflows

### 1. Monitor System
```bash
# Check health
curl http://localhost:8002/health

# Get current status
curl http://localhost:8002/status

# Check AI Mode
curl http://localhost:8002/ai-mode
```

### 2. Manual Control
```bash
# Disable AI Mode
curl -X POST http://localhost:8002/ai-mode \
  -d '{"enabled": false}'

# Set temperature manually
curl -X POST http://localhost:8002/setpoint \
  -d '{"temperature": 40.0}'
```

### 3. Automatic Control (AI Mode)
```bash
# Enable AI Mode
curl -X POST http://localhost:8002/ai-mode \
  -d '{"enabled": true}'

# System now automatically adjusts based on:
# - Outdoor temperature
# - Room temperature
# - Heating curve
```

### 4. Configuration Management
```bash
# Reload heating curves (no restart needed)
curl -X POST http://localhost:8002/ai-mode/reload-config

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
- [AI Mode Documentation](./AI_MODE.md)
- [Heat Pump Control](./HEAT_PUMP_CONTROL.md)
- [Deployment Guide](./DEPLOYMENT.md)
