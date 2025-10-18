# The LG Therma V R290 Modbus Journey
## *A Tale of Registers, Retries, and Relentless Polling*

---

## TL;DR

**Goal:** Control an LG Therma V R290 heat pump via Modbus instead of the proprietary ThinQ app.

**Outcome:** SUCCESS! Complete external control achieved.

**The Twist:** The heat pump has a secret requirement that's not in any manual... 🤦

---

## Chapter 1: The Optimistic Beginning

*"How hard could it be? It's just Modbus!"*

We had:
- ✅ LG Therma V R290 7kW heat pump (HN1639HC NK0)
- ✅ Official Modbus documentation (well, sort of...)
- ✅ Waveshare RS485-to-Ethernet gateway
- ✅ A dream of open-source heat pump control

The documentation showed registers for:
- Coil 00001: Power ON/OFF
- Register 40001: Operating Mode (Heating/Cooling)
- Register 40003: Target Temperature
- Register 40010: Energy State (mysterious...)

*"Let's just set these and we're done!"*

Narrator: They were not done.

---

## Chapter 2: The CH03 Mystery

First attempt at Modbus communication:

```
> Turn ON heat pump via Modbus
✅ Success! Heat pump turned on!

> Check touchscreen
⚠️  CH03 error displayed
🔒 Touchscreen locked out
🔒 ThinQ app locked out
```

**Panic mode engaged.** 💀

*"Did we brick a €3000 heat pump?!"*

Hours of research later: CH03 = "External Control Mode Active"

**Not an error!** It's a feature. The heat pump locks out manual control when external Modbus control is detected to prevent conflicting commands. You must choose: ThinQ OR Modbus. Not both.

**Lesson 1:** What looks like an error code might be an informational status. RTFM carefully.

---

## Chapter 3: The RMC Red Herring

Heat pump has an RMC (Remote Controller) setting buried in the touchscreen menu:
- MASTER mode: RMC controls heat pump
- SLAVE mode: Heat pump follows another RMC

*"Maybe this affects Modbus control?"*

Changed RMC setting to different values.
Sent Modbus commands.
Heat pump turned on!

**Victory!** 🎉

...for about 30 seconds. Then it shut down. 😐

**Plot twist discovered later:** The RMC setting has NOTHING to do with Modbus control! It's only relevant when you have multiple RMC controllers in one installation. We changed it during debugging and assumed it mattered - classic debugging correlation error!

---

## Chapter 4: The Register Rabbit Hole

*"Maybe we need to set ALL the registers?"*

Deep dive into every register:
- ✅ 40001 = 4 (Heating mode)
- ✅ 40002 = 0 (Water outlet control)
- ✅ 40003 = 400 (40.0°C target)
- ❓ 40010 = ? (Energy State... what does this do?)

Tried different values:
- 40010 = 0 (Not used) → Heat pump shuts down after 30 seconds
- 40010 = 2 (Normal) → Heat pump shuts down after 30 seconds
- 40010 = 4 (ON-Command) → Heat pump shuts down after 30 seconds
- 40010 = 5 (ON-Command Step2) → Heat pump runs for... 60 seconds! Then shuts down.

**Progress!** But still not working properly.

**Lesson 2:** When documentation says "Energy State Input for external energy management", it's not just a suggestion.

---

## Chapter 5: The Shared Bus Adventure

Our RS-485 bus has two devices:
- Device ID 2: WAGO energy meter (polling every 30 seconds)
- Device ID 7: LG Therma V

*"Will they interfere with each other?"*

Implemented retry logic:
- 3 attempts per operation
- Exponential backoff (2s, 4s, 6s)
- 30-second timeouts

Added error handling for:
- `ModbusException` - Protocol errors
- `asyncio.TimeoutError` - Network timeouts
- `ConnectionError` - TCP disconnects
- Generic `Exception` - Everything else

**Bus collision concerns:** Handled! The retry logic gracefully manages any interference.

