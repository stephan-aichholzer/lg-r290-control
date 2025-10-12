# Hardware Integration Plan

**Critical Phase: Transitioning from Mock to Real LG R290 Heat Pump**

⚠️ **WARNING**: This document outlines a careful, staged approach to connecting to real hardware. Follow each phase sequentially and do not skip safety measures.

---

## 🎯 Staged Hardware Integration Strategy

### Overview

The goal is to replace the mock Modbus server with a real connection to the LG R290 heat pump in a safe, controlled manner. We'll use a phased approach with multiple safety checkpoints.

### Key Principles

1. **Read before Write**: Verify READ operations work perfectly before attempting any writes
2. **Isolation**: Test hardware separately from production mock setup
3. **Observation Period**: Monitor stability for 24-48 hours before proceeding
4. **Rollback Plan**: Always have a way to revert to safe state
5. **Documentation**: Record all observations and current states

---

## 📋 Phase-by-Phase Implementation

### **Phase 1: Isolated Read-Only Test (1-2 hours)**

**Goal**: Verify basic Modbus TCP connectivity and READ operations without Docker complexity.

#### Step 1.1: Create Standalone Test Script

Create `test_hardware_connection.py` in the repository root:

```python
#!/usr/bin/env python3
"""
Safe hardware connection test - READ ONLY
Tests Modbus TCP connection to real LG R290 heat pump
NO WRITES - READ OPERATIONS ONLY
"""
import asyncio
from pymodbus.client import AsyncModbusTcpClient

async def test_connection(host: str, port: int = 502, unit_id: int = 1):
    """
    Test connection to heat pump and read all register types.

    Args:
        host: Heat pump IP address
        port: Modbus TCP port (default 502)
        unit_id: Modbus unit/slave ID (default 1)
    """
    print("=" * 60)
    print("LG R290 Heat Pump - Hardware Connection Test")
    print("READ ONLY - NO WRITES")
    print("=" * 60)
    print(f"\nTarget: {host}:{port} (Unit ID: {unit_id})")

    client = AsyncModbusTcpClient(host=host, port=port, timeout=10)

    try:
        # Step 1: Connect
        print("\n[1/4] Testing connection...")
        connected = await client.connect()
        if not connected:
            print("❌ FAILED: Could not connect to heat pump")
            print("\nPossible issues:")
            print("  - Heat pump IP address incorrect")
            print("  - Modbus TCP not enabled on heat pump")
            print("  - Network connectivity issue")
            print("  - Firewall blocking port 502")
            return False

        print("✅ SUCCESS: Connected to heat pump")

        # Step 2: Read Coils (Digital outputs - power status)
        print("\n[2/4] Testing COIL reads (Digital Outputs)...")
        print("    Reading coil 0 (Power ON/OFF)...")
        result = await client.read_coils(0, 1, slave=unit_id)
        if result.isError():
            print(f"❌ FAILED: Coil read error: {result}")
            print("    This may indicate wrong unit ID or register not supported")
        else:
            power_state = result.bits[0]
            print(f"✅ SUCCESS: Coil 0 (Power): {'ON' if power_state else 'OFF'}")

        # Step 3: Read Input Registers (Sensor readings)
        print("\n[3/4] Testing INPUT REGISTER reads (Sensor Data)...")
        print("    Reading registers 0-13 (temperatures, pressures, etc.)...")
        result = await client.read_input_registers(0, 14, slave=unit_id)
        if result.isError():
            print(f"❌ FAILED: Input register read error: {result}")
        else:
            regs = result.registers
            print(f"✅ SUCCESS: Read {len(regs)} input registers")
            print("\n    Decoded Values:")
            print(f"      Error Code (30001):        {regs[0]}")
            print(f"      Operating Mode (30002):    {regs[1]} (0=Standby, 1=Cooling, 2=Heating)")
            print(f"      Return Temp (30003):       {regs[2]/10.0}°C")
            print(f"      Flow Temp (30004):         {regs[3]/10.0}°C")
            print(f"      Flow Rate (30009):         {regs[8]/10.0} LPM")
            print(f"      Outdoor Temp (30013):      {regs[12]/10.0}°C")
            print(f"      Water Pressure (30014):    {regs[13]/10.0} bar")

        # Step 4: Read Holding Registers (Configuration - target temps)
        print("\n[4/4] Testing HOLDING REGISTER reads (Configuration)...")
        print("    Reading registers 0-2 (operating mode, target temp)...")
        result = await client.read_holding_registers(0, 3, slave=unit_id)
        if result.isError():
            print(f"❌ FAILED: Holding register read error: {result}")
        else:
            holding_regs = result.registers
            print(f"✅ SUCCESS: Read {len(holding_regs)} holding registers")
            print("\n    Decoded Values:")
            print(f"      Operating Mode (40001):    {holding_regs[0]}")
            print(f"      Control Method (40002):    {holding_regs[1]}")
            print(f"      Target Temp (40003):       {holding_regs[2]/10.0}°C")

        # Summary
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nNext Steps:")
        print("  1. Review all values - do they make sense?")
        print("  2. Compare with heat pump display")
        print("  3. Run test multiple times to verify stability")
        print("  4. If stable, proceed to Phase 2 (Docker Integration)")

        await client.close()
        return True

    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        print("\nTroubleshooting:")
        print("  - Check heat pump is powered on")
        print("  - Verify Modbus TCP is enabled in heat pump settings")
        print("  - Confirm network connectivity: ping <IP>")
        print("  - Check firewall settings")
        if client:
            await client.close()
        return False

async def main():
    """Main test runner"""
    print("\nConfiguration:")
    print("-" * 60)

    # TODO: REPLACE WITH YOUR HEAT PUMP IP ADDRESS
    HEATPUMP_IP = "192.168.x.x"  # <-- CHANGE THIS
    MODBUS_PORT = 502
    UNIT_ID = 1

    print(f"Heat Pump IP:  {HEATPUMP_IP}")
    print(f"Modbus Port:   {MODBUS_PORT}")
    print(f"Unit ID:       {UNIT_ID}")
    print("-" * 60)

    if HEATPUMP_IP == "192.168.x.x":
        print("\n⚠️  WARNING: Please update HEATPUMP_IP with your actual heat pump IP address")
        print("Edit this script and change the HEATPUMP_IP variable.")
        return

    input("\nPress ENTER to start test (Ctrl+C to cancel)...")

    success = await test_connection(HEATPUMP_IP, MODBUS_PORT, UNIT_ID)

    if success:
        print("\n✅ Hardware connection verified!")
        print("You may proceed to Phase 2 when ready.")
    else:
        print("\n❌ Hardware connection failed.")
        print("Review errors above and resolve issues before proceeding.")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Step 1.2: Run Test

```bash
# Make executable
chmod +x test_hardware_connection.py

