#!/usr/bin/env python3
"""
LG R290 Heat Pump FastAPI Service
Provides REST API for monitoring and controlling the heat pump via Modbus TCP.
"""

import os
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Gauge, make_asgi_app

# Import shared Modbus library (replaces modbus_client.py)
import sys
sys.path.insert(0, '/app')
from lg_r290_modbus import connect_gateway, set_power, set_target_temperature, set_auto_mode_offset

from adaptive_controller import AdaptiveController
from scheduler import Scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Status file path (written by monitor_and_keep_alive.py)
STATUS_FILE = Path("/app/status.json")

# Global Modbus client for write operations
modbus_client = None

# Global adaptive controller instance
adaptive_controller: Optional[AdaptiveController] = None

# Global scheduler instance
scheduler: Optional[Scheduler] = None

# Feature flags - set to False to disable features
ENABLE_SCHEDULER = True  # Set to False to disable scheduler

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Temperature metrics
heatpump_flow_temp = Gauge('heatpump_flow_temperature_celsius', 'Heat pump flow temperature (water outlet)')
heatpump_return_temp = Gauge('heatpump_return_temperature_celsius', 'Heat pump return temperature (water inlet)')
heatpump_outdoor_temp = Gauge('heatpump_outdoor_temperature_celsius', 'Outdoor air temperature')
heatpump_target_temp = Gauge('heatpump_target_temperature_celsius', 'Target temperature setpoint')

# Status metrics
heatpump_power_state = Gauge('heatpump_power_state', 'Power state (0=OFF, 1=ON)')
heatpump_compressor_running = Gauge('heatpump_compressor_running', 'Compressor running (0=OFF, 1=ON)')
heatpump_water_pump_running = Gauge('heatpump_water_pump_running', 'Water pump running (0=OFF, 1=ON)')
heatpump_operating_mode = Gauge('heatpump_operating_mode', 'Operating mode (0=Standby, 1=Cooling, 2=Heating, 3=Auto)')
heatpump_error_code = Gauge('heatpump_error_code', 'Error code (0=no error)')

# Calculated metrics
heatpump_temp_delta = Gauge('heatpump_temperature_delta_celsius', 'Temperature delta (flow - return)')