**Lesson 3:** Shared RS-485 buses work fine with proper retry logic and backoff delays.

---

## Chapter 6: The Aha Moment

*"Wait... what if the heat pump NEEDS continuous communication?"*

**The Hypothesis:** Maybe the heat pump interprets silence as "external controller crashed" and shuts down as a safety feature?

**The Test:** Keep reading status registers every 10 seconds.

```python
while True:
    status = read_heat_pump_status()
    await asyncio.sleep(10)
```

Result: **HEAT PUMP STAYS ON!** 🎉🎉🎉

**The Secret:** The LG Therma V R290 requires continuous Modbus polling (every 5-10 seconds) to maintain external control mode. If polling stops, it assumes the external controller has failed and shuts down for safety.

**THIS IS NOT DOCUMENTED ANYWHERE.** 📖❌

We discovered this through trial and error after:
- Reading all registers
- Comparing working vs non-working states
- Testing different Energy State values
- Trying various initialization sequences
- Finally: "What if we just keep talking to it?"

**Lesson 4:** Safety-critical systems may require heartbeat/keepalive signals. The LG engineers designed it this way on purpose!

---

## Chapter 7: The Connection Stability Saga

After ~8 minutes of successful polling:

```
[475s] Mode: Heating | Flow: 31.6°C ...
❌ list index out of range
❌ unpack requires a buffer of 2 bytes
❌ Connection lost during request
💀 TCP connection died
```

*"NOOOOO! We were so close!"*

**The Problem:** Corrupted Modbus responses from bus collisions or gateway hiccups.

**The Solution:** Enhanced error handling:

```python
except (IndexError, struct.error, ValueError) as e:
    # Corrupted response - retry
    retry_with_backoff()

except (ConnectionError, OSError, asyncio.TimeoutError) as e:
    # Connection lost - reconnect
    reconnect_gateway()

# Verify register count matches expected
if len(result.registers) != expected_count:
    # Partial response - retry
    retry_with_backoff()
```

Consecutive failure tracking:
- Allow up to 5 consecutive failures
- Reset counter on successful read
- Automatic reconnection with 2-second delay

**Result:** 15+ minutes of flawless operation! Zero errors!

**Lesson 5:** Defense-in-depth error handling is essential for industrial protocols. Expect the unexpected.

---

## Chapter 8: The Final Architecture

### Production Scripts (3 essential tools)

**1. `keep_alive.py` - The Heart**
- Continuous polling daemon
- Sets Energy State = 5 (ON-Command Step2)
- Polls every 10 seconds
- Auto-reconnect on failures
- Comprehensive error handling

```bash
python3 keep_alive.py
# Runs forever, keeps heat pump alive
```

**2. `fallback_control.py` - The Brain**
- Command-line control tool
- Commands: status, on, off, temp, set
- Retry logic and error recovery

```bash
python3 fallback_control.py set 40 on  # Set to 40°C and turn ON
python3 fallback_control.py temp 42    # Adjust temperature
python3 fallback_control.py off        # Turn OFF
```

**3. `dump_all_registers.py` - The Debugger**
- Diagnostic tool
- Reads ALL registers for analysis
- Reference for troubleshooting

```bash
python3 dump_all_registers.py > state.txt
# Capture complete heat pump state
```

---

## The Proven Facts

After extensive testing, these are **confirmed truths**:

### ✅ Fact 1: Continuous Polling is REQUIRED (The Real Secret!)
- Must poll status every 5-30 seconds
- Heat pump interprets silence as controller failure
- Safety feature: prevents runaway heating if controller crashes
- **This is THE critical requirement - everything else is secondary!**

### ✅ Fact 2: Polling Stops = Heat Pump Stops
- Tested and confirmed multiple times
- Shutdown occurs within ~60 seconds of last communication
- Not a bug, it's a feature!

