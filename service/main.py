#!/usr/bin/env python3
"""
LG R290 Heat Pump FastAPI Service
Provides REST API for monitoring and controlling the heat pump via Modbus TCP.
"""

import os
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modbus_client import HeatPumpModbusClient
from adaptive_controller import AdaptiveController
from scheduler import Scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global Modbus client instance
modbus_client: Optional[HeatPumpModbusClient] = None

# Global adaptive controller instance
adaptive_controller: Optional[AdaptiveController] = None

# Global scheduler instance
scheduler: Optional[Scheduler] = None

# Feature flags - set to False to disable features
ENABLE_SCHEDULER = True  # Set to False to disable scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    global modbus_client, adaptive_controller, scheduler

    # Startup
    host = os.getenv("MODBUS_HOST", "heatpump-mock")
    port = int(os.getenv("MODBUS_PORT", "502"))
    unit_id = int(os.getenv("MODBUS_UNIT_ID", "1"))
    poll_interval = int(os.getenv("POLL_INTERVAL", "5"))
    thermostat_api_url = os.getenv("THERMOSTAT_API_URL", "http://192.168.2.11:8001")

    logger.info(f"Connecting to Modbus TCP at {host}:{port}, Unit ID: {unit_id}")
    modbus_client = HeatPumpModbusClient(host, port, unit_id, poll_interval)

    await modbus_client.connect()
    modbus_client.start_polling()

    # Initialize adaptive controller
    logger.info("Initializing adaptive controller (AI Mode)")
    adaptive_controller = AdaptiveController(modbus_client, thermostat_api_url)
    adaptive_controller.start()

    # Initialize scheduler (if enabled)
    if ENABLE_SCHEDULER:
        logger.info("Initializing scheduler")
        scheduler = Scheduler(thermostat_api_url, schedule_file="schedule.json")
        # Start scheduler as background task
        asyncio.create_task(scheduler.run())
        logger.info(f"Scheduler started (enabled={scheduler.enabled})")
    else:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER flag")

    yield

    # Shutdown
    if scheduler and ENABLE_SCHEDULER:
        logger.info("Scheduler stopped")

    if adaptive_controller:
        adaptive_controller.stop()
        logger.info("Adaptive controller stopped")

    if modbus_client:
        modbus_client.stop_polling()
        await modbus_client.disconnect()
        logger.info("Modbus client disconnected")


