# LG Mode Refactoring Plan
**Branch:** `feature/auto_manual_mode`
**Created:** 2025-10-19

## Goal
Remove the dead-end "AI Mode" / heating curve implementation and replace it with a simple LG mode switch between:
- **LG Auto Mode (register 40001 = 3)**: LG's own heating curve logic + offset adjustment
- **LG Heating Mode (register 40001 = 4)**: Manual flow temperature control (direct slider, no logic)

## Current Status
✅ Analysis complete
✅ Refactoring plan created
⏳ Implementation pending

---

## Files to DELETE Entirely

1. **`service/adaptive_controller.py`** (13KB)
   - Dead-end implementation of custom heating curve logic

2. **`service/heating_curve.py`** (9KB)
   - Dead-end heating curve calculations

---

## Files to MODIFY

### 1. `service/heating_curve_config.json`
**Action:** Clean up - keep ONLY the `lg_auto_offset` section

**Current structure:**
```json
{
  "heating_curves": { ... },  ← DELETE THIS
  "settings": { ... },         ← DELETE THIS
  "lg_auto_offset": { ... }    ← KEEP THIS
}
```

**New structure:**
```json
{
  "lg_auto_offset": {
    "description": "LG Auto Mode offset adjustment based on thermostat mode (ECO/AUTO/ON/OFF)",
    "enabled": true,
    "thermostat_mode_mappings": {
      "ECO": -3,
      "AUTO": 0,
      "ON": 0,
      "OFF": -5
    },
    "settings": {
      "default_offset": 0,
      "min_offset": -5,
      "max_offset": 5
    }
  }
}
```

### 2. `lg_r290_modbus.py`
**Action:** Add new function `set_lg_mode()`

**Add after `set_auto_mode_offset()` function (after line ~419):**
```python
async def set_lg_mode(client: AsyncModbusTcpClient, mode: int) -> bool:
    """
    Set LG heat pump operating mode.

    Args:
        client: Connected Modbus client
        mode: Operating mode:
            - 3 = Auto mode (LG's heating curve logic)
            - 4 = Heating mode (manual flow temperature control)

    Returns:
        True on success, False on failure
    """
    valid_modes = {3: "Auto", 4: "Heating"}

    if mode not in valid_modes:
        logger.error(f"Invalid LG mode {mode}. Valid modes: 3=Auto, 4=Heating")
        return False

    try:
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_register,
            HOLDING_OP_MODE, mode,
            operation_name=f"set LG mode to {valid_modes[mode]} ({mode})",
            slave=DEVICE_ID
        )

        if result is None:
            logger.error(f"Failed to set LG mode to {valid_modes[mode]} ({mode})")
            return False

        logger.info(f"LG mode set to {valid_modes[mode]} (register 40001 = {mode})")
        return True

    except Exception as e:
        logger.error(f"Error setting LG mode: {e}")
        return False
```

### 3. `service/main.py`
**Actions:**

#### A. Remove imports and globals:
```python
# REMOVE these lines:
from adaptive_controller import AdaptiveController
adaptive_controller: Optional[AdaptiveController] = None
```

#### B. Update imports:
```python
# ADD this import:
from lg_r290_modbus import connect_gateway, set_power, set_target_temperature, set_auto_mode_offset, set_lg_mode
```

#### C. Remove from lifespan() function:
```python
# REMOVE these sections in lifespan():
# - Lines ~188-191: adaptive_controller initialization
# - Lines ~216-218: adaptive_controller.stop()
# - Lines ~505-514: AI Mode sync with power state
```

#### D. Remove AI Mode endpoints:
**DELETE these entire endpoint functions:**
- `POST /ai-mode` (lines ~655-692) - set_ai_mode()
- `GET /ai-mode` (lines ~694-726) - get_ai_mode()
- `POST /ai-mode/reload-config` (lines ~728-759) - reload_heating_curve_config()

#### E. Add NEW LG Mode endpoints:
```python
# Pydantic model for request
class LGModeControl(BaseModel):
    mode: int = Field(..., ge=3, le=4, description="LG mode: 3=Auto, 4=Heating")

@app.post(
    "/lg-mode",
    summary="Set LG Operating Mode",
    description="""
    Switch LG heat pump between Auto and Heating modes.

    **Modes:**
    - **3 = Auto Mode**: LG's own heating curve logic (use offset for adjustments)
    - **4 = Heating Mode**: Manual flow temperature control (set via /setpoint)

    **Register**: 40001 (HOLDING_OP_MODE)
    """,
    tags=["Heat Pump"]
)
async def set_lg_mode_endpoint(control: LGModeControl):
    """Set LG heat pump operating mode (Auto=3 or Heating=4)."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    try:
        success = await set_lg_mode(modbus_client, control.mode)
        if success:
            mode_name = "Auto" if control.mode == 3 else "Heating"
            return {"status": "success", "mode": control.mode, "mode_name": mode_name}
        else:
            raise HTTPException(status_code=500, detail="Failed to set LG mode")
    except Exception as e:
        logger.error(f"Error setting LG mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### F. Update status endpoint documentation:
Remove references to "AI Mode" in `/status` endpoint description

### 4. `ui/static/index.html`
**Actions:**

#### A. Replace AI Mode toggle (lines ~30-36):
**OLD:**
```html
<div class="control-item">
    <label class="switch">
        <input type="checkbox" id="ai-mode-switch">
        <span class="slider"></span>
    </label>
    <span class="switch-label">AI</span>
</div>
<div class="ai-status-text" id="ai-status-text">Manual Control</div>
```

**NEW:**
```html
<div class="control-item">
    <label class="switch">
        <input type="checkbox" id="lg-mode-switch">
        <span class="slider"></span>
    </label>
    <span class="switch-label">LG Auto</span>
