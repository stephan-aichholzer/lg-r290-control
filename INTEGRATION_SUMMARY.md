# Docker Stack Integration - Complete Summary

## ✅ What Was Updated

### `service/modbus_client.py` - Production-Ready Modbus Client

#### 1. **Added Critical Register Definitions**
```python
HOLDING_CONTROL_METHOD = 1   # 40002: Control Method
HOLDING_ENERGY_STATE = 9     # 40010: Energy State Input (CRITICAL)
```

#### 2. **Added Retry Logic with Comprehensive Error Handling**
New method: `_modbus_operation_with_retry()`
- 3 retry attempts with exponential backoff (2s, 4s, 6s)
- Handles bus collisions (shared RS-485 with WAGO meter)
- Catches corrupted responses: `IndexError`, `struct.error`, `ValueError`
- Handles network errors: `ConnectionError`, `OSError`, `asyncio.TimeoutError`
- Handles Modbus protocol errors: `ModbusException`
- **Proper logging** at each retry attempt with clear operation names

#### 3. **Enhanced Polling Loop**
- **Critical documentation**: Polling maintains external control mode
- Consecutive failure tracking (max 5 failures before reconnect)
- Automatic reconnection on repeated failures
- **Warning logged** if polling cancelled (heat pump will shut down!)
- Returns success/failure boolean for monitoring

#### 4. **Updated `_update_cached_data()` Method**
- Uses retry logic for ALL Modbus operations
- Reads Energy State register (40010) - **CRITICAL**
- Warns if Energy State changes unexpectedly
- Better error handling with detailed logging
- Returns `True`/`False` for success tracking

#### 5. **Critical: Energy State Initialization in `set_power()`**
When turning heat pump ON for first time:
1. **Sets Energy State = 5** (ON-Command Step2) - Required!
2. Sets Control Method = 0 (Water outlet control)
3. Sets Operating Mode = 4 (Heating)
4. Tracks initialization with `_energy_state_initialized` flag
5. **Detailed logging** for each step

#### 6. **Enhanced `set_target_temperature()`**
- Uses retry logic
- Validates temperature range (20-60°C)
- Better error logging
- Updates cached value on success

#### 7. **Added to Status Response**
```python
'energy_state': self._cached_data.get('energy_state', 0)
```

## 🎯 Key Features

### Continuous Polling (24/7)
- **Starts at service startup** - NOT when heat pump turns ON
- **Never stops** - Runs regardless of heat pump ON/OFF state
- **Maintains external control mode** - Prevents CH03 error
- **Auto-reconnects** on connection failures

### Robust Error Handling
✅ Bus collisions handled gracefully (WAGO + LG sharing RS-485)
✅ Corrupted packet detection and retry
✅ Network timeout recovery
✅ Automatic reconnection with exponential backoff
✅ Comprehensive logging for debugging

### Energy State Management
✅ Automatically set to 5 on first power-on
✅ Continuously monitored during polling
✅ Warns if value changes unexpectedly
✅ Required for heat pump to stay running

## 📝 Logging Levels

### INFO Level:
- Connection established/disconnected
- Polling loop started
- Power ON/OFF successful
- Temperature set successful
- Energy State initialized
- Reconnection successful

### WARNING Level:
- Poll failed (with retry counter)
- Connection lost (before reconnect attempt)
- Energy State changed unexpectedly
- Non-critical register read failures

### ERROR Level:
- Connection failed after retries
- Register read/write failed after retries
- Too many consecutive failures
- Invalid temperature range

### DEBUG Level:
- Temperature readings each poll
- Target temperature
- Cache updated confirmation

## 🔧 What You Need To Do

### 1. Update `main.py` to Start Polling at Startup

```python
@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    global modbus_client

    # Connect to heat pump
    if await modbus_client.connect():
        logger.info("✅ Connected to heat pump")

        # Start continuous polling - CRITICAL for external control mode
        modbus_client.start_polling()
        logger.info("✅ Polling started - heat pump in external control mode")
    else:
        logger.error("❌ Failed to connect to heat pump")
```

### 2. Verify Poll Interval in docker-compose.yml

```yaml
environment:
  - POLL_INTERVAL=${POLL_INTERVAL:-10}  # 10 seconds recommended
```

**Note:** The standalone `keep_alive.py` uses 10 seconds. Docker service can use the same.

### 3. Update Any Existing Control Logic

The `set_power()` method now handles Energy State initialization automatically.
No changes needed to existing API endpoints - they'll just work!

## ✅ What's Already Working

### From `modbus_client.py`:
- ✅ Polling loop with cache
- ✅ Connection management
- ✅ `get_cached_status()` for non-blocking reads
- ✅ Basic power and temperature control

