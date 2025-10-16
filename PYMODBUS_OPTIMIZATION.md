# PyModbus Optimization for Shared RS-485 Bus

## Current Setup Analysis

**Environment:**
- PyModbus version: 3.6.9
- Connection: Modbus TCP → Waveshare RS232/RS485 Gateway
- Shared RS-485 bus: LG Heat Pump (Device ID 7) + WAGO Energy Meter
- Current timeout: 30 seconds
- Current retries: 3 attempts
- Retry backoff: Exponential (2s, 4s, 6s)

**Observed Issues:**
1. `list index out of range` - Incomplete Modbus responses (retry recovers)
2. `unpack requires a buffer of 2 bytes` - Corrupted packets with full tracebacks
3. Verbose error logging clutters logs despite successful retries

## PyModbus Advanced Configuration Options

### Available AsyncModbusTcpClient Parameters

**Currently Used:**
- `host` - Gateway IP (192.168.2.10) ✓
- `port` - Modbus port (8899) ✓
- `timeout` - 30 seconds ✓

**Not Currently Used:**
- `retries` - Built-in retry mechanism (default: 3)
- `reconnect_delay` - Min reconnection delay (default: 0.1s)
- `reconnect_delay_max` - Max reconnection delay (default: 300s)
- `source_address` - Client bind address
- `name` - Logger name for debugging
- `trace_packet` - Callable to intercept bytestream
- `trace_pdu` - Callable to intercept PDU data
- `trace_connect` - Callable for connection events

### Key Findings

1. **PyModbus has built-in retry logic** - We're implementing manual retry on top
2. **Reconnect delay uses exponential backoff** - Automatically doubles from `reconnect_delay` to `reconnect_delay_max`
3. **Logging can be suppressed per namespace** - Control client, server, protocol logging separately

## Recommended Improvements

### 1. Optimize Timeout Settings

**Problem:** 30-second timeout is excessive for local network
**Impact:** Slower recovery from bus collisions

**Recommendation:**
```python
# Reduce timeout to 5-10 seconds
client = AsyncModbusTcpClient(
    host=GATEWAY_IP,
    port=MODBUS_PORT,
    timeout=5,        # ← Reduce from 30s
    retries=3,        # ← Use built-in retries
    reconnect_delay=0.5,     # ← Start with 500ms
    reconnect_delay_max=10   # ← Cap at 10s
)
```

**Rationale:**
- Local network response should be <1s under normal conditions
- 30s timeout means waiting 30s for each timeout × 3 retries = 90s recovery time
- 5s timeout × 3 retries = 15s recovery time (6× faster)
- Shared bus collisions should resolve within 1-2 seconds

### 2. Suppress PyModbus Internal Error Logging

**Problem:** PyModbus logs full tracebacks for recoverable errors
**Impact:** Log files filled with noise despite successful retries

**Recommendation:**
```python
# In monitor_and_keep_alive.py and lg_r290_modbus.py
import logging

# Suppress pymodbus internal errors (keep only CRITICAL)
logging.getLogger('pymodbus').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.client').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.protocol').setLevel(logging.CRITICAL)
```

**Rationale:**
- Retry logic already handles recoverable errors
- Application-level logging (our code) still reports failures
- Eliminates "unpack requires buffer" tracebacks
- Only CRITICAL errors (library bugs) will appear

### 3. Use Built-in Retries Instead of Manual Retry Wrapper

**Problem:** Double retry logic (PyModbus + our wrapper)
**Impact:** Confusion, longer recovery times

**Current Code:**
```python
# lg_r290_modbus.py - manual retry wrapper
async def modbus_operation_with_retry(client, func, *args, **kwargs):
    for attempt in range(MAX_RETRIES):  # ← Manual retry
        result = await func(*args, **kwargs)  # ← PyModbus also retries internally
```

**Recommendation:** **Keep current implementation**

**Rationale:**
- PyModbus built-in retries work at transport layer (TCP reconnect)
- Our retry wrapper handles application-layer errors (Modbus exceptions, corrupt responses)
- Two-tier approach is actually beneficial:
  - PyModbus retries: Network/connection issues
  - Application retries: Bus collisions, corrupt frames
- Our wrapper provides better logging and exponential backoff control

### 4. Reduce Inter-Request Delay for Sequential Reads

**Problem:** 500ms delay between each register read
**Impact:** Slow polling (3× 500ms = 1.5s minimum per poll)

**Current Code:**
```python
# lg_r290_modbus.py
INTER_REQUEST_DELAY = 0.5  # 500ms between requests

await asyncio.sleep(INTER_REQUEST_DELAY)  # Before each read
input_result = await client.read_input_registers(...)
await asyncio.sleep(INTER_REQUEST_DELAY)
holding_result = await client.read_holding_registers(...)
await asyncio.sleep(INTER_REQUEST_DELAY)
coil_result = await client.read_coils(...)
```

**Recommendation:**
```python
# Reduce to 100-200ms - enough to prevent bus congestion
INTER_REQUEST_DELAY = 0.2  # 200ms
```

**Rationale:**
- Modbus RTU spec requires 3.5 character times between frames (~4ms at 9600 baud)
- RS-485 turnaround time: ~0.6ms for direction control
- WAGO meter likely polls every 1-2 seconds
- 200ms provides 50× safety margin while speeding up our polls

### 5. Add Logging Name for Debugging

**Problem:** Hard to distinguish multiple client instances in logs
**Solution:** Use `name` parameter

**Recommendation:**
```python
client = AsyncModbusTcpClient(
    host=GATEWAY_IP,
    port=MODBUS_PORT,
    timeout=5,
    retries=3,
    name="LG_R290"  # ← Appears in logs
)
```

## Implementation Priority

### High Priority (Immediate Impact)
1. **Suppress PyModbus logging** - Eliminates log noise immediately
2. **Reduce timeout to 5-10s** - Faster recovery from bus collisions
3. **Reduce inter-request delay to 200ms** - Faster polling

### Medium Priority (Nice to Have)
4. **Add client name** - Better debugging
5. **Configure reconnect delays** - Tune reconnect behavior

### Low Priority (Already Optimal)
6. Keep current retry wrapper - Working well for shared bus

## Expected Results

**Before:**
- Poll cycle: ~2 seconds (with delays)
- Recovery from timeout: 90 seconds (30s × 3 retries)
- Logs: Verbose PyModbus tracebacks

**After:**
- Poll cycle: ~1 second (faster delays)
- Recovery from timeout: 15 seconds (5s × 3 retries)
- Logs: Clean application-level messages only

## Testing Plan

1. Apply logging suppression first (no risk, immediate benefit)
2. Reduce timeout to 5s and test for 24 hours
3. Reduce inter-request delay to 200ms and test for 24 hours
4. Monitor `monitor.log` for error frequency
5. Verify supervision loop still catches daemon crashes

## Code Changes Required

### File: `lg_r290_modbus.py`
- Add PyModbus logging suppression
- Change `TIMEOUT = 5` (from 30)
- Change `INTER_REQUEST_DELAY = 0.2` (from 0.5)
- Add `name="LG_R290"` to client init
- Add `retries=3` to client init (explicit)
- Add `reconnect_delay=0.5` to client init
- Add `reconnect_delay_max=10` to client init

### File: `monitor_and_keep_alive.py`
- Add PyModbus logging suppression at startup

## References

- PyModbus 3.6.9 Documentation: https://pymodbus.readthedocs.io/en/v3.6.9/
- Modbus RTU Timing Spec: 3.5 character times between frames
- RS-485 Bus Arbitration: Half-duplex, collision detection via timeout
