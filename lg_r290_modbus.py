#!/usr/bin/env python3
"""
LG Therma V R290 - Shared Modbus Library

This module provides core Modbus communication functions for the LG Therma V heat pump.
Used by both standalone scripts and the Docker service.

Key learnings:
- Continuous polling (every 10s) is required to maintain external control
- Energy State register (40010) can stay at 0 (Not used) - polling alone is sufficient
- Retry logic is essential for shared Waveshare gateway (handles WAGO meter contention)
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

# Suppress verbose PyModbus internal error logging
# Only CRITICAL errors (library bugs) will be logged
# Application-level errors are handled by our retry logic
logging.getLogger('pymodbus').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.client').setLevel(logging.CRITICAL)
logging.getLogger('pymodbus.protocol').setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================
GATEWAY_IP = "192.168.2.10"
MODBUS_PORT = 8899
DEVICE_ID = 7  # LG Therma V

# Energy State Configuration
# After testing: Polling alone is sufficient, Energy State = 0 works fine
ENERGY_STATE_VALUE = 0  # 0 = Not used (default)

# Retry configuration for shared gateway (WAGO meter also uses this gateway)
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds between retries
INTER_REQUEST_DELAY = 0.2  # delay between consecutive requests (reduced from 0.5s)

# Timeout for Modbus operations
TIMEOUT = 5  # seconds - local network should respond quickly
# (Reduced from 30s: 5s × 3 retries = 15s recovery vs 90s previously)

# ============================================================================
# Register Definitions
# ============================================================================
# Coil registers
COIL_POWER = 0  # 00001: Enable/Disable

# Holding registers (subtract 1 from documentation address)
HOLDING_OP_MODE = 0          # 40001: Operating Mode (0=Cooling, 3=Auto, 4=Heating)
HOLDING_CONTROL_METHOD = 1   # 40002: Control Method (0=Water outlet, 1=Water inlet, 2=Room air)
HOLDING_TARGET_TEMP = 2      # 40003: Target Temperature Circuit 1
HOLDING_AUTO_MODE_OFFSET = 4 # 40005: Auto Mode Offset (-5 to +5K adjustment in Auto mode)
HOLDING_ENERGY_STATE = 9     # 40010: Energy State Input (0=Not used, 5=ON-Command Step2)

# Input registers (subtract 1 from documentation address)
INPUT_ERROR_CODE = 0         # 30001: Error Code
INPUT_OPERATING_MODE = 1     # 30002: ODU Operating Cycle
INPUT_RETURN_TEMP = 2        # 30003: Water Inlet Temperature (return)
INPUT_FLOW_TEMP = 3          # 30004: Water Outlet Temperature (flow)
INPUT_OUTDOOR_TEMP = 12      # 30013: Outdoor Air Temperature

# ============================================================================
# Helper Functions
# ============================================================================

def decode_temperature(value: int) -> float:
    """
    Decode temperature value from Modbus register.

    LG uses signed 16-bit integers with 0.1°C resolution.
    Example: 350 = 35.0°C, -50 = -5.0°C
    """
    if value > 32767:
        value = value - 65536
    return value / 10.0


# ============================================================================
# Core Modbus Functions
# ============================================================================

async def modbus_operation_with_retry(
    client: AsyncModbusTcpClient,
    func,
    *args,
    operation_name: str = "operation",
    **kwargs
) -> Optional[Any]:
    """
    Execute Modbus operation with retry logic for shared gateway.

    This handles:
    - Bus collisions (WAGO meter on same gateway)
    - Network timeouts
    - Connection errors

    Args:
        client: AsyncModbusTcpClient instance
        func: Modbus function to call (e.g., client.read_holding_registers)
        *args: Arguments to pass to func
        operation_name: Description for logging
        **kwargs: Keyword arguments to pass to func

    Returns:
        Modbus response or None on failure
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between requests to reduce gateway congestion
            if attempt > 0:
                delay = RETRY_DELAY * attempt  # Exponential backoff
                await asyncio.sleep(delay)

            result = await func(*args, **kwargs)

            if result.isError():
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying..."
                    )
                    continue
                logger.error(f"{operation_name} failed after {MAX_RETRIES} attempts")
                return None

            # Success
            if attempt > 0:
                logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
            return result

        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"{operation_name} timeout (attempt {attempt + 1}/{MAX_RETRIES}), "
                    f"retrying..."
                )
                continue
            logger.error(f"{operation_name} timeout after {MAX_RETRIES} attempts")
            return None

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"{operation_name} error (attempt {attempt + 1}/{MAX_RETRIES}): {e}, "
                    f"retrying..."
                )
                continue
            logger.error(f"{operation_name} failed after {MAX_RETRIES} attempts: {e}")
            return None

    return None


async def connect_gateway() -> Optional[AsyncModbusTcpClient]:
    """
    Connect to Modbus TCP gateway.

    Returns:
        Connected client or None on failure
    """
    try:
        client = AsyncModbusTcpClient(
            host=GATEWAY_IP,
            port=MODBUS_PORT,
            timeout=TIMEOUT,
            retries=3,              # Built-in retry mechanism
            reconnect_delay=0.5,    # Start reconnect delay at 500ms
            reconnect_delay_max=10, # Cap reconnect delay at 10s
            name="LG_R290"          # Logger name for debugging
        )

        await client.connect()

        if not client.connected:
            logger.error(f"Failed to connect to gateway at {GATEWAY_IP}:{MODBUS_PORT}")
            return None

        logger.info(f"Connected to Modbus gateway at {GATEWAY_IP}:{MODBUS_PORT}")
        return client

    except Exception as e:
        logger.error(f"Connection error: {e}")
        return None