async def update_prometheus_metrics():
    """Background task to update Prometheus metrics from status.json"""
    logger.info("Starting Prometheus metrics updater (30s interval)")

    while True:
        try:
            if STATUS_FILE.exists():
                with open(STATUS_FILE, 'r') as f:
                    data = json.load(f)

                # Temperature metrics
                flow = data.get('flow_temp')
                ret = data.get('return_temp')
                outdoor = data.get('outdoor_temp')
                target = data.get('target_temp')

                if flow is not None:
                    heatpump_flow_temp.set(flow)
                if ret is not None:
                    heatpump_return_temp.set(ret)
                if outdoor is not None:
                    heatpump_outdoor_temp.set(outdoor)
                if target is not None:
                    heatpump_target_temp.set(target)

                # Calculate delta if both temps available
                if flow is not None and ret is not None:
                    heatpump_temp_delta.set(flow - ret)

                # Status metrics
                heatpump_power_state.set(1 if data.get('power_state') == 'ON' else 0)
                heatpump_compressor_running.set(1 if data.get('operating_mode') in [1, 2] else 0)  # 1=Defrost, 2=Heating
                heatpump_water_pump_running.set(1 if data.get('operating_mode') in [1, 2] else 0)  # Running when compressor active
                heatpump_operating_mode.set(data.get('operating_mode', 0))
                heatpump_error_code.set(data.get('error_code', 0))

        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")

        await asyncio.sleep(30)  # Update every 30s


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    global modbus_client, adaptive_controller, scheduler

    # Startup
    thermostat_api_url = os.getenv("THERMOSTAT_API_URL", "http://192.168.2.11:8001")

    # Connect Modbus client for write operations (read is from status.json)
    logger.info("Connecting to Modbus gateway for control operations...")
    modbus_client = await connect_gateway()

    if not modbus_client:
        logger.error("Failed to connect to Modbus gateway - service may not function correctly")
    else:
        logger.info("✅ Modbus gateway connected")

    # Initialize adaptive controller
    logger.info("Initializing adaptive controller (AI Mode)")
    adaptive_controller = AdaptiveController(STATUS_FILE, thermostat_api_url)
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

    # Start Prometheus metrics updater
    asyncio.create_task(update_prometheus_metrics())

    yield

    # Shutdown
    if scheduler and ENABLE_SCHEDULER:
        logger.info("Scheduler stopped")

    if adaptive_controller:
        adaptive_controller.stop()
        logger.info("Adaptive controller stopped")

    if modbus_client:
        modbus_client.close()
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

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Pydantic models for API
class HeatPumpStatus(BaseModel):
    """Complete heat pump status with all sensor readings and operational state."""
    is_on: bool = Field(description="Heat pump power state (true=ON, false=OFF)")
    water_pump_running: bool = Field(description="Water circulation pump status")
    compressor_running: bool = Field(description="Compressor operational status")
    operating_mode: str = Field(description="Current operating mode (Standby, Heating, Cooling, Auto) - actual cycle state")
    mode_setting: str = Field(description="LG mode setting (Cool, Heat, Auto) - HOLDING register 40001")
    target_temperature: float = Field(description="Target flow temperature setpoint in °C (20.0-60.0) - ONLY USED in Heat/Cool modes, IGNORED in Auto mode")
    auto_mode_offset: int = Field(description="LG Auto mode temperature offset in K (-5 to +5) - ONLY USED in Auto mode, ignored in Heat/Cool modes")
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
    Check if the API service is healthy and status data is available.

    Returns HTTP 200 if healthy, HTTP 503 if status file is unavailable or stale.
    """,
    tags=["System"]
)
async def health_check():
    """Health check endpoint - verifies status file availability."""
    if not STATUS_FILE.exists():
        raise HTTPException(status_code=503, detail="Status file not available")

    # Check if status is recent (within last 30 seconds)
    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)

        from datetime import datetime, timedelta
        timestamp = datetime.fromisoformat(data['timestamp'])
        age = (datetime.now() - timestamp).total_seconds()

        if age > 30:
            raise HTTPException(
                status_code=503,
                detail=f"Status data is stale ({age:.0f}s old)"
            )

        return {"status": "healthy", "status_age_seconds": age}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Status file error: {e}")


@app.get(
    "/status",
    response_model=HeatPumpStatus,
    summary="Get Heat Pump Status",
    description="""
    Get complete heat pump status including:
    - Power state and operating mode
    - Temperature readings (flow, return, outdoor)
    - Water flow rate and pressure (defaults if not available)
    - Compressor and pump status (derived from operating mode)
    - Error codes

    Data is cached and updated every 10 seconds by monitor daemon.
    """,
    tags=["Heat Pump"]
)
async def get_status():
    """Get current heat pump status from status.json file."""
    if not STATUS_FILE.exists():
        raise HTTPException(status_code=503, detail="Status file not available")

    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)

        # Map operating modes (INPUT 30002 - actual cycle state)
        mode_map = {
            0: "Standby",
            1: "Cooling",
            2: "Heating",
            3: "Auto"
        }

        # Map LG mode settings (HOLDING 40001 - user setting)
        lg_mode_setting_map = {
            0: "Cool",
            3: "Auto",
            4: "Heat"
        }

        # Map status.json format to API format
        status = {
            "is_on": data['power_state'] == "ON",
            "water_pump_running": data['operating_mode'] in [1, 2],  # Running in Cooling/Heating
            "compressor_running": data['operating_mode'] in [1, 2],  # Running in Cooling/Heating
            "operating_mode": mode_map.get(data['operating_mode'], "Unknown"),
            "mode_setting": lg_mode_setting_map.get(data['op_mode'], f"Unknown ({data['op_mode']})"),
            "target_temperature": data['target_temp'],
            "auto_mode_offset": data.get('auto_mode_offset', 0),
            "flow_temperature": data['flow_temp'],
            "return_temperature": data['return_temp'],
            "flow_rate": 0.0,  # Not available in current register set
            "outdoor_temperature": data['outdoor_temp'],
            "water_pressure": 0.0,  # Not available in current register set
            "error_code": data['error_code'],
            "has_error": data['error_code'] != 0
        }

        return status
    except Exception as e:
        logger.error(f"Error reading status file: {e}")
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
async def set_power_endpoint(control: PowerControl):
    """Turn heat pump on or off via Modbus TCP."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    try:
        # READ-ONLY MODE: Modbus write disabled
        # success = await set_power(modbus_client, control.power_on)
        success = False  # Disabled
        if False and success:
            logger.info(f"Heat pump power set to {'ON' if control.power_on else 'OFF'} via API")

            # Sync AI Mode with power state
            if adaptive_controller:
                if control.power_on:
                    # Turning ON → Enable AI Mode
                    adaptive_controller.enabled = True
                    logger.info("AI Mode automatically enabled (heat pump turned ON)")
                else:
                    # Turning OFF → Disable AI Mode
                    adaptive_controller.enabled = False
                    logger.info("AI Mode automatically disabled (heat pump turned OFF)")

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

    **IMPORTANT - Mode Behavior:**

    - **Heat/Cool Mode** (register 40001 = 0 or 4): This setting ACTIVELY controls flow temperature
    - **Auto Mode** (register 40001 = 3): This setting is IGNORED by LG's internal heating curve
      - In Auto mode, use `/auto-mode-offset` endpoint instead to adjust the offset (±5K)
      - LG calculates flow temp based on: outdoor_temp + heating_curve + offset

    **AI Mode Note**: This setting will also be overridden by our AI Mode if enabled.

    **Effect**: Writes to Modbus holding register 40003 (Target Temperature Circuit 1).
    """,
    tags=["Heat Pump"]
)
async def set_temperature_setpoint_endpoint(setpoint: TemperatureSetpoint):
    """Set target flow temperature setpoint via Modbus TCP."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    # Validate temperature range
    if not 20.0 <= setpoint.temperature <= 60.0:
        raise HTTPException(status_code=400, detail="Temperature must be between 20.0 and 60.0°C")

    try:
        # READ-ONLY MODE: Modbus write disabled
        # success = await set_target_temperature(modbus_client, setpoint.temperature)
        success = False  # Disabled
        if False and success:
            logger.info(f"Flow temperature setpoint changed to {setpoint.temperature}°C")
            return {"status": "success", "target_temperature": setpoint.temperature}
        else:
            raise HTTPException(status_code=500, detail="Failed to set temperature")
    except Exception as e:
        logger.error(f"Error setting temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
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
    """,
    tags=["Heat Pump"]
)
async def set_auto_mode_offset_endpoint(offset_control: AutoModeOffset):
    """Set LG Auto mode temperature offset via Modbus TCP."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not connected")

    # Validate offset range
    if not -5 <= offset_control.offset <= 5:
        raise HTTPException(status_code=400, detail="Offset must be between -5 and +5 Kelvin")

    try:
        # READ-ONLY MODE: Modbus write disabled
        # success = await set_auto_mode_offset(modbus_client, offset_control.offset)
        success = False  # Disabled
        if False and success:
            logger.info(f"LG Auto mode offset changed to {offset_control.offset:+d}K")
            return {"status": "success", "auto_mode_offset": offset_control.offset}
        else:
            raise HTTPException(status_code=500, detail="Failed to set auto mode offset (read-only mode)")
    except Exception as e:
        logger.error(f"Error setting auto mode offset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/registers/raw",
    summary="Get Raw Status Data",
    description="""
    Get raw status data from status.json file for debugging purposes.

    **Use Case**: Troubleshooting, hardware verification, development.
    """,
    tags=["Debug"]
)
async def get_raw_registers():
    """Get raw status data from status.json (for debugging)."""
    if not STATUS_FILE.exists():
        raise HTTPException(status_code=503, detail="Status file not available")

    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error reading status file: {e}")
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
