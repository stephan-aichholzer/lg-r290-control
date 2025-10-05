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
from pydantic import BaseModel

from modbus_client import HeatPumpModbusClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global Modbus client instance
modbus_client: Optional[HeatPumpModbusClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    global modbus_client

    # Startup
    host = os.getenv("MODBUS_HOST", "heatpump-mock")
    port = int(os.getenv("MODBUS_PORT", "502"))
    unit_id = int(os.getenv("MODBUS_UNIT_ID", "1"))
    poll_interval = int(os.getenv("POLL_INTERVAL", "5"))

    logger.info(f"Connecting to Modbus TCP at {host}:{port}, Unit ID: {unit_id}")
    modbus_client = HeatPumpModbusClient(host, port, unit_id, poll_interval)

    await modbus_client.connect()
    modbus_client.start_polling()

    yield

    # Shutdown
    if modbus_client:
        modbus_client.stop_polling()
        await modbus_client.disconnect()
        logger.info("Modbus client disconnected")


# Create FastAPI app
app = FastAPI(
    title="LG R290 Heat Pump API",
    description="REST API for monitoring and controlling LG R290 heat pump via Modbus TCP",
    version="1.0.0",
    lifespan=lifespan
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
    """Heat pump status response."""
    is_on: bool
    compressor_running: bool
    operating_mode: str
    flow_temperature: float
    return_temperature: float
    flow_rate: float
    outdoor_temperature: float
    water_pressure: float
    error_code: int
    has_error: bool


class PowerControl(BaseModel):
    """Power control request."""
    power_on: bool


class TemperatureSetpoint(BaseModel):
    """Temperature setpoint request."""
    temperature: float


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "LG R290 Heat Pump API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not modbus_client or not modbus_client.is_connected:
        raise HTTPException(status_code=503, detail="Modbus connection not available")
    return {"status": "healthy", "modbus_connected": True}


@app.get("/status", response_model=HeatPumpStatus)
async def get_status():
    """Get current heat pump status."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    try:
        status = modbus_client.get_cached_status()
        return status
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/power")
async def set_power(control: PowerControl):
    """Turn heat pump on or off."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    try:
        success = await modbus_client.set_power(control.power_on)
        if success:
            return {"status": "success", "power_on": control.power_on}
        else:
            raise HTTPException(status_code=500, detail="Failed to set power state")
    except Exception as e:
        logger.error(f"Error setting power: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/setpoint")
async def set_temperature_setpoint(setpoint: TemperatureSetpoint):
    """Set target temperature setpoint."""
    if not modbus_client:
        raise HTTPException(status_code=503, detail="Modbus client not initialized")

    # Validate temperature range
    if not 20.0 <= setpoint.temperature <= 60.0:
        raise HTTPException(status_code=400, detail="Temperature must be between 20.0 and 60.0°C")

    try:
        success = await modbus_client.set_target_temperature(setpoint.temperature)
        if success:
            return {"status": "success", "target_temperature": setpoint.temperature}
        else:
            raise HTTPException(status_code=500, detail="Failed to set temperature")
    except Exception as e:
        logger.error(f"Error setting temperature: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/registers/raw")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
