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

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Gauge, make_asgi_app

# Import shared Modbus library (replaces modbus_client.py)
import sys
sys.path.insert(0, '/app')
from lg_r290_modbus import connect_gateway, set_power, set_target_temperature, set_auto_mode_offset, set_lg_mode

from scheduler import Scheduler
import schedule_api
import heatpump_api

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


async def set_lg_auto_mode_on_startup():
    """
    Set LG Auto mode (register 40001 = 3) as default on service startup.

    This ensures the heat pump always starts in Auto mode regardless of the
    previous state (e.g., after power outage, service restart, or manual mode change).
    """
    try:
        # Wait a few seconds for Modbus connection to stabilize
        await asyncio.sleep(3)

        if not modbus_client:
            logger.warning("Modbus client not connected - cannot set LG Auto mode on startup")
            return

        logger.info("Setting heat pump to LG Auto mode (register 40001 = 3)...")
        success = await set_lg_mode(modbus_client, 3)

        if success:
            logger.info("✅ LG Auto mode set successfully on startup")
        else:
            logger.error("❌ Failed to set LG Auto mode on startup")

    except Exception as e:
        logger.error(f"Error setting LG Auto mode on startup: {e}")


async def sync_lg_offset_on_startup(thermostat_api_url: str):
    """
    Sync LG Auto mode offset with current thermostat mode on service startup.

    This ensures that after a power outage/reboot, the LG offset matches the
    thermostat mode without requiring a browser to be open.
    """
    try:
        # Wait a few seconds for services to stabilize
        await asyncio.sleep(5)

        logger.info("Reading thermostat mode for LG offset sync...")

        # Get current thermostat mode
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{thermostat_api_url}/api/v1/thermostat/config")
            response.raise_for_status()
            thermostat_config = response.json()
            current_mode = thermostat_config.get('mode', 'AUTO')

        logger.info(f"Current thermostat mode: {current_mode}")

        # Load LG offset configuration
        config_file = Path("/app/config.json")
        if not config_file.exists():
            logger.warning("config.json not found - skipping LG offset sync")
            return

        with open(config_file) as f:
            config = json.load(f)

        lg_offset_config = config.get('lg_auto_offset', {})

        if not lg_offset_config.get('enabled', False):
            logger.info("LG Auto offset sync disabled in config")
            return

        # Get offset value for current mode
        mode_mappings = lg_offset_config.get('thermostat_mode_mappings', {})
        target_offset = mode_mappings.get(current_mode, 0)

        logger.info(f"Setting LG Auto offset to {target_offset:+d}K for mode {current_mode}")

        # Set the offset
        if modbus_client:
            success = await set_auto_mode_offset(modbus_client, target_offset)
            if success:
                logger.info(f"✓ LG Auto offset synced: {target_offset:+d}K (mode: {current_mode})")
            else:
                logger.error(f"✗ Failed to set LG Auto offset on startup")
        else:
            logger.warning("Modbus client not available - cannot sync LG offset")

    except Exception as e:
        logger.error(f"Error syncing LG Auto offset on startup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    global modbus_client, scheduler

    # Startup
    thermostat_api_url = os.getenv("THERMOSTAT_API_URL", "http://192.168.2.11:8001")

    # Connect Modbus client for write operations (read is from status.json)
    logger.info("Connecting to Modbus gateway for control operations...")
    modbus_client = await connect_gateway()

    if not modbus_client:
        logger.error("Failed to connect to Modbus gateway - service may not function correctly")
    else:
        logger.info("✅ Modbus gateway connected")

    # Register Modbus client with heatpump_api module
    heatpump_api.set_modbus_client(modbus_client)

    # Initialize scheduler (if enabled)
    if ENABLE_SCHEDULER:
        logger.info("Initializing scheduler")
        heatpump_api_url = "http://localhost:8000"  # Internal API for auto_offset control
        scheduler = Scheduler(thermostat_api_url, schedule_file="schedule.json", heatpump_api_url=heatpump_api_url)
        # Start scheduler as background task
        asyncio.create_task(scheduler.run())
        logger.info(f"Scheduler started (enabled={scheduler.enabled})")

        # Register scheduler instance with schedule_api module
        schedule_api.set_scheduler_instance(scheduler, enabled=True)
    else:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER flag")
        schedule_api.set_scheduler_instance(None, enabled=False)

    # Start Prometheus metrics updater
    asyncio.create_task(update_prometheus_metrics())

    # Set LG Auto mode (3) as default on startup
    logger.info("Setting LG Auto mode as default...")
    asyncio.create_task(set_lg_auto_mode_on_startup())

    # Sync LG Auto offset with current thermostat mode on startup
    logger.info("Syncing LG Auto offset with thermostat mode...")
    asyncio.create_task(sync_lg_offset_on_startup(thermostat_api_url))

    yield

    # Shutdown
    if scheduler and ENABLE_SCHEDULER:
        logger.info("Scheduler stopped")

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

# Mount API routers
app.include_router(schedule_api.router)
app.include_router(heatpump_api.router)


# Pydantic models for API
class HeatPumpStatus(BaseModel):
    """Complete heat pump status with all sensor readings and operational state."""
    is_on: bool = Field(description="Heat pump power state (true=ON, false=OFF)")
    water_pump_running: bool = Field(description="Water circulation pump status")
    compressor_running: bool = Field(description="Compressor operational status")
    operating_mode: str = Field(description="Current operating mode (Standby, Heating, Cooling, Auto) - actual cycle state")
    mode_setting: str = Field(description="LG mode setting (Cool, Heat, Auto) - HOLDING register 40001")
    op_mode: int = Field(description="Raw LG mode register value (3=Auto, 4=Heating) - HOLDING register 40001")
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
            "op_mode": data['op_mode'],  # Raw register 40001 value (3=Auto, 4=Heating)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