# Install dependencies if needed
pip install pymodbus

# Run test
python test_hardware_connection.py
```

#### Step 1.3: Validation Checklist

- [ ] Script connects successfully
- [ ] All register types can be read (coils, inputs, holdings)
- [ ] Values match heat pump display
- [ ] Run test 5-10 times - all succeed
- [ ] No errors or timeouts

**✅ Phase 1 Success Criteria**: All reads work consistently, values are sensible.

**❌ If Phase 1 Fails**: DO NOT PROCEED. Resolve connection issues first.

---

### **Phase 2: Read-Only Docker Service (24 hours)**

**Goal**: Run hardware monitoring service in parallel with mock, observe stability.

#### Step 2.1: Create Hardware Test Docker Compose

Create `docker-compose.hardware-test.yml`:

```yaml
version: '3.8'

services:
  hardware-monitor:
    build:
      context: ./service
      dockerfile: Dockerfile
    container_name: lg_hardware_monitor
    ports:
      - "8003:8000"  # Different port from mock (8002)
    environment:
      - MODBUS_HOST=${HEATPUMP_IP}  # Set via .env or command line
      - MODBUS_PORT=502
      - MODBUS_UNIT_ID=1
      - POLL_INTERVAL=10  # Poll every 10 seconds
      - READ_ONLY_MODE=true  # CRITICAL: Disable all writes
      - THERMOSTAT_API_URL=http://iot-api:8000
      - TZ=Europe/Vienna
    networks:
      - heatpump-net
      - shelly_bt_temp_default
    restart: "no"  # Manual restart only during testing