async def read_all_registers(client: AsyncModbusTcpClient) -> Optional[Dict[str, Any]]:
    """
    Read all heat pump registers and return structured data.

    This reads:
    - Input registers (temperatures, status)
    - Holding registers (settings)
    - Coil (power state)

    Returns:
        Dictionary with all status data, or None on failure
    """
    try:
        # Read input registers (30001-30013) - we need registers 0-12
        await asyncio.sleep(INTER_REQUEST_DELAY)
        input_result = await modbus_operation_with_retry(
            client,
            client.read_input_registers,
            0, 13,  # Changed from 14 to 13 to get registers 0-12
            operation_name="read input registers",
            slave=DEVICE_ID
        )

        if input_result is None:
            logger.error("Failed to read input registers")
            return None

        input_regs = input_result.registers
        logger.debug(f"Read {len(input_regs)} input registers")

        # Read holding registers (40001-40010)
        await asyncio.sleep(INTER_REQUEST_DELAY)
        holding_result = await modbus_operation_with_retry(
            client,
            client.read_holding_registers,
            0, 10,
            operation_name="read holding registers",
            slave=DEVICE_ID
        )

        if holding_result is None:
            logger.error("Failed to read holding registers")
            return None

        holding_regs = holding_result.registers

        # Read power state
        await asyncio.sleep(INTER_REQUEST_DELAY)
        coil_result = await modbus_operation_with_retry(
            client,
            client.read_coils,
            COIL_POWER, 1,
            operation_name="read coils",
            slave=DEVICE_ID
        )

        power_state = "ON" if (coil_result and coil_result.bits[0]) else "OFF"

        # Parse and return structured data
        return {
            'power_state': power_state,
            'error_code': input_regs[INPUT_ERROR_CODE],
            'operating_mode': input_regs[INPUT_OPERATING_MODE],
            'flow_temp': decode_temperature(input_regs[INPUT_FLOW_TEMP]),
            'return_temp': decode_temperature(input_regs[INPUT_RETURN_TEMP]),
            'outdoor_temp': decode_temperature(input_regs[INPUT_OUTDOOR_TEMP]),
            'op_mode': holding_regs[HOLDING_OP_MODE],
            'control_method': holding_regs[HOLDING_CONTROL_METHOD],
            'target_temp': decode_temperature(holding_regs[HOLDING_TARGET_TEMP]),
            'auto_mode_offset': holding_regs[HOLDING_AUTO_MODE_OFFSET],
            'energy_state': holding_regs[HOLDING_ENERGY_STATE],
        }

    except Exception as e:
        logger.error(f"Error reading registers: {e}")
        return None


async def set_power(client: AsyncModbusTcpClient, power_on: bool) -> bool:
    """
    Turn heat pump ON or OFF.

    Args:
        client: Connected Modbus client
        power_on: True to turn ON, False to turn OFF

    Returns:
        True on success, False on failure
    """
    try:
        if power_on:
            # Optional: Set control method and operating mode
            # These are not strictly required if polling is active
            await asyncio.sleep(INTER_REQUEST_DELAY)
            await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_CONTROL_METHOD, 0,  # 0 = Water outlet control
                operation_name="set Control Method",
                slave=DEVICE_ID
            )

            await asyncio.sleep(INTER_REQUEST_DELAY)
            await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_OP_MODE, 4,  # 4 = Heating mode
                operation_name="set Operating Mode",
                slave=DEVICE_ID
            )

        # Set power ON/OFF
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_coil,
            COIL_POWER, power_on,
            operation_name=f"set power {'ON' if power_on else 'OFF'}",
            slave=DEVICE_ID
        )

        if result is None:
            logger.error(f"Failed to set power {'ON' if power_on else 'OFF'}")
            return False

        logger.info(f"Heat pump turned {'ON' if power_on else 'OFF'}")
        return True

    except Exception as e:
        logger.error(f"Error setting power: {e}")
        return False


async def set_target_temperature(client: AsyncModbusTcpClient, temp: float) -> bool:
    """
    Set target flow temperature.

    Args:
        client: Connected Modbus client
        temp: Target temperature in °C (20.0 - 60.0)

    Returns:
        True on success, False on failure
    """
    if temp < 20.0 or temp > 60.0:
        logger.error(f"Temperature {temp}°C out of range (20-60°C)")
        return False

    try:
        temp_value = int(temp * 10)  # Convert to register value

        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_register,
            HOLDING_TARGET_TEMP, temp_value,
            operation_name=f"set temperature to {temp}°C",
            slave=DEVICE_ID
        )

        if result is None:
            logger.error(f"Failed to set temperature to {temp}°C")
            return False

        logger.info(f"Target temperature set to {temp}°C")
        return True

    except Exception as e:
        logger.error(f"Error setting temperature: {e}")
        return False


async def set_auto_mode_offset(client: AsyncModbusTcpClient, offset: int) -> bool:
    """
    Set LG Auto mode temperature offset.

    This adjusts the calculated flow temperature when the heat pump is in Auto mode (40001=3).
    The offset allows fine-tuning without switching to manual control.

    Args:
        client: Connected Modbus client
        offset: Temperature offset in Kelvin (-5 to +5)

    Returns:
        True on success, False on failure
    """
    if offset < -5 or offset > 5:
        logger.error(f"Auto mode offset {offset}K out of range (-5 to +5K)")
        return False

    try:
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_register,
            HOLDING_AUTO_MODE_OFFSET, offset,
            operation_name=f"set auto mode offset to {offset:+d}K",
            slave=DEVICE_ID
        )

        if result is None:
            logger.error(f"Failed to set auto mode offset to {offset:+d}K")
            return False

        logger.info(f"Auto mode offset set to {offset:+d}K")
        return True

    except Exception as e:
        logger.error(f"Error setting auto mode offset: {e}")
        return False