### ❌ Myth: Energy State Register (40010) is Critical
**Previously thought:** Register 40010 must be set to 5 for external control
**Actually discovered:** It works fine with 0 (Not used) as long as you poll!
- The polling is what matters, not the Energy State value
- Setting it to 5 during early testing coincided with starting continuous polling
- Classic correlation vs causation confusion
- **Lesson:** The simplest explanation is often correct

### ✅ Fact 3: CH03 is Informational, Not an Error
- "External Control Mode Active"
- Locks out ThinQ and touchscreen to prevent conflicts
- Normal and expected behavior

### ✅ Fact 4: Shared RS-485 Bus Works Fine
- WAGO meter (30s polling) + LG Therma V (30s polling)
- No interference with proper retry logic
- 3 retries with exponential backoff handles collisions
- <6% error rate, all recovered automatically

### ❌ Myth: RMC Must Be in SLAVE Mode
**Previously thought:** RMC setting must be SLAVE for Modbus control
**Actually discovered:** RMC setting doesn't matter for Modbus!
- MASTER vs SLAVE only relevant if you have 2 RMC controllers in one house
- Modbus works fine regardless of RMC setting
- Another red herring from the debugging process
- We changed it during testing and assumed it mattered - it didn't!

---

## The Journey in Numbers

### Phase 1: Initial Discovery (October 2024)
- **Days of debugging:** ~3-4
- **Test scripts written:** 12+ (consolidated to 3)
- **Register combinations tried:** 50+
- **"This should work!" moments:** 237
- **Times we thought we broke it:** 8
- **Coffee consumed:** Classified ☕

### Phase 2: Production System (October 2024)
- **Docker containers:** 3 (service, UI, mock)
- **REST API endpoints:** 15+
- **UML diagrams created:** 11
- **Documentation pages:** 10+
- **Lines of Python code:** ~3,500
- **Prometheus metrics exported:** 10
- **Docker networks joined:** 3
- **Uptime achieved:** Days without restart! ✨

### Overall Stats
- **Total time invested:** ~2 weeks
- **Registers fully documented:** 20+
- **Features implemented:** Read-only mode, Scheduler, AI Mode, Prometheus, LG Auto mode offset
- **Bugs fixed:** Too many to count
- **Satisfaction level:** 💯💯💯

---

## Key Lessons Learned

### 1. **RTFM, But Know When It's Incomplete**
The official Modbus documentation is necessary but not sufficient. Critical details (continuous polling requirement) are not documented.

### 2. **Safety Features May Look Like Bugs**
The shutdown behavior felt like a bug but is actually an intelligent safety feature. If the external controller crashes, the heat pump should not continue running uncontrolled.

### 3. **Industrial Protocols Need Robust Error Handling**
- Retry logic with exponential backoff
- Multiple exception types caught
- Response validation
- Automatic reconnection
- Consecutive failure tracking

### 4. **Shared Bus Communication Works**
Multiple devices on RS-485 bus work fine with proper retry logic. Don't be afraid of bus collisions - just handle them gracefully.

### 5. **Test, Document, Test Again**
What you *think* works after 2 minutes might fail after 8 minutes. Extended testing reveals edge cases.

### 6. **Keep It Simple**
Started with complex initialization sequences, registry dumps, and elaborate state machines. Final solution: "Just keep talking to it every 10 seconds."

---

## For Anyone Attempting This

### Minimum Requirements

**Hardware:**
- LG Therma V R290 heat pump (should work with other LG Therma V models)
- RS-485 to Ethernet/TCP gateway (Waveshare or similar)
- Proper RS-485 wiring (A to A, B to B, twisted pair)

**Configuration:**
- Device ID: 7 (or whatever your manual specifies)
- Modbus TCP → RTU gateway at 9600 baud, 8N1
- RMC setting: Doesn't matter! (MASTER or SLAVE, either works)

**Software:**
- Python 3.7+
- pymodbus library (v3.x)
- Continuous polling daemon

### Critical Settings (Simplified!)

