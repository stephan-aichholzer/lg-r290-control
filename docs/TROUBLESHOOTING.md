# Troubleshooting Guide

This guide consolidates troubleshooting information for the LG R290 Heat Pump Control System.

## Table of Contents

- [Connection Issues](#connection-issues)
- [Modbus Communication](#modbus-communication)
- [Docker & Services](#docker--services)
- [Heat Pump Control](#heat-pump-control)
- [Scheduler Issues](#scheduler-issues)
- [Network & API](#network--api)
- [Hardware Integration](#hardware-integration)

---

## Connection Issues

### Cannot Connect to Modbus Gateway

**Symptoms:**
- `/health` endpoint returns 503
- Logs show "Connection refused" or "Connection timeout"

**Checks:**

1. Verify services are running:
```bash
docker-compose ps
```

2. Check service logs:
```bash
docker-compose logs heatpump-service
```

3. Verify gateway is reachable:
```bash
ping 192.168.2.10  # Your gateway IP
```

4. Check Modbus port (should be 8899 for Waveshare, or 502 for standard):
```bash
telnet 192.168.2.10 502
```

**Solutions:**
- Verify `MODBUS_HOST` and `MODBUS_PORT` in docker-compose.yml
- Check gateway is powered on and connected to network
- Ensure firewall allows outgoing connections on Modbus port
- Verify gateway IP hasn't changed (use static IP if possible)

---

### UI Shows "Disconnected"

**Symptoms:**
- Web UI displays "Disconnected" status
- Controls don't respond

**Checks:**

1. Check if API service is running:
```bash
curl http://localhost:8002/health
```

2. Check browser console for CORS errors (F12 → Console tab)

3. Verify API_URL in browser:
```javascript
// Should be: http://<raspberry-pi-ip>:8002
```

**Solutions:**
- Restart heatpump-service: `docker-compose restart heatpump-service`
- Check CORS configuration in `service/main.py`
- Verify port 8002 is accessible from browser's network

---

## Modbus Communication

### Timeout Errors

**Symptoms:**
- `asyncio.TimeoutError` in logs
- "No response received after 3 retries"

**Causes:**
- Shared RS-485 bus congestion (multiple devices)
- Gateway queue overflow
- Network latency

**Solutions:**

1. **Increase timeout** (already set to 30s in production):
```python
# lg_r290_modbus.py
TIMEOUT = 30  # seconds
```

2. **Reduce polling frequency** if bus is congested:
```yaml
# docker-compose.yml
POLL_INTERVAL=30  # Increase from 5 to 30 seconds
```

3. **Check gateway is accessible**:
```bash
ping 192.168.2.10
```

4. **Verify port**:
- Waveshare gateway: Port 8899
- Standard Modbus: Port 502

5. **Check device ID**:
- LG heat pump: Device ID 5 (or 7, check manual)
- WAGO meter: Device ID 2

---

### Wrong Device ID Responses

**Symptoms:**
```
ERROR: request ask for id=5 but got id=2, Skipping.
```

**Explanation:**
This is **normal behavior** on a shared RS-485 bus! PyModbus correctly filters out responses from other devices (e.g., WAGO energy meter with ID 2) when waiting for the LG heat pump (ID 5).

**No action needed** - this is expected and handled automatically by retry logic.

---

### Real Hardware Not Responding

**Checks:**

1. **Verify gateway configuration**:
   - IP address and port correct
   - Protocol: Modbus RTU → Modbus TCP
   - Baud rate: 9600
   - Parity: None
   - Data bits: 8
   - Stop bits: 1

2. **Check LG R290 DIP switches**:
   - SW1-1: ON (Enable Modbus)
   - SW1-2: ON (Enable Modbus)

3. **Verify RS-485 wiring**:
   - A+ to A+
   - B- to B-
   - Twisted pair cable recommended
   - Check termination resistors if bus is long

4. **Test with read-only script**:
```bash
python3 test_lg_registers.py
```

**Solutions:**
- Power cycle the heat pump
- Check RS-485 wiring continuity
- Verify device ID matches manual (usually 5 or 7)
- Emergency rollback: DIP switches to OFF disables Modbus

---

## Docker & Services

### Services Won't Start

**Checks:**

1. Check Docker status:
```bash
sudo systemctl status docker
```

2. View all logs:
```bash
docker-compose logs
```

3. Check for port conflicts:
```bash
sudo netstat -tlnp | grep -E "8080|8002|5020"
```

**Solutions:**

1. **Rebuild from scratch**:
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

2. **Change ports** if conflicting (in docker-compose.yml):
```yaml
ports:
  - "8081:80"  # Changed from 8080
  - "8003:8000"  # Changed from 8002
```

3. **Check disk space**:
```bash
df -h
```

---

### Container Keeps Restarting

**Symptoms:**
- Container status shows "Restarting"
- Logs show crash errors

**Checks:**

1. View container logs:
```bash
docker logs lg_r290_service --tail 100
```

2. Check for Python errors, missing dependencies, or configuration issues

**Solutions:**
- Fix configuration errors in `.env` or `docker-compose.yml`
- Rebuild container after code changes
- Check volume mounts are correct
- Verify all required environment variables are set

---

## Heat Pump Control

### Temperature Not Changing

**Symptoms:**
- Slider moves but flow temperature stays the same
- Target temperature set but not reached

**Checks:**

1. **Verify operating mode**:
```bash
curl http://localhost:8002/status | jq '.operating_mode, .target_temperature'
```

2. **Check if in correct mode**:
   - **Manual Heating mode (4)**: Register 40003 controls temperature
   - **LG Auto mode (3)**: Register 40005 offset adjusts curve (40003 ignored!)

3. **Heat pump must be ON**:
   - Compressor must run to heat water
   - Check power status and compressor status

4. **Monitor actual vs target**:
```bash
watch -n 2 'curl -s http://localhost:8002/status | jq .'
```

**Solutions:**
- Switch to Manual Heating mode if you want direct temperature control
- If using LG Auto mode, adjust offset instead of setpoint
- Ensure heat pump is powered ON
- Wait for compressor cycle (can take minutes to change temperature)

---

### Write Operations Failing

**Symptoms:**
- POST `/power` or `/setpoint` returns 500 error
- Changes don't apply to heat pump

**Checks:**

1. Check logs:
```bash
docker logs lg_r290_service | grep "error\|Error"
```

2. Common causes:
   - Modbus not connected
   - Heat pump not responding
   - Invalid register address
   - Value out of range (e.g., temperature < 20 or > 60)

3. **Verify with raw registers**:
```bash
curl http://localhost:8002/registers/raw | jq .
```

**Solutions:**
- Check Modbus connection first (`/health` endpoint)
- Verify temperature range: 20-60°C for setpoint, -5 to +5K for offset
- Check heat pump error code (register 30001)
- Restart service if Modbus connection lost

---

### Power Control Not Working

**Symptoms:**
- Power button clicks but heat pump doesn't turn ON/OFF
- CH03 error displayed on heat pump

**Explanation:**
CH03 = "External Control Mode Active" - **Not an error!**

When Modbus control is active, the heat pump:
- Locks out ThinQ app
- Locks out touchscreen
- Only responds to Modbus commands

This prevents conflicting commands from multiple sources.

**Solutions:**
- Continue controlling via Modbus/API
- To restore manual control: Turn off DIP switches (SW1-1 and SW1-2)
- Power button in UI should work - check logs for errors

---

## Scheduler Issues

### Schedule Not Triggering

**Symptoms:**
- Scheduled times pass but temperature doesn't change
- No scheduler logs

**Checks:**

1. Check scheduler status:
```bash
curl http://localhost:8002/schedule | jq .
```

2. Verify:
   - `enabled: true`
   - `current_time` matches expected timezone
   - `current_day` is correct

3. Check logs:
```bash
docker logs lg_r290_service | grep scheduler
```

Look for:
- `Schedule loaded: enabled=True`
- `Scheduler check:` messages (every 60 seconds)
- `Schedule match:` when trigger occurs

**Solutions:**
- Ensure `enabled: true` in `schedule.json`
- Reload config: `curl -X POST http://localhost:8002/schedule/reload`
- Check timezone (`TZ=Europe/Vienna` in docker-compose.yml)
- Verify container time: `docker exec lg_r290_service date`

---

### Schedule Triggers But Temperature Doesn't Change

**Symptoms:**
- Logs show "Schedule match" but no temperature change

**Check current thermostat mode:**
```bash
curl http://192.168.2.11:8001/api/v1/thermostat/status | jq .config.mode
```

**Explanation:**
If mode is `ECO` or `OFF`, scheduler **skips** (by design). The scheduler only applies when thermostat is in `AUTO` or `ON` mode.

**Look for this log:**
```
Schedule skipped: current mode is ECO (only AUTO/ON are affected)
```

**Solutions:**
- This is expected behavior - scheduler respects user's ECO/OFF choice
- Switch thermostat to AUTO mode if you want scheduling
- Scheduler acts as "resetter" not "forcer"

---

### Timezone Issues

**Symptoms:**
- Schedule triggers at wrong time
- Container time doesn't match local time

**Checks:**

1. Verify container timezone:
```bash
docker exec lg_r290_service date
```
Should show CEST/CET time, not UTC.

2. Check TZ environment variable:
```bash
docker exec lg_r290_service printenv TZ
```
Should output: `Europe/Vienna`

**Solutions:**
- Set `TZ=Europe/Vienna` in docker-compose.yml
- Restart service: `docker-compose restart heatpump-service`
- DST is handled automatically

---

## Network & API

### Thermostat API Unreachable from Container

**Symptoms:**
- LG Auto offset not applying based on thermostat mode
- Logs show connection errors to thermostat API

**Checks:**

1. Verify network exists:
```bash
docker network ls | grep shelly_bt_temp_default
docker network inspect shelly_bt_temp_default
```

2. Test connection from container:
```bash
docker exec lg_r290_service curl http://iot-api:8000/api/v1/thermostat/status
```

**Solutions:**
- Verify `shelly_bt_temp_default` network exists and is external in docker-compose.yml
- Start thermostat stack first: `cd ../shelly_bt_temp && docker-compose up -d`
- Use container name `iot-api` not host IP in `THERMOSTAT_API_URL`

**Fallback behavior:**
If thermostat API is unavailable, system uses default offset (0K) - no crash.

---

### Port Conflicts

**Symptoms:**
- "Address already in use" error
- Services won't start

**Check ports:**
```bash
sudo netstat -tlnp | grep -E "8080|8002|5020"
```

**Solutions:**

1. Stop conflicting service, or

2. Change ports in `docker-compose.yml`:
```yaml
ports:
  - "8081:80"  # Changed from 8080
  - "8003:8000"  # Changed from 8002
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

---

## Hardware Integration

### Waveshare Gateway Configuration

**Required Settings:**
- **IP Address**: Static (e.g., 192.168.2.10)
- **Protocol**: Modbus RTU → Modbus TCP
- **Baud Rate**: 9600
- **Parity**: None (N)
- **Data Bits**: 8
- **Stop Bits**: 1
- **TCP Port**: 502 or 8899 (check manual)

**Access gateway web interface:**
```
http://192.168.2.10
```

**Test connection:**
```bash
telnet 192.168.2.10 502
# Should connect without "Connection refused"
```

---

### LG R290 Not Responding

**Hardware Checklist:**

1. **DIP Switches** (inside unit):
   - SW1-1: ON
   - SW1-2: ON

2. **RS-485 Connection**:
   - Terminals 21 (A+) and 22 (B-)
   - Use shielded twisted pair cable
   - Connect A+ to A+, B- to B-

3. **Device ID**: Usually 5 or 7 (check manual)

4. **Power**: Heat pump powered on

**Testing:**

1. Read-only test:
```bash
python3 test_lg_registers.py
```

2. Check for errors:
```bash
curl http://localhost:8002/status | jq '.error_code, .has_error'
```

**Emergency Rollback:**
- Turn DIP switches OFF → Disables Modbus
- Heat pump returns to manual control
- No permanent changes

---

## Diagnostic Commands

### Quick Status Check

```bash
# All containers running?
docker-compose ps

# API healthy?
curl http://localhost:8002/health

# Current status
curl http://localhost:8002/status | jq .

# Scheduler status
curl http://localhost:8002/schedule | jq .

# Recent logs
docker-compose logs --tail=50
```

### Deep Dive

```bash
# All logs since startup
docker-compose logs

# Follow logs in real-time
docker-compose logs -f heatpump-service

# Search for errors
docker logs lg_r290_service | grep -i error

# Raw Modbus registers
curl http://localhost:8002/registers/raw | jq .

# Container resource usage
docker stats
```

### Network Diagnostics

```bash
# Container networks
docker network ls

# Inspect network
docker network inspect shelly_bt_temp_default

# Test DNS resolution
docker exec lg_r290_service ping iot-api

# Test API access
docker exec lg_r290_service curl http://iot-api:8000/api/v1/thermostat/status
```

---

## Getting Help

If you've tried the above solutions and still have issues:

1. **Gather diagnostics**:
```bash
# Save all logs
docker-compose logs > debug_logs.txt

# Save status
curl http://localhost:8002/status > status.json
curl http://localhost:8002/registers/raw > registers.json

# Save configuration
cat docker-compose.yml > config.txt
cat .env >> config.txt
```

2. **Check documentation**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
   - [MODBUS.md](../MODBUS.md) - Register reference
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Setup guide
   - [MODBUS_JOURNEY.md](../MODBUS_JOURNEY.md) - Implementation story

3. **Review related documentation**:
   - [Heat Pump Control](HEAT_PUMP_CONTROL.md)
   - [Scheduler](SCHEDULER.md)
   - [Thermostat Integration](THERMOSTAT_INTEGRATION.md)

---

## Known Issues

### Mock Server Register Offset
The mock server has a register addressing offset that can cause some values to read as zero. This is a known issue with the mock server only - real hardware works correctly.

### Coil/Discrete Registers May Timeout
Reading coil and discrete input registers may timeout on some heat pump models. Input and holding registers work reliably. If you encounter this, focus on input/holding registers only.

### Shared Bus Occasional Timeouts
When multiple devices share the RS-485 bus (e.g., WAGO meter + LG heat pump), occasional timeouts are normal (<6% error rate). The retry logic recovers automatically - no action needed.