### What We Added:
- ✅ Energy State register support
- ✅ Retry logic for bus collisions
- ✅ Auto-reconnection on failures
- ✅ Comprehensive error handling
- ✅ Detailed logging
- ✅ Energy State initialization

## 🧪 Testing Checklist

### Before Starting Docker Stack:
1. ✅ Standalone `keep_alive.py` tested (30+ minutes, stable)
2. ✅ Energy State = 5 confirmed working
3. ✅ Continuous polling requirement proven
4. ✅ Error handling tested (bus collisions, reconnects)

### After Starting Docker Stack:
1. Check logs for successful connection
2. Verify polling started
3. Turn heat pump ON via API
4. Check Energy State initialization in logs
5. Monitor for 30+ minutes for stability
6. Test temperature changes
7. Test power OFF
8. Verify no CH03 error appears

### Expected Log Output on Startup:
```
INFO: Connected to Modbus TCP at 192.168.2.10:8899
INFO: Started polling task (interval: 10s)
INFO: Starting continuous polling loop - CRITICAL for external control mode
DEBUG: Temperatures - Flow: 25.0°C, Return: 24.5°C, Outdoor: 10.0°C
DEBUG: Target temp: 40.0°C
DEBUG: Poll successful - cache updated
```

### Expected Log Output When Turning ON:
```
INFO: Initializing Energy State for external control (required on first turn-on)
INFO: ✅ Energy State initialized to 5 (ON-Command Step2)
INFO: ✅ Heat pump initialization complete - ready for external control
INFO: ✅ Heat pump power set to ON
```

## 📊 Comparison: Standalone vs Docker Integration

| Feature | keep_alive.py | modbus_client.py |
|---------|---------------|------------------|
| Polling interval | 10s | 10s (configurable) |
| Energy State init | Manual (fallback_control.py) | Automatic (on first ON) |
| Retry logic | ✅ 3 attempts | ✅ 3 attempts |
| Auto-reconnect | ✅ Yes | ✅ Yes |
| Error handling | ✅ Comprehensive | ✅ Comprehensive |
| Logging | ✅ Detailed | ✅ Detailed |
| Integration | Standalone script | FastAPI service |

## 🎯 Architecture

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Service (main.py)                               │
│  ├─> startup_event(): Start polling                     │
│  ├─> POST /control/power → modbus_client.set_power()    │
│  ├─> POST /control/temp → modbus_client.set_target()    │
│  └─> GET /status → modbus_client.get_cached_status()    │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│ HeatPumpModbusClient (modbus_client.py)                 │
│                                                          │
│  Background Task (Runs Forever):                        │
│  ┌────────────────────────────────────────────┐        │
│  │ _poll_loop()                                │        │
│  │  while True:                                │        │
│  │    _update_cached_data() # Every 10s        │        │
│  │    → Maintains external control mode        │        │
│  │    → Prevents CH03 error                    │        │
│  │    → Auto-reconnects on failure             │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
│  Control Methods:                                        │
│  ├─> set_power(on/off)                                  │
│  │    └─> Initializes Energy State = 5 on first ON     │
│  └─> set_target_temperature(temp)                       │
│                                                          │
│  All operations use retry logic:                        │
│  └─> _modbus_operation_with_retry()                     │
│       ├─> 3 attempts                                    │
│       ├─> Exponential backoff                           │
│       ├─> Handles bus collisions                        │
│       └─> Comprehensive error handling                  │
└─────────────────────────────────────────────────────────┘
```

## 🔥 Critical Success Factors

### 1. Polling Must Never Stop
The polling loop maintains the "channel" to the heat pump. Without it:
- Heat pump shuts down within ~60 seconds
- CH03 error appears on touchscreen
- External control is lost

### 2. Energy State Must Be Set
Register 40010 must equal 5 for external control:
- Set automatically on first power-on
- Monitored continuously during polling
- Required for heat pump to stay running

### 3. Retry Logic Is Essential
Shared RS-485 bus with WAGO meter requires:
- Retry on failures (bus collisions)
- Exponential backoff
- Response validation
- Auto-reconnection

## 📚 References

- **MODBUS_JOURNEY.md** - Complete discovery story
- **keep_alive.py** - Proven standalone implementation
- **fallback_control.py** - Manual control reference
- **dump_all_registers.py** - Diagnostic tool

## 🎉 Status: READY FOR TESTING

All critical changes complete. The Docker service now has:
- ✅ All proven logic from standalone scripts
- ✅ Energy State initialization
- ✅ Continuous polling (24/7)
- ✅ Comprehensive error handling
- ✅ Detailed logging
- ✅ Auto-reconnection
- ✅ Retry logic for bus collisions

**Next Step:** Test with real hardware! 🚀