```python
# Optional registers to set (not strictly required):
HOLDING_OP_MODE = 0         # Register 40001 = 4 (Heating) or 3 (Auto)
HOLDING_CONTROL_METHOD = 1  # Register 40002 = 0 (Water outlet)
HOLDING_TARGET_TEMP = 2     # Register 40003 = temp * 10

# THE ONLY CRITICAL REQUIREMENT:
POLL_INTERVAL = 10-30  # seconds - MUST poll continuously!

# What's NOT needed (despite earlier assumptions):
# HOLDING_ENERGY_STATE = 9  # Works fine at 0 (default)
# RMC SLAVE mode            # Doesn't affect Modbus at all
```

### Testing Procedure

1. **Start with read-only tests**
   ```bash
   python3 dump_all_registers.py
   ```

2. **Test power control**
   ```bash
   python3 fallback_control.py on
   ```

3. **Start keep-alive immediately**
   ```bash
   python3 keep_alive.py
   ```

4. **Monitor for 15+ minutes**
   - Watch for errors
   - Verify heat pump stays on
   - Check temperature control

5. **Test turning OFF**
   ```bash
   python3 fallback_control.py off
   # Heat pump shuts down
   # keep_alive.py can keep running
   ```

---

## What This Enables

### 🎯 Complete External Control
- Set target temperature
- Turn ON/OFF programmatically
- Read all status values
- No dependency on ThinQ cloud

### 🏠 Home Automation Integration
- Home Assistant
- OpenHAB
- Node-RED
- Custom control logic

### 📊 Advanced Control Strategies
- Weather-compensated heating curves
- Dynamic pricing optimization
- Solar PV integration
- Predictive heating schedules

### 🔧 Independence from Proprietary Apps
- No cloud dependency
- No vendor lock-in
- Open source control
- Community-driven improvements

---

## Chapter 9: The Production Evolution

*"Three scripts? We can do better than that!"*

After proving the concept works, we built a proper production system:

### Docker-Compose Stack
Goodbye manual scripts, hello container orchestration:

```yaml
services:
  heatpump-service:    # FastAPI REST API
  heatpump-ui:         # Web interface
  heatpump-mock:       # Testing without hardware
```

**Key Features:**
- FastAPI service with OpenAPI docs
- Background monitor daemon (replaces keep_alive.py)
- Atomic status.json caching for fast API access
- Health checks and auto-restart
- Read-only mode for safety

### The Monitor Daemon
Our keep_alive.py evolved into a robust daemon:
- Polls every 30 seconds (optimized from 10s)
- Caches status to JSON file
- Prevents supervision timeout with file touch
- Graceful error handling with reconnection
- Console logging: `[ON ] Heating (Auto +2K) | Flow: 39.2°C | ...`

**Lesson 7:** Moving from proof-of-concept scripts to production infrastructure requires health checks, supervision, and graceful degradation.

---

## Chapter 10: The Two's Complement Bug

*"Why does -1K show as +65535K?"*

After implementing LG Auto mode offset control (register 40005), we hit a sneaky bug:

```
User sets offset: -1K
Display shows: Auto +65535K  😱
```

**The Problem:** Register 40005 stores signed integers using two's complement:
- `-1` is stored as `0xFFFF` (65535 unsigned)
- We were reading it as unsigned: 65535 instead of -1

**The Fix:**
```python
def decode_signed_int(value: int) -> int:
    """Convert unsigned 16-bit to signed (two's complement)"""
    if value > 32767:
        value = value - 65536
    return value
```

Applied to `auto_mode_offset` in `read_all_registers()`.

**Result:**
- `-1` now displays correctly as `Auto -1K` ✓
- All negative offsets work perfectly ✓

**Lesson 8:** Always handle signed integers correctly in Modbus registers. Two's complement is standard but easy to forget!

---

## Chapter 11: The Register Discovery

*"Wait, there are TWO different operating mode registers?!"*

Confusion arose when comparing LG's "Auto" mode with our thermostat's "AUTO" mode:

**The Discovery:**
- **INPUT 30002** (operating_mode): What heat pump is ACTUALLY doing
  - 0=Standby, 1=Defrost, 2=Heating, 3=Cooling
  - Read-only, changes based on conditions