# Create FastAPI app
app = FastAPI(
    title="LG R290 Heat Pump API",
    description="""
# LG R290 Heat Pump Control API

REST API for monitoring and controlling LG R290 7kW heat pump via Modbus TCP.

## Features
- **Heat Pump Control**: Power ON/OFF, temperature setpoint control
- **AI Mode**: Automatic flow temperature adjustment based on outdoor temperature and heating curves
- **Scheduler**: Time-based automatic temperature control (weekday/weekend patterns)
- **Real-time Monitoring**: Live status updates via polling

## Modes
- **Manual Mode**: Direct control of flow temperature setpoint
- **AI Mode (Automatic)**: System calculates optimal flow temperature based on:
  - Outdoor temperature (from Shelly BT sensor)
  - Target room temperature (from thermostat)
  - Selected heating curve (Comfort/Standard/Eco)

## Architecture
- **Service**: FastAPI backend (this API)
- **Heat Pump**: LG R290 via Modbus TCP
- **Thermostat**: Shelly BT temperature control system
- **UI**: Web interface for control and monitoring
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None  # Disable ReDoc
)

# Enable CORS for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class HeatPumpStatus(BaseModel):
    """Complete heat pump status with all sensor readings and operational state."""
    is_on: bool = Field(description="Heat pump power state (true=ON, false=OFF)")
    water_pump_running: bool = Field(description="Water circulation pump status")
    compressor_running: bool = Field(description="Compressor operational status")
    operating_mode: str = Field(description="Current operating mode (Standby, Heating, Cooling)")
    target_temperature: float = Field(description="Target flow temperature setpoint in °C (20.0-60.0)")
    flow_temperature: float = Field(description="Actual flow temperature (water outlet) in °C")
    return_temperature: float = Field(description="Return temperature (water inlet) in °C")
    flow_rate: float = Field(description="Water flow rate in liters per minute (LPM)")
    outdoor_temperature: float = Field(description="Outdoor air temperature in °C (from heat pump sensor)")
    water_pressure: float = Field(description="Water system pressure in bar")
    error_code: int = Field(description="Error code (0 = no error)")
    has_error: bool = Field(description="Error flag indicating if any error is present")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "is_on": True,
                "water_pump_running": False,
                "compressor_running": False,
                "operating_mode": "Standby",
                "target_temperature": 35.0,
                "flow_temperature": 45.0,
                "return_temperature": 30.0,
                "flow_rate": 12.5,
                "outdoor_temperature": 5.0,
                "water_pressure": 1.5,
                "error_code": 0,
                "has_error": False
            }]
        }
    }


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


class AIModeControl(BaseModel):
    """Enable or disable AI Mode (automatic flow temperature control based on heating curves)."""
    enabled: bool = Field(
        description="Set to true to enable AI Mode (automatic), false for manual control"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"enabled": True}, {"enabled": False}]
        }
    }


@app.get(
    "/",
    summary="API Information",
    description="Get API service information and version.",
    tags=["System"]
)
async def root():
    """API root endpoint - returns basic service information."""
    return {
        "service": "LG R290 Heat Pump API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get(
    "/health",
    summary="Health Check",
    description="""
    Check if the API service is healthy and Modbus connection is active.

    Returns HTTP 200 if healthy, HTTP 503 if Modbus connection is unavailable.
    """,
    tags=["System"]
)
async def health_check():
    """Health check endpoint - verifies Modbus connectivity."""
    if not modbus_client or not modbus_client.is_connected:
        raise HTTPException(status_code=503, detail="Modbus connection not available")
    return {"status": "healthy", "modbus_connected": True}


@app.get(
    "/status",
    response_model=HeatPumpStatus,
    summary="Get Heat Pump Status",
    description="""
    Get complete heat pump status including:
    - Power state and operating mode
    - Temperature readings (flow, return, outdoor)
    - Water flow rate and pressure
    - Compressor and pump status
    - Error codes

    Data is cached and updated every 5 seconds via background polling.
    """,
    tags=["Heat Pump"]
)
async def get_status():
    """Get current heat pump status from cached Modbus data."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    try:
        status = modbus_client.get_cached_status()
        return status
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/power",
    summary="Control Heat Pump Power",
    description="""
    Turn the heat pump ON or OFF.

    **Note**: In AI Mode, the system may automatically turn the heat pump ON/OFF
    based on outdoor temperature and heating curve calculations.

    **Effect**: Writes to Modbus coil register 1 (Enable/Disable Heating/Cooling).
    """,
    tags=["Heat Pump"]
)
async def set_power(control: PowerControl):
    """Turn heat pump on or off via Modbus TCP."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    try:
        success = await modbus_client.set_power(control.power_on)
        if success:
            logger.info(f"Heat pump power set to {'ON' if control.power_on else 'OFF'} via API")
            return {"status": "success", "power_on": control.power_on}
        else:
            raise HTTPException(status_code=500, detail="Failed to set power state")
    except Exception as e:
        logger.error(f"Error setting power: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/setpoint",
    summary="Set Flow Temperature Setpoint",
    description="""
    Set target flow temperature (water outlet temperature) in °C.

    **Valid Range**: 20.0°C - 60.0°C

    **Manual Mode**: Temperature is set directly and maintained.

    **AI Mode**: This setting will be overridden by automatic calculations based on:
    - Outdoor temperature
    - Target room temperature
    - Selected heating curve

    **Effect**: Writes to Modbus holding register 40003 (Target Temperature Circuit 1).
    """,
    tags=["Heat Pump"]
)
async def set_temperature_setpoint(setpoint: TemperatureSetpoint):
    """Set target flow temperature setpoint via Modbus TCP."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    # Validate temperature range
    if not 20.0 <= setpoint.temperature <= 60.0:
        raise HTTPException(status_code=400, detail="Temperature must be between 20.0 and 60.0°C")

    try:
        success = await modbus_client.set_target_temperature(setpoint.temperature)
        if success:
            logger.info(f"Flow temperature setpoint changed to {setpoint.temperature}°C")
            return {"status": "success", "target_temperature": setpoint.temperature}
        else:
            raise HTTPException(status_code=500, detail="Failed to set temperature")
    except Exception as e:
        logger.error(f"Error setting temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/registers/raw",
    summary="Get Raw Modbus Registers",
    description="""
    Get raw cached Modbus register values for debugging purposes.

    Returns unprocessed register data including coils, discrete inputs,
    input registers, and holding registers.

    **Use Case**: Troubleshooting, hardware verification, development.
    """,
    tags=["Debug"]
)
async def get_raw_registers():
    """Get raw register values (for debugging)."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    try:
        raw_data = modbus_client.get_raw_registers()
        return raw_data
    except Exception as e:
        logger.error(f"Error getting raw registers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/ai-mode",
    summary="Enable/Disable AI Mode",
    description="""
    Enable or disable AI Mode (automatic flow temperature control).

    **AI Mode Enabled (Automatic)**:
    - System automatically calculates optimal flow temperature
    - Based on outdoor temperature and target room temperature
    - Uses predefined heating curves (Comfort/Standard/Eco)
    - Adjusts every 30 seconds
    - May turn heat pump ON/OFF based on outdoor cutoff temperature

    **AI Mode Disabled (Manual)**:
    - Flow temperature is controlled manually via /setpoint
    - No automatic adjustments

    **Default**: AI Mode is enabled by default at startup for deterministic control.
    """,
    tags=["AI Mode"]
)
async def set_ai_mode(control: AIModeControl):
    """Enable or disable AI mode (adaptive heating curve control)."""
    if not adaptive_controller:
        raise HTTPException(status_code=503, detail="Adaptive controller not initialized")

    try:
        adaptive_controller.enabled = control.enabled
        status_text = "enabled" if control.enabled else "disabled"
        logger.info(f"AI Mode {status_text}")

        return {
            "status": "success",
            "ai_mode": control.enabled,
            "message": f"AI Mode {status_text}"
        }
    except Exception as e:
        logger.error(f"Error setting AI mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/ai-mode",
    summary="Get AI Mode Status",
    description="""
    Get current AI Mode status and detailed information including:
    - Enabled/disabled state
    - Last update timestamp
    - Current outdoor and target room temperatures
    - Calculated flow temperature
    - Selected heating curve
    - Update interval and adjustment threshold

    **Response includes**:
    - `enabled`: AI Mode state
    - `outdoor_temperature`: Current outdoor temp (°C)
    - `target_room_temperature`: Target room temp from thermostat (°C)
    - `calculated_flow_temperature`: Optimal flow temp (°C)
    - `heating_curve`: Selected curve info (name, target temp range)
    """,
    tags=["AI Mode"]
)
async def get_ai_mode():
    """Get current AI mode status and information."""
    if not adaptive_controller:
        raise HTTPException(status_code=503, detail="Adaptive controller not initialized")

    try:
        status = adaptive_controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting AI mode status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/ai-mode/reload-config",
    summary="Reload Heating Curve Configuration",
    description="""
    Hot-reload heating curve configuration from `heating_curve_config.json` without restarting the service.

    **Use Case**: Update heating curves, outdoor cutoff temperatures, or AI Mode parameters
    without downtime.

    **Configuration File**: `service/heating_curve_config.json`

    **Response**:
    - `config_changed`: true if configuration was modified, false if unchanged
    """,
    tags=["AI Mode"]
)
async def reload_heating_curve_config():
    """Reload heating curve configuration without restarting service."""
    if not adaptive_controller:
        raise HTTPException(status_code=503, detail="Adaptive controller not initialized")

    try:
        changed = adaptive_controller.reload_config()
        logger.info(f"AI Mode configuration reloaded via API (config changed: {changed})")
        return {
            "status": "success",
            "config_changed": changed,
            "message": "Configuration reloaded successfully"
        }
    except Exception as e:
        logger.error(f"Error reloading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/schedule",
    summary="Get Scheduler Status",
    description="""
    Get current scheduler status and configuration.

    **Scheduler** automatically sets thermostat mode to AUTO and adjusts target temperature
    at scheduled times (e.g., 05:00 weekdays, 06:00 weekends).

    **Features**:
    - Weekday/weekend patterns
    - Multiple periods per day
    - Only applies when thermostat is in AUTO or ON mode
    - ECO and OFF modes are not affected

    **Response includes**:
    - `enabled`: Scheduler state
    - `schedule_count`: Number of schedule patterns
    - `current_time`: Current system time with timezone
    - `current_day`: Current day of week
    """,
    tags=["Scheduler"]
)
async def get_schedule_status():
    """Get current scheduler status."""
    if not ENABLE_SCHEDULER:
        return {
            "enabled": False,
            "message": "Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
        }

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        status = scheduler.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/schedule/reload",
    summary="Reload Schedule Configuration",
    description="""
    Hot-reload schedule configuration from `schedule.json` without restarting the service.

    **Use Case**: Update schedule times or temperature setpoints without downtime.

    **Configuration File**: `service/schedule.json`

    **Response**:
    - `enabled`: Scheduler enabled state from config
    - `schedule_count`: Number of schedule patterns loaded
    """,
    tags=["Scheduler"]
)
async def reload_schedule_config():
    """Reload schedule configuration without restarting service."""
    if not ENABLE_SCHEDULER:
        raise HTTPException(
            status_code=503,
            detail="Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
        )

    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        result = scheduler.reload_schedule()
        logger.info(f"Schedule configuration reloaded via API (enabled: {result.get('enabled')}, schedules: {result.get('schedule_count')})")
        return result
    except Exception as e:
        logger.error(f"Error reloading schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
