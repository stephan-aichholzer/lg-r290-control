# TODO - Future Improvements

## Code Refactoring

### Refactor service/main.py (Priority: Medium)
**Status**: Deferred - Current implementation is working
**Complexity**: Low-Medium risk refactoring
**Estimated effort**: 2-3 hours

**Current state**:
- `service/main.py` - 781 lines (largest Python file)
- Mixes concerns: API routes, models, metrics, app initialization

**Proposed split**:
1. `service/models.py` - Pydantic models (~70 lines)
   - HeatPumpStatus, PowerControl, TemperatureSetpoint, AutoModeOffset, AIModeControl

2. `service/metrics.py` - Prometheus metrics (~80 lines)
   - Gauge definitions, update_prometheus_metrics()

3. `service/routes/heatpump.py` - Heat pump control endpoints (~200 lines)
   - /status, /power, /setpoint, /auto-mode-offset, /registers/raw

4. `service/routes/ai_mode.py` - AI mode endpoints (~60 lines)
   - /ai-mode, /heating-curve/reload

5. `service/routes/scheduler.py` - Scheduler endpoints (~60 lines)
   - /schedule/status, /schedule/reload

6. `service/main.py` - Main app initialization (~200 lines)
   - FastAPI app, CORS, lifespan, global clients, route registration

**Benefits**:
- Better code organization and maintainability
- Easier to locate specific functionality
- Clearer separation of concerns
- Improved testability

**Risks**:
- Circular import issues (mitigate with dependency injection)
- Requires Docker rebuild and testing
- Global state management (modbus_client, adaptive_controller, scheduler)

**Testing plan**:
1. Create feature branch from current state
2. Split one module at a time
3. Rebuild Docker after each split
4. Test all API endpoints
5. Commit incrementally for easy rollback

**Note**: Added 2025-10-18 during feature/write_to_lg development

---

## Features

### Enable Power Control Write
**Status**: Not started
**Priority**: Low (AI mode handles power automatically)
**Safety consideration**: Requires careful testing

Currently power control endpoint is read-only. Could be enabled similar to offset adjustment.

### Enable Temperature Setpoint Write
**Status**: Not started
**Priority**: Low (AI mode handles temperature automatically)
**Safety consideration**: Requires mode detection (only write in Heat/Cool modes, not Auto)

Currently temperature setpoint endpoint is read-only.

---

## Documentation

### API Documentation
**Status**: Partial (FastAPI auto-docs)
**Priority**: Low

Consider adding:
- Postman/Insomnia collection
- OpenAPI spec export
- Usage examples

---

## Operations

### Monitoring & Alerting
**Status**: Partial (Prometheus metrics exposed)
**Priority**: Medium

Could add:
- Grafana dashboard JSON export
- Alert rules for error conditions
- Health check improvements

---

*This file tracks ideas for future improvements. Not all items may be implemented.*