</div>
<div class="lg-mode-status-text" id="lg-mode-status-text">Manual Heating</div>
```

#### B. Update section visibility logic:
The existing sections are already good:
- `manual-setpoint-section` - Shows when mode=4 (Heating)
- `lg-auto-offset-section` - Shows when mode=3 (Auto)

### 5. `ui/static/heatpump.js`
**Actions:**

#### A. Remove AI mode code:
- Remove `updateAIMode()` function
- Remove AI mode toggle event listener
- Remove AI mode API calls

#### B. Add LG mode toggle:
```javascript
// Initialize LG mode toggle
const lgModeSwitch = document.getElementById('lg-mode-switch');
const lgModeStatusText = document.getElementById('lg-mode-status-text');

lgModeSwitch.addEventListener('change', async () => {
    const mode = lgModeSwitch.checked ? 3 : 4; // 3=Auto, 4=Heating
    await setLGMode(mode);
});

async function setLGMode(mode) {
    try {
        const result = await apiRequest(`${CONFIG.HEATPUMP_API_URL}/lg-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });

        console.log('LG mode set:', result);

        // Update UI
        updateLGModeUI(mode);
    } catch (error) {
        console.error('Failed to set LG mode:', error);
        alert('Failed to set LG mode');
    }
}

function updateLGModeUI(mode) {
    const isAuto = (mode === 3);

    // Update toggle
    lgModeSwitch.checked = isAuto;

    // Update status text
    lgModeStatusText.textContent = isAuto ? 'LG Auto Mode' : 'Manual Heating';

    // Show/hide appropriate sections
    const manualSection = document.getElementById('manual-setpoint-section');
    const autoSection = document.getElementById('lg-auto-offset-section');

    if (isAuto) {
        manualSection.style.display = 'none';
        autoSection.style.display = 'block';
    } else {
        manualSection.style.display = 'block';
        autoSection.style.display = 'none';
    }
}
```

#### C. Update status polling:
```javascript
// In updateStatus() or similar function, add:
const lgMode = data.op_mode; // 3=Auto, 4=Heating
updateLGModeUI(lgMode);
```

### 6. `service/Dockerfile`
**Action:** Remove heating_curve.py and adaptive_controller.py from COPY

**OLD:**
```dockerfile
COPY service/main.py service/heating_curve.py service/adaptive_controller.py service/scheduler.py /app/
```

**NEW:**
```dockerfile
COPY service/main.py service/scheduler.py /app/
```

---

## Implementation Steps (Sequential Order)

### Step 1: Backend - Add LG mode function
- [ ] Add `set_lg_mode()` to `lg_r290_modbus.py`

### Step 2: Backend - Clean up main.py
- [ ] Remove adaptive_controller imports/initialization
- [ ] Remove AI mode endpoints (3 functions)
- [ ] Add LG mode endpoint (POST /lg-mode)
- [ ] Update status endpoint docs

### Step 3: Backend - Clean up config
- [ ] Simplify `heating_curve_config.json` (keep only lg_auto_offset)

### Step 4: Backend - Delete dead files
- [ ] Delete `service/adaptive_controller.py`
- [ ] Delete `service/heating_curve.py`
- [ ] Update `service/Dockerfile`

### Step 5: Frontend - Update HTML
- [ ] Replace AI toggle with LG mode toggle in `index.html`

### Step 6: Frontend - Update JavaScript
- [ ] Remove AI mode code from `heatpump.js`
- [ ] Add LG mode toggle handler
- [ ] Add `updateLGModeUI()` function
- [ ] Update status polling to sync LG mode

### Step 7: Testing
- [ ] Rebuild containers
- [ ] Test LG Auto mode (mode=3): offset controls visible
- [ ] Test Manual Heating mode (mode=4): flow temp slider visible
- [ ] Test mode switching via toggle
- [ ] Test status persistence after restart

### Step 8: Commit
- [ ] Commit all changes with descriptive message

---

## Testing Checklist

After implementation, verify:

1. **LG Auto Mode (3)**
   - [ ] Toggle switch ON shows "LG Auto Mode"
   - [ ] Offset controls visible (-5 to +5)
   - [ ] Flow temperature slider hidden
   - [ ] Offset adjustment works
   - [ ] Mode persists after restart

2. **Manual Heating Mode (4)**
   - [ ] Toggle switch OFF shows "Manual Heating"
   - [ ] Flow temperature slider visible (33-50°C)
   - [ ] Offset controls hidden
   - [ ] Temperature setpoint works
   - [ ] Mode persists after restart

3. **Mode Switching**
   - [ ] Toggle Auto → Heating: UI switches correctly
   - [ ] Toggle Heating → Auto: UI switches correctly
   - [ ] Modbus register 40001 updates correctly
   - [ ] No errors in browser console
   - [ ] No errors in backend logs

---

## Notes

- **Keep thermostat mode offset sync**: The existing functionality that adjusts LG offset based on thermostat mode (ECO/AUTO/ON/OFF) should remain unchanged
- **No breaking changes**: The LG offset functionality is independent and should continue working
- **Simple is better**: No logic behind the scenes - just direct control of LG modes

---

## Design Decisions

- ✅ **No confirmation dialog** - Direct switching for quick control
- ✅ **No compressor protection** - LG handles mode switching safely
- ✅ **Log mode changes** - Add to monitor logs for history/debugging

## Mode Change Logging

Add mode change events to monitoring logs with format:
```
2025-10-21 21:30:45 - INFO - LG Mode changed: Auto → Heating (register 40001: 3 → 4)
2025-10-21 21:35:12 - INFO - LG Mode changed: Heating → Auto (register 40001: 4 → 3)
```