- **HOLDING 40001** (op_mode): User's MODE SETTING
  - 0=Cool, 3=Auto, 4=Heat
  - Read/write, stays until changed

- **HOLDING 40005** (auto_mode_offset): NEW! ±5K adjustment
  - Only active when 40001=Auto
  - Fine-tune LG's internal heating curve
  - Range: -5K to +5K

**Example:**
```
User setting (40001): Auto (3)
Current cycle (30002): Heating (2)
Auto offset (40005): +2K

Display: "Heating (LG: Auto +2K)"
```

This explains why heat pump can be in "Auto" mode but actively "Heating" - the user setting is Auto, but conditions dictate heating right now.

**Lesson 9:** Read the register documentation CAREFULLY. Similar-sounding registers may have completely different purposes!

---

## Chapter 11.5: The Target Temperature Revelation

*"Wait... the target temperature doesn't do anything in Auto mode?!"*

After months of monitoring and testing, we discovered a critical detail about how the LG Therma V handles temperature control:

**The Big Revelation:**

When the heat pump is in **Auto mode** (register 40001 = 3), the **target temperature register (40003) is completely ignored!** 🤯

**How Temperature Control Actually Works:**

### Manual Mode (Heat/Cool):
```
Register 40001 = 4 (Heat) or 0 (Cool)
Register 40003 = 380 (38.0°C) ← ACTIVE! Controls flow temperature
Register 40005 = ±X ← Ignored

Flow Temperature: Set directly by user via 40003
```

### Auto Mode:
```
Register 40001 = 3 (Auto)
Register 40003 = 380 (38.0°C) ← IGNORED! Has no effect
Register 40005 = +2K ← ACTIVE! Adjusts heating curve

Flow Temperature: Calculated by LG algorithm
  = f(outdoor_temp, heating_curve, auto_offset)
```

**Why This Matters:**

We initially thought register 40003 was always important. But in Auto mode:
- LG uses its **internal heating curve** (proprietary algorithm)
- Outdoor temperature sensor (INPUT 30013) is the primary input
- Auto mode offset (HOLDING 40005) fine-tunes the curve: ±5K
- Target temperature (HOLDING 40003) sitting at 38.0°C? Doesn't matter!

**UI Implementation:**

Our UI correctly handles this by showing different controls:

| Mode | Register 40001 | UI Display | User Controls |
|------|----------------|------------|---------------|
| Heat | 4 | "Target Water Temperature" slider | 33-50°C setpoint (40003) |
| Cool | 0 | "Target Water Temperature" slider | 33-50°C setpoint (40003) |
| Auto | 3 | "LG Auto Mode Offset" display | Read-only offset display (40005) |

**Example Scenario:**
```
Current state:
- Mode setting: Auto (40001 = 3)
- Target temp: 38.0°C (40003 = 380) ← Meaningless
- Auto offset: +2K (40005 = 2) ← This matters!
- Outdoor temp: 4.3°C
- Actual flow temp: 40.5°C ← Calculated by LG, not from 40003!

If we change 40003 to 45.0°C → Nothing happens!
If we change 40005 to +3K → Flow temp increases!
```

**Why We Missed This Initially:**

During testing, we could set target temp and see flow temp change - but only because we were testing in **Heat mode**, not Auto mode! The confusion happened because:
1. We tested temperature control → worked (we were in Heat mode)
2. We switched to Auto mode → saw flow temp adjust itself
3. We assumed target temp still mattered → it doesn't!

**Lesson 9.5:** Don't assume all registers are always active. The **mode setting** determines which control registers are used. In Auto mode, the LG engineers want you to trust their algorithm - you can only nudge it with the offset!

**The Wisdom:**

LG's Auto mode essentially says: *"We've calculated the optimal heating curve based on physics and outdoor temperature. You can adjust it ±5K if you want, but we're not letting you set arbitrary flow temperatures - that's our job!"*