networks:
  heatpump-net:
    driver: bridge
  shelly_bt_temp_default:
    external: true
```

#### Step 2.2: Add Read-Only Mode to Service

Modify `service/main.py` to add read-only protection:

```python
# At top of file
READ_ONLY_MODE = os.getenv("READ_ONLY_MODE", "false").lower() == "true"

# In set_power endpoint
@app.post("/power")
async def set_power(control: PowerControl):
    if READ_ONLY_MODE:
        raise HTTPException(
            status_code=403,
            detail="Read-only mode: Write operations disabled for safety"
        )
    # ... rest of code

# In set_temperature_setpoint endpoint
@app.post("/setpoint")
async def set_temperature_setpoint(setpoint: TemperatureSetpoint):
    if READ_ONLY_MODE:
        raise HTTPException(
            status_code=403,
            detail="Read-only mode: Write operations disabled for safety"
        )
    # ... rest of code
```

#### Step 2.3: Start Hardware Monitor

```bash
# Export your heat pump IP
export HEATPUMP_IP=192.168.x.x

# Start hardware monitor (port 8003)
docker-compose -f docker-compose.hardware-test.yml up -d

# Keep mock running (port 8002)
docker-compose ps  # Verify both running

# Watch logs
docker logs -f lg_hardware_monitor
```

#### Step 2.4: Monitoring Commands

```bash
# Terminal 1: Hardware monitor logs
docker logs -f lg_hardware_monitor

# Terminal 2: Compare mock vs hardware
watch -n 5 'echo "=== MOCK (8002) ===" && curl -s http://localhost:8002/status | jq ".flow_temperature, .target_temperature, .outdoor_temperature" && echo "\n=== HARDWARE (8003) ===" && curl -s http://localhost:8003/status | jq ".flow_temperature, .target_temperature, .outdoor_temperature"'

# Terminal 3: Check for errors
docker logs lg_hardware_monitor 2>&1 | grep -i error
```

#### Step 2.5: 24-Hour Observation

**What to monitor:**
- Connection stability (no disconnections)
- Values update regularly (every 10 seconds)
- Values are realistic and change appropriately
- No error messages in logs
- CPU/memory usage is normal

**Record observations in a log:**
```bash
# Create observation log
cat > hardware_observation.log <<EOF
Hardware Monitoring Log
Start: $(date)
Heat Pump IP: $HEATPUMP_IP

Hour 0: Initial startup
- Connection: OK
- Flow temp: XX°C
- Target temp: XX°C
- Outdoor temp: XX°C
- Notes: ...

Hour 6: Morning check
- Connection: ...
- Notes: ...

Hour 12: Midday check
...

Hour 24: Final check
...
EOF
```

#### Step 2.6: Validation Checklist

After 24 hours:
- [ ] No connection drops or timeouts
- [ ] Values update consistently
- [ ] Data makes sense (temps realistic, changes reasonable)
- [ ] No errors in logs
- [ ] Compare with mock - behavior similar
- [ ] Heat pump operates normally (not affected by monitoring)

**✅ Phase 2 Success Criteria**: 24 hours of stable READ operations.

**❌ If Phase 2 Fails**: Stop hardware monitor, analyze logs, resolve issues.

---

### **Phase 3: Controlled Write Test (30 minutes)**

**Goal**: Test ONE write operation in controlled manner.

⚠️ **CRITICAL**: This phase will MODIFY heat pump settings. Proceed with caution.

#### Step 3.1: Document Current State

```bash
# Before any writes, document everything
echo "Current Heat Pump State - $(date)" > pre_write_state.txt
curl -s http://localhost:8003/status | jq '.' >> pre_write_state.txt

