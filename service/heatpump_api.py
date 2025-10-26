"""
Heat Pump Control API Module

Provides all heat pump control (write) endpoints and configuration:
- POST /power - Power ON/OFF control
- POST /setpoint - Temperature setpoint control
- POST /auto-mode-offset - LG Auto mode offset adjustment
- POST /lg-mode - LG operating mode switching
- GET /lg-auto-offset-config - LG offset configuration
- GET /registers/raw - Raw register data (debugging)

Separated from main.py to keep the codebase modular and maintainable.
Main.py focuses on monitoring (read-only status), this module handles control (writes).
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import shared Modbus library
import sys
sys.path.insert(0, '/app')
from lg_r290_modbus import set_power, set_target_temperature, set_auto_mode_offset, set_lg_mode

logger = logging.getLogger(__name__)

# Create API router for heat pump control endpoints
router = APIRouter(tags=["Heat Pump"])

# Module-level references (set by main.py during startup)
_modbus_client = None
_status_file = Path("/app/status.json")


def set_modbus_client(client):
    """
    Set the Modbus client instance for this module.

    Called by main.py during application startup.

    Args:
        client: AsyncModbusTcpClient instance for write operations
    """
    global _modbus_client
    _modbus_client = client
    logger.info("Heat Pump API module initialized")


# ============================================================================
# Pydantic Models
# ============================================================================

class PowerControl(BaseModel):
    """Control heat pump power state."""
    power_on: bool = Field(description="Set to true to turn ON, false to turn OFF")

    model_config = {
        "json_schema_extra": {
            "examples": [{"power_on": True}, {"power_on": False}]
        }
    }


class TemperatureSetpoint(BaseModel):
    """Set target flow temperature (water outlet temperature)."""
    temperature: float = Field(
        description="Target flow temperature in °C",
        ge=20.0,
        le=60.0,
        examples=[35.0, 40.0, 45.0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"temperature": 35.0}]
        }
    }


class AutoModeOffset(BaseModel):
    """Set LG Auto mode temperature offset."""
    offset: int = Field(
        description="Temperature offset in Kelvin (K)",
        ge=-5,
        le=5,
        examples=[-2, 0, 2]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"offset": 2}]
        }
    }


class LGModeControl(BaseModel):
    """Set LG heat pump operating mode."""
    mode: int = Field(
        ...,
        ge=3,
        le=4,
        description="LG mode: 3=Auto (LG heating curve), 4=Heating (manual flow temp)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"mode": 3}, {"mode": 4}]
        }
    }


# ============================================================================
# Control Endpoints (Write Operations)
# ============================================================================

@router.post(
    "/power",
    summary="Control Heat Pump Power",
    description="""
    Turn the heat pump ON or OFF.

    **Note**: In AI Mode, the system may automatically turn the heat pump ON/OFF
    based on outdoor temperature and heating curve calculations.

    **Effect**: Writes to Modbus coil register 1 (Enable/Disable Heating/Cooling).
    """
)
async def set_power_endpoint(control: PowerControl):
    """Turn heat pump on or off via Modbus TCP."""
    if not _modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    try:
        success = await set_power(_modbus_client, control.power_on)
        if success:
            logger.info(f"🔌 Heat pump power set to {'ON' if control.power_on else 'OFF'} via API")
            return {"status": "success", "power_on": control.power_on}
        else:
            raise HTTPException(status_code=500, detail="Failed to set power state")
    except Exception as e:
        logger.error(f"Error setting power: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/setpoint",
    summary="Set Flow Temperature Setpoint",
    description="""
    Set target flow temperature (water outlet temperature) in °C.

    **Valid Range**: 20.0°C - 60.0°C

    **IMPORTANT - Mode Behavior:**

    - **Heat/Cool Mode** (register 40001 = 0 or 4): This setting ACTIVELY controls flow temperature
    - **Auto Mode** (register 40001 = 3): This setting is IGNORED by LG's internal heating curve
      - In Auto mode, use `/auto-mode-offset` endpoint instead to adjust the offset (±5K)
      - LG calculates flow temp based on: outdoor_temp + heating_curve + offset

    **AI Mode Note**: This setting will also be overridden by our AI Mode if enabled.

    **Effect**: Writes to Modbus holding register 40003 (Target Temperature Circuit 1).
    """
)
async def set_temperature_setpoint_endpoint(setpoint: TemperatureSetpoint):
    """Set target flow temperature setpoint via Modbus TCP."""
    if not _modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    # Validate temperature range
    if not 20.0 <= setpoint.temperature <= 60.0:
        raise HTTPException(status_code=400, detail="Temperature must be between 20.0 and 60.0°C")

    try:
        # READ-ONLY MODE: Modbus write disabled
        # success = await set_target_temperature(_modbus_client, setpoint.temperature)
        success = False  # Disabled
        if False and success:
            logger.info(f"Flow temperature setpoint changed to {setpoint.temperature}°C")
            return {"status": "success", "target_temperature": setpoint.temperature}
        else:
            raise HTTPException(status_code=500, detail="Failed to set temperature")
    except Exception as e:
        logger.error(f"Error setting temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/auto-mode-offset",
    summary="Set LG Auto Mode Temperature Offset",
    description="""
    Adjust the LG Auto mode temperature by ±5K.

    **Valid Range**: -5 to +5 Kelvin

    **IMPORTANT - Only Active in Auto Mode:**
    - **Auto Mode** (register 40001 = 3): This offset ACTIVELY adjusts the heating curve
      - LG calculates: flow_temp = f(outdoor_temp, heating_curve) + offset
      - Positive offset (+2K): Increases flow temperature (warmer)
      - Negative offset (-2K): Decreases flow temperature (cooler)
    - **Heat/Cool Mode** (register 40001 = 0 or 4): This setting is IGNORED
      - Use `/setpoint` endpoint to control target temperature instead

    **Use Case**: Fine-tune the automatic temperature calculation without switching to manual control.
    For example, if LG Auto mode calculates 35°C flow temperature but rooms feel too cold,
    set offset to +2K to get 37°C.

    **Effect**: Writes to Modbus holding register 40005 (Auto Mode Switch Value Circuit 1).
    """
)
async def set_auto_mode_offset_endpoint(offset_control: AutoModeOffset):
    """Set LG Auto mode temperature offset via Modbus TCP."""
    logger.info(f"=== AUTO MODE OFFSET CHANGE REQUEST ===")
    logger.info(f"Requested offset: {offset_control.offset:+d}°C")

    if not _modbus_client:
        logger.warning("Modbus client not connected - cannot set offset")
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    # Validate offset range
    if not -5 <= offset_control.offset <= 5:
        logger.error(f"Invalid offset value: {offset_control.offset} (must be -5 to +5)")
        raise HTTPException(status_code=400, detail="Offset must be between -5 and +5 Kelvin")

    logger.info(f"Writing to register 40005: {offset_control.offset:+d}°C")
    logger.info(f"Modbus client connected: {_modbus_client.connected if hasattr(_modbus_client, 'connected') else 'unknown'}")

    try:
        # WRITE ENABLED for auto mode offset adjustment only
        success = await set_auto_mode_offset(_modbus_client, offset_control.offset)

        if success:
            logger.info(f"✓ Successfully changed LG Auto mode offset to {offset_control.offset:+d}°C")
            logger.info(f"Register 40005 updated")
            logger.info(f"=== END AUTO MODE OFFSET REQUEST ===")
            return {"status": "success", "auto_mode_offset": offset_control.offset}
        else:
            logger.error(f"✗ Failed to write offset to register 40005")
            logger.info(f"=== END AUTO MODE OFFSET REQUEST ===")
            raise HTTPException(status_code=500, detail="Failed to set auto mode offset")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error setting auto mode offset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/lg-mode",
    summary="Set LG Operating Mode",
    description="""
    Switch LG heat pump between Auto and Heating modes.

    **Modes:**
    - **3 = Auto Mode**: LG's own heating curve logic (use offset for adjustments)
    - **4 = Heating Mode**: Manual flow temperature control (set via /setpoint)

    **Register**: 40001 (HOLDING_OP_MODE)

    **Automatic Actions:**
    - When switching to **Heating mode (4)**, automatically sets flow temperature to
      default value from config.json (lg_heating_mode.default_flow_temperature)

    **Note**: Mode changes are logged for history/debugging.
    """
)
async def set_lg_mode_endpoint(control: LGModeControl):
    """Set LG heat pump operating mode (Auto=3 or Heating=4)."""
    if not _modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    try:
        # Set the LG mode
        success = await set_lg_mode(_modbus_client, control.mode)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set LG mode")

        mode_name = "Auto" if control.mode == 3 else "Heating"

        # When switching to Heating mode, set default flow temperature
        if control.mode == 4:
            # Load default flow temperature from config
            config_file = Path("/app/config.json")
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)

                    heating_config = config.get('lg_heating_mode', {})
                    default_temp = heating_config.get('default_flow_temperature', 40.0)

                    logger.info(f"Setting default flow temperature to {default_temp}°C for Heating mode")

                    # Set the default temperature
                    temp_success = await set_target_temperature(_modbus_client, default_temp)
                    if temp_success:
                        logger.info(f"✓ Default flow temperature set to {default_temp}°C")
                        return {
                            "status": "success",
                            "mode": control.mode,
                            "mode_name": mode_name,
                            "default_temperature": default_temp
                        }
                    else:
                        logger.warning(f"Mode set to Heating but failed to set default temperature")
                except Exception as e:
                    logger.warning(f"Could not set default temperature: {e}")

        return {"status": "success", "mode": control.mode, "mode_name": mode_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting LG mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Configuration & Debug Endpoints
# ============================================================================

@router.get(
    "/lg-auto-offset-config",
    summary="Get LG Auto Offset Configuration",
    description="""
    Get the LG Auto mode offset configuration that maps thermostat modes to offset values.

    **Use Case**: Frontend needs to know which offset to apply when thermostat mode changes.

    **Configuration File**: `service/config.json` (lg_auto_offset section)

    **Response**:
    - `enabled`: Whether auto offset adjustment is enabled
    - `thermostat_mode_mappings`: Map of thermostat mode (ECO/AUTO/ON/OFF) to offset value (-5 to +5)
    - `settings`: Min/max offset and default value

    **Example Response**:
    ```json
    {
      "enabled": true,
      "thermostat_mode_mappings": {
        "ECO": -2,
        "AUTO": 2,
        "ON": 2,
        "OFF": -5
      },
      "settings": {
        "default_offset": 0,
        "min_offset": -5,
        "max_offset": 5
      }
    }
    ```
    """
)
async def get_lg_auto_offset_config():
    """Get LG Auto offset configuration for frontend."""
    config_file = Path("/app/config.json")

    if not config_file.exists():
        raise HTTPException(status_code=503, detail="Configuration file not found")

    try:
        with open(config_file) as f:
            config = json.load(f)

        lg_offset_config = config.get('lg_auto_offset', {})

        if not lg_offset_config:
            # Return default config if not found
            return {
                "enabled": False,
                "thermostat_mode_mappings": {
                    "ECO": 0,
                    "AUTO": 0,
                    "ON": 0,
                    "OFF": 0
                },
                "settings": {
                    "default_offset": 0,
                    "min_offset": -5,
                    "max_offset": 5
                }
            }

        return lg_offset_config
    except Exception as e:
        logger.error(f"Error reading LG auto offset config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/registers/raw",
    summary="Get Raw Status Data",
    description="""
    Get raw status data from status.json file for debugging purposes.

    **Use Case**: Troubleshooting, hardware verification, development.

    **Returns**: Complete raw data including:
    - All register values (no mapping/conversion)
    - Timestamp of last update
    - Raw operating mode codes
    - Unprocessed temperature values

    **Note**: This is a debug endpoint. For normal operations, use `GET /status` instead.
    """
)
async def get_raw_registers():
    """Get raw status data from status.json (for debugging)."""
    if not _status_file.exists():
        raise HTTPException(status_code=503, detail="Status file not available")

    try:
        with open(_status_file) as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error reading status file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