It's actually clever engineering - prevents users from setting inefficient temperatures that would waste energy or reduce comfort.

---

## Chapter 12: The Prometheus Journey

*"Let's add monitoring!"*

We already had the WAGO energy meter publishing to Prometheus. Why not add heat pump metrics?

### The Integration
1. **FastAPI /metrics endpoint** using prometheus-client
2. **Background metrics updater** reads status.json every 30s
3. **Prometheus scrapes** lg_r290_service:8000/metrics
4. **Docker network magic** - joined modbus_default network
5. **Grafana dashboards** visualize everything

### Metrics Exported
Temperature metrics:
- `heatpump_flow_temperature_celsius`
- `heatpump_return_temperature_celsius`
- `heatpump_outdoor_temperature_celsius`
- `heatpump_target_temperature_celsius`
- `heatpump_temperature_delta_celsius`

Status metrics:
- `heatpump_power_state` (0=OFF, 1=ON)
- `heatpump_compressor_running` (0=OFF, 1=ON)
- `heatpump_water_pump_running` (0=OFF, 1=ON)
- `heatpump_operating_mode` (0-3)
- `heatpump_error_code`

### The Network Challenge
Heat pump service now joins THREE networks:
- `heatpump-net` (internal) - for mock server
- `shelly_bt_temp_default` (external) - for thermostat API
- `modbus_default` (external) - for Prometheus

**Why it works:** Docker DNS resolves container names across networks. Prometheus scrapes `lg_r290_service:8000/metrics` without needing host IP or port mapping!

**Lesson 10:** Prometheus metrics are FREE performance monitoring. Export everything, correlate later!

---

## Chapter 13: The PyModbus Optimization

*"Why are the logs so noisy?"*

After implementing retry logic, we saw these errors constantly:
```
ERROR:pymodbus.client: list index out of range
ERROR:pymodbus.protocol: unpack requires a buffer of 2 bytes
```

But our retries recovered! These weren't real errors.

### The Problem
PyModbus logs EVERY exception at ERROR level, even when retry logic recovers successfully.

### The Solution
```python
# Suppress PyModbus internal error logging
logging.getLogger('pymodbus').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.client').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.protocol').setLevel(logging.CRITICAL)
```

Also optimized:
- Timeout: 30s → 5s (6× faster recovery)
- Inter-request delay: 500ms → 200ms (less latency)
- Added explicit retry/reconnect configuration

**Result:**
- Clean logs showing only real problems ✓
- <6% error rate from RS-485 collisions ✓
- All errors recovered automatically ✓

**Lesson 11:** Tune your retry timeouts aggressively for local networks. 30s timeout on a LAN is overkill!

---

## Chapter 14: The Documentation Effort

*"We should probably document all this..."*

Created comprehensive documentation suite:
- **ARCHITECTURE.md** - System overview
- **MODBUS.md** - Complete register reference
- **PYMODBUS_OPTIMIZATION.md** - Tuning decisions
- **UML Diagrams** (11 sequence diagrams!)
  - Manual control flow
  - AI Mode control
  - Power control
  - Scheduler
  - LG Auto mode offset
  - Prometheus metrics integration
  - Network architecture
  - Error handling
  - ... and more!

Also added:
- **API documentation** via OpenAPI/Swagger
- **README.md** with quick start
- **CHANGELOG.md** tracking versions
- **This journey document!**

**Why?** Because 6 months from now, we won't remember why we set timeout=5 or why register 40005 needs two's complement conversion.

**Lesson 12:** Document as you go. Future-you will thank present-you!

---

## Chapter 15: The Energy State Plot Twist

*"Wait... we don't need register 40010 at all?!"*

Remember all that struggle with Energy State (register 40010) from Chapter 4? The endless testing of values 0, 2, 4, 5? The assumption it was CRITICAL for external control?

**The Plot Twist:** After months of production operation with continuous polling, we discovered:

```python
ENERGY_STATE_VALUE = 0  # 0 = Not used (default)
```

**IT WORKS FINE WITH 0!** 🤦

The real secret was never the Energy State register. It was always:
1. **Continuous polling** (every 10-30 seconds)
2. **That's it. That's the whole secret.**

Setting Energy State = 5 felt like progress during debugging because we were ALSO starting to poll continuously at that point. Classic correlation vs causation mistake!

**The ONLY Real Requirement:**
- ✅ Continuous Modbus polling (heartbeat)

**What's NOT Required (Red Herrings):**
- ❌ Energy State register = Not needed!
- ❌ RMC SLAVE mode = Doesn't affect Modbus!
- ❌ Special initialization sequence = Just start polling!

**Lesson 13:** Sometimes the "critical" things you discovered were just red herrings. The simple solution (keep talking to it) was right all along. Everything else was debugging theater!

---

## Chapter 16: The Ultimate Irony

*"So... about that LG Auto mode..."*

After building:
- Custom AI Mode with heating curves
- Outdoor temperature compensation
- Dynamic flow temperature calculation
- Thermostat API integration
- Sophisticated control algorithms

We discovered register 40005 (Auto Mode Offset) and realized:

**LG ALREADY HAD AN AUTO MODE THAT DOES ALL OF THIS!** 😂

The LG Therma V has its own:
- Internal heating curve
- Outdoor temperature sensor
- Automatic flow temperature calculation
- Fine-tuning via ±5K offset (register 40005)

**The Irony:**
```
What we built:                  What LG included:
─────────────────              ──────────────────
✓ Heating curves               ✓ Built-in heating curve
✓ Outdoor temp sensing         ✓ Outdoor sensor (INPUT 30013)
✓ Auto calculation             ✓ LG Auto mode (HOLDING 40001=3)
✓ Fine-tuning offset           ✓ Auto offset (HOLDING 40005 ±5K)
✓ Complex algorithm            ✓ Already done by LG engineers
```

**But here's the thing:**

We don't regret ANY of it! Here's why:

**What We Gained:**
1. **Deep Understanding** - We know EXACTLY how heating curves work
2. **Flexibility** - We can switch between LG Auto and our AI Mode
3. **Integration** - Our system talks to the thermostat, theirs doesn't
4. **Monitoring** - We export Prometheus metrics, track everything
5. **Learning** - Understanding the physics makes us better users
6. **Fun** - Let's be honest, coding this was genuinely enjoyable
7. **Control** - We're not locked into LG's algorithm
8. **Documentation** - We now understand their system better than their manual

**The Sarcastic Truth:**
*"Sure, we could have just used LG's Auto mode from day one. But then we wouldn't have learned about:*
- *Modbus protocols and retry logic*
- *Two's complement signed integers*
- *Docker networking black magic*
- *Prometheus metrics integration*
- *The satisfaction of making it work ourselves"*

**Lesson 14:** Sometimes the journey is more valuable than the destination. We set out to replace LG's proprietary control, and ended up with:
- ✅ Production-grade monitoring infrastructure
- ✅ Deep knowledge of heat pump physics
- ✅ Ability to choose: LG Auto OR our AI Mode
- ✅ Comprehensive documentation
- ✅ A fun story to tell
- ✅ Skills that transfer to other projects

Would LG Auto mode alone have been enough? Probably.

Was building our own system worth it? **Absolutely!**

*"The best code is the code you learned from, even if you don't end up using it."*

---

## The Happy Ending

After days of frustration, countless test scripts, mysterious shutdowns, and one too many "this should definitely work!" moments...

**We achieved complete, stable, external control of the LG Therma V R290 heat pump via Modbus!**

The heat pump now:
- ✅ Responds to external commands
- ✅ Maintains temperature setpoints
- ✅ Runs stably for extended periods
- ✅ Handles bus collisions gracefully
- ✅ Recovers from connection issues
- ✅ Operates independently of ThinQ