# Take photo of heat pump display
# Note: Power state, mode, target temp, actual temps
```

#### Step 3.2: Disable Read-Only Mode

```bash
# Stop hardware monitor
docker-compose -f docker-compose.hardware-test.yml down

# Edit docker-compose.hardware-test.yml
# Change: READ_ONLY_MODE=false

# Restart
docker-compose -f docker-compose.hardware-test.yml up -d
```

#### Step 3.3: Test Single Write

**Test: Increase target temperature by 1°C**

```bash
# Get current target temp
CURRENT_TEMP=$(curl -s http://localhost:8003/status | jq -r '.target_temperature')
echo "Current target: ${CURRENT_TEMP}°C"

# Calculate new temp (+1°C)
NEW_TEMP=$(echo "$CURRENT_TEMP + 1" | bc)
echo "New target: ${NEW_TEMP}°C"

# CRITICAL: Confirm before proceeding
read -p "Press ENTER to write new target temp to REAL HARDWARE (Ctrl+C to cancel): "

# Write new temperature
curl -X POST http://localhost:8003/setpoint \
  -H "Content-Type: application/json" \
  -d "{\"temperature\": $NEW_TEMP}"

# Observe logs immediately
docker logs -f lg_hardware_monitor
```

#### Step 3.4: Verify Write Success

```bash
# Wait 10 seconds for polling
sleep 10

# Read back value
curl -s http://localhost:8003/status | jq '.target_temperature'

# Check heat pump display - does it match?

# Wait 5 minutes - observe heat pump behavior
# Does it respond appropriately to new setpoint?
```

#### Step 3.5: 30-Minute Observation

**Monitor:**
- Heat pump responds to new setpoint
- Flow temperature adjusts if needed
- Compressor behavior normal
- No error codes
- System remains stable

#### Step 3.6: Validation Checklist

- [ ] Write operation succeeded
- [ ] Value can be read back correctly
- [ ] Heat pump display shows new value
- [ ] Heat pump responds appropriately
- [ ] No errors or alarms triggered
- [ ] System stable after 30 minutes

**✅ Phase 3 Success Criteria**: Single write works, heat pump responds correctly.

**❌ If Phase 3 Fails**:
1. Stop hardware service immediately
2. Reset heat pump to safe values manually
3. Analyze what went wrong
4. Do NOT proceed to Phase 4

---

### **Phase 4: Full Integration (48 hours)**

**Goal**: Switch UI to hardware, enable all features, monitor stability.

⚠️ **NOTE**: Only proceed if ALL previous phases succeeded.

#### Step 4.1: Enable All Features

```bash
# Stop hardware test service
docker-compose -f docker-compose.hardware-test.yml down

# Update main docker-compose.yml
# Change MODBUS_HOST from "heatpump-mock" to your heat pump IP
# Or use environment variable override
```

#### Step 4.2: Create Backup Configuration

```bash
# Backup current working config
cp docker-compose.yml docker-compose.yml.mock-backup
cp .env .env.backup

# Create hardware config
cat > .env.hardware <<EOF
MODBUS_HOST=192.168.x.x  # Your heat pump IP
MODBUS_PORT=502
MODBUS_UNIT_ID=1
POLL_INTERVAL=5
THERMOSTAT_API_URL=http://iot-api:8000
TZ=Europe/Vienna
EOF
```

#### Step 4.3: Switch to Hardware

```bash
# Use hardware config
cp .env.hardware .env

# Stop mock stack
docker-compose down

# Start with hardware
docker-compose up -d

# Verify
docker-compose ps
docker logs -f lg_r290_service
```

#### Step 4.4: Test All Features

**Systematic feature testing:**

1. **Power Control**
   ```bash
   # Turn OFF
   curl -X POST http://localhost:8002/power -d '{"power_on": false}'
   # Wait 30 seconds, observe

   # Turn ON
   curl -X POST http://localhost:8002/power -d '{"power_on": true}'
   # Wait 30 seconds, observe
   ```

2. **Temperature Control**
   ```bash
   # Set target temp
   curl -X POST http://localhost:8002/setpoint -d '{"temperature": 40.0}'
   # Observe for 5 minutes
   ```

3. **AI Mode** (if comfortable)
   ```bash
   # Enable AI Mode
   curl -X POST http://localhost:8002/ai-mode -d '{"enabled": true}'
   # Monitor for 1 hour

   # Disable if issues
   curl -X POST http://localhost:8002/ai-mode -d '{"enabled": false}'
   ```

4. **Scheduler** (if comfortable)
   ```bash
   # Check scheduler status
   curl http://localhost:8002/schedule

   # May want to disable initially
   # Set ENABLE_SCHEDULER=false in docker-compose.yml
   ```

#### Step 4.5: 48-Hour Production Monitoring

**Monitoring plan:**
```bash
# Create monitoring cron job
crontab -e

# Add: Check every hour
0 * * * * /home/stephan/projects/lg_r290_control/system_status.sh >> /var/log/heatpump_monitor.log 2>&1

# Manual checks every 6 hours
./system_status.sh
./monitor_ai_mode.sh
docker logs lg_r290_service --tail 50
```

**What to monitor:**
- Heat pump responds correctly to all commands
- AI Mode adjusts temperatures appropriately
- Scheduler triggers at expected times
- No disconnections or errors
- Performance is acceptable
- Energy usage is reasonable

#### Step 4.6: Final Validation Checklist

After 48 hours:
- [ ] All features work correctly
- [ ] No unexpected behavior
- [ ] System is stable
- [ ] Heat pump operates efficiently
- [ ] No manual interventions needed
- [ ] UI responsive and accurate
- [ ] Comfortable leaving system running autonomously

**✅ Phase 4 Success Criteria**: Full production use for 48 hours without issues.

---

## 🚨 Emergency Procedures

### Immediate Rollback to Mock

```bash
# Stop hardware service
docker-compose down

# Restore mock configuration
cp docker-compose.yml.mock-backup docker-compose.yml
cp .env.backup .env

# Start mock
docker-compose up -d

# Verify
curl http://localhost:8002/status
```

### Heat Pump Manual Override

If heat pump is in undesired state:
1. Use physical controls on heat pump to reset
2. Disconnect Modbus TCP (network cable or heat pump settings)
3. Document what happened
4. Analyze logs before reconnecting

### Critical Failure Response

1. **Stop all services immediately**
   ```bash
   docker-compose down
   docker-compose -f docker-compose.hardware-test.yml down
   ```

2. **Reset heat pump manually** using physical controls

3. **Document the failure**
   - What operation was being performed?
   - What values were written?
   - Heat pump response?
   - Error messages?

4. **Analyze before retry**
   - Review logs
   - Check Modbus register mapping
   - Verify values are in valid ranges
   - Consult heat pump manual

---

## ✅ Pre-Flight Checklist

Before starting Phase 1:

### Information Gathering
- [ ] Heat pump IP address known: ___________________
- [ ] Heat pump manual available (Modbus section)
- [ ] Current heat pump settings documented (photos taken)
- [ ] Modbus TCP confirmed enabled on heat pump
- [ ] Network connectivity verified (ping works)
- [ ] Port 502 accessible (firewall rules checked)
- [ ] Unit ID confirmed (usually 1)

### Safety Preparations
- [ ] Mock server tested and working as backup
- [ ] Backup configurations created
- [ ] Monitoring scripts ready
- [ ] Emergency rollback procedure understood
- [ ] Know how to use heat pump manual controls
- [ ] Time allocated for careful testing (not rushed)

### Technical Readiness
- [ ] Repository backed up (git push)
- [ ] Test script created (`test_hardware_connection.py`)
- [ ] Read-only mode implemented in code
- [ ] Docker Compose files prepared
- [ ] Observation logs prepared
- [ ] Monitoring commands tested

---

## 📝 Register Reference

Quick reference for LG R290 Modbus registers:

### Coils (Read/Write)
- **0 (00001)**: Power ON/OFF

### Discrete Inputs (Read-Only)
- **1 (10002)**: Water pump status
- **3 (10004)**: Compressor status
- **13 (10014)**: Error flag

### Input Registers (Read-Only)
- **0 (30001)**: Error code
- **1 (30002)**: Operating mode (0=Standby, 1=Cooling, 2=Heating)
- **2 (30003)**: Return temperature (×0.1°C)
- **3 (30004)**: Flow temperature (×0.1°C)
- **8 (30009)**: Flow rate (×0.1 LPM)
- **12 (30013)**: Outdoor temperature (×0.1°C)
- **13 (30014)**: Water pressure (×0.1 bar)

### Holding Registers (Read/Write)
- **0 (40001)**: Operating mode setting
- **2 (40003)**: Target temperature (×0.1°C)

**Valid ranges (verify with manual):**
- Target temperature: 20.0°C - 60.0°C
- Never write values outside valid ranges!

---

## 📊 Decision Tree

```
Start
  │
  ├─ Phase 1: Test Script
  │    │
  │    ├─ Success? → Continue to Phase 2
  │    └─ Fail? → Debug connection, do not proceed
  │
  ├─ Phase 2: Read-Only Docker (24h)
  │    │
  │    ├─ Stable? → Continue to Phase 3
  │    └─ Unstable? → Fix issues, restart Phase 2
  │
  ├─ Phase 3: Single Write Test (30min)
  │    │
  │    ├─ Works correctly? → Continue to Phase 4
  │    └─ Issues? → Rollback, analyze, do not proceed
  │
  └─ Phase 4: Full Integration (48h)
       │
       ├─ Stable? → SUCCESS! Switch to production
       └─ Issues? → Rollback to mock, refine approach
```

---

## 📞 Support Resources

- **LG R290 Manual**: Check Modbus TCP configuration section
- **Repository Issues**: Document any problems found
- **Docker Logs**: `docker logs lg_r290_service` or `lg_hardware_monitor`
- **System Status**: `./system_status.sh`
- **Heat Pump Display**: Physical verification of all settings

---

## 🎯 Recommended Approach Summary

**My strongest recommendation:**

1. **Start with Phase 1** - Standalone test script (lowest risk)
2. **Run multiple times** - Verify consistency before proceeding
3. **Phase 2 in parallel** - Keep mock running, test hardware separately
4. **Take your time** - Don't rush through observation periods
5. **Document everything** - You'll thank yourself later
6. **Have rollback ready** - Test emergency procedures before you need them

**Timeline estimate:**
- Phase 1: 1-2 hours
- Phase 2: 24 hours (monitoring)
- Phase 3: 30 minutes (testing) + analysis
- Phase 4: 48 hours (monitoring)
- **Total: ~4 days** for safe, careful integration

**Don't skip phases!** Each builds confidence for the next.

---

## 📋 Questions to Answer Before Starting

1. **Heat pump IP address?** ___________________
2. **Is Modbus TCP already enabled?** ___________________
3. **Do you have the manual?** ___________________
4. **Backup plan if things go wrong?** ___________________
5. **Time available for testing?** ___________________
6. **Comfortable with manual heat pump controls?** ___________________

---

**Document created**: 2025-10-12
**For project**: LG R290 Heat Pump Control System
**Critical phase**: Mock → Hardware transition

**Status**: Planning stage - NOT YET EXECUTED
**Next step**: Review this plan, answer questions above, prepare for Phase 1
