# AI Mode Issue - Missing Room Temperature Check

## Problem Summary

AI Mode turns ON the heat pump based solely on:
1. Outdoor temperature (< 15°C restart threshold)
2. Target room temperature (from schedule)

**AI Mode does NOT check the actual current room temperature!**

## Example - What Happened on 2025-10-14 at 23:38

**Situation:**
- Container restarted (supervision loop detected failed monitor daemon)
- Time: 23:38 (Monday night)
- Schedule: Night setback to 21.5°C target
- Outdoor temp: 10.4°C
- **Actual room temp: Unknown (not checked!)**

**AI Mode Decision:**
```
Outdoor: 10.4°C < 15°C (restart threshold) → Heat pump should be ON
Target room: 21.5°C (from schedule)
Selected curve: Comfort (21-23°C range)
Calculated flow: 37°C
Result: TURNED ON HEAT PUMP
```

**The Problem:**
- Room was likely already at 22°C or warmer (heating all day)
- Heat pump turned ON to support 21.5°C target
- No check: "Is room already warm enough?"

## Missing Logic

AI Mode should ask before turning ON:

```python
if actual_room_temp >= target_room_temp:
    # Room is already warm enough
    return None  # Heat pump OFF

if actual_room_temp < target_room_temp - hysteresis:
    # Room needs heating
    return calculated_flow_temp  # Heat pump ON
```

## Current Behavior

**Turns ON when:**
- Outdoor < 15°C (restart threshold)

**Should turn ON when:**
- Outdoor < 15°C **AND**
- Actual room temp < target room temp

## Impact

- Heat pump runs unnecessarily when room is already warm
- Wastes energy
- Overheats rooms
- Defeats purpose of night setback schedule

## Solution Needed

Add actual room temperature check to AI Mode before turning ON heat pump.

**Data available:**
- Thermostat API provides `current_temp` (actual room temperature)
- Already used for outdoor temp, just need to read `current_temp` field

**Implementation:**
1. Read actual room temp from thermostat API
2. Compare: actual_room_temp vs target_room_temp
3. Only turn ON if: actual < target - hysteresis
4. Add hysteresis (e.g., 0.5°C) to prevent oscillation

## Files to Modify

- `service/adaptive_controller.py` - Add room temp comparison logic
- `service/heating_curve.py` - Add parameter for actual room temp check

## Status

**Issue identified:** 2025-10-15
**Priority:** Medium (energy waste, but not critical)
**Fix needed:** Add room temperature comparison before heat pump activation