**Most importantly:** We understand WHY it works. The continuous polling requirement is not a workaround - it's the correct way to safely integrate external control with a safety-critical heating system.

---

## Acknowledgments

- **LG Engineers:** For designing a safety feature that prevents runaway heating (even if you didn't document it)
- **pymodbus Community:** For an excellent Modbus library
- **Stack Overflow:** For nothing, because this specific combination of issues was never solved there
- **Trial and Error:** The ultimate teacher
- **Coffee:** The ultimate enabler

---

## Resources

**Official Documentation:**
- LG Therma V R290 Installation Manual
- LG Therma V Modbus Communication Manual (ask your installer)

**Hardware:**
- Waveshare RS485 to Ethernet Module (or equivalent)
- Shielded twisted pair cable for RS-485

**Software:**
- pymodbus: https://pypi.org/project/pymodbus/
- Python 3.7+: https://www.python.org/

**This Repository:**
- `keep_alive.py` - Continuous polling daemon
- `fallback_control.py` - Command-line control tool
- `dump_all_registers.py` - Diagnostic dump tool

---

## Final Thoughts

This journey taught us that modern "smart" devices often have hidden requirements that aren't documented. The continuous polling requirement for the LG Therma V is a perfect example:

- ✅ Good engineering: Safety feature prevents runaway operation
- ❌ Poor documentation: Completely undocumented behavior
- 🤷 Result: Days of debugging for integrators

**If you're reading this because you're attempting the same thing:** You're not crazy. The heat pump really does need continuous communication. Set Energy State to 5, poll every 10 seconds, and it will work.

**If you're reading this for entertainment:** Welcome to the world of industrial automation, where the documentation is sparse and the timeouts are arbitrary!

**If you're from LG:** Please document the continuous polling requirement in the Modbus manual. Future integrators will thank you. 🙏

---

## Status: MISSION ACCOMPLISHED ✅

**Current System State (2025-10-18):**

| Component | Status |
|-----------|--------|
| Heat Pump | 🟢 Running in production |
| External Control | ✅ Complete via Modbus TCP |
| Continuous Polling | ✅ 30s interval, auto-recovery |
| Docker Stack | 🐳 3 containers, health-checked |
| REST API | 🌐 FastAPI with OpenAPI docs |
| Web UI | 💻 Real-time monitoring dashboard |
| Prometheus Metrics | 📊 10 metrics exported |
| Grafana Integration | 📈 Temperature trends, cycles |
| LG Auto Mode Offset | ±5K Fine-tuning working |
| Error Rate | <6% (all auto-recovered) |
| Uptime | 🎯 Days without intervention |
| Read-Only Mode | 🔒 Safety mode active |
| Documentation | 📚 11 UML diagrams, 10+ docs |

**What's Working:**
- ✅ Stable Modbus communication with retry logic
- ✅ Shared RS-485 bus with WAGO meter (no issues)
- ✅ Real-time status monitoring
- ✅ Temperature control (read-only for safety)
- ✅ Prometheus metrics export
- ✅ Cross-stack Docker networking
- ✅ Two's complement signed integers handled correctly
- ✅ Operating mode distinction (cycle vs setting)
- ✅ Automatic error recovery and reconnection
- ✅ Health checks and supervision

**Not Quite There Yet (The Dream):**
- ⏳ Full write access (currently read-only for safety)
- ⏳ AI Mode dynamic control (disabled in read-only)
- ⏳ Automated testing suite
- ⏳ Home Assistant integration
- ⏳ Efficiency analytics (COP calculation)

**But we're 90% there!** The hard parts are solved:
- Continuous polling requirement ✓
- Register mapping ✓
- Error handling ✓
- Production infrastructure ✓
- Monitoring ✓

*The journey was frustrating. The solution was simple. The learning was priceless.*
*And the documentation is comprehensive enough that future-us won't be lost!*

---

*Generated with a mix of frustration, determination, and ultimately joy.*
*May your Modbus communications be stable and your registers always readable.*

🔥 Happy Heating! 🔥
