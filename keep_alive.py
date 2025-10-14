#!/usr/bin/env python3
"""
LG Therma V R290 Heat Pump - Keep Alive Script

This script maintains continuous Modbus communication with the LG heat pump
to keep it running in external control mode (Energy State = 5).

The LG Therma V requires regular polling to maintain external control.
If communication stops, it will shut down as a safety feature.

Usage:
    python3 keep_alive.py

Press Ctrl+C to stop.
"""

import asyncio
import struct
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
import sys
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================
GATEWAY_HOST = "192.168.2.10"
GATEWAY_PORT = 8899
DEVICE_ID = 7
TIMEOUT = 30
POLL_INTERVAL = 10  # Poll every 10 seconds

# Register definitions (Modbus addressing: subtract 1 from documentation)
INPUT_ERROR_CODE = 0         # 30001: Error Code
INPUT_OPERATING_MODE = 1     # 30002: ODU Operating Cycle
INPUT_RETURN_TEMP = 2        # 30003: Water Inlet Temperature (return)
INPUT_FLOW_TEMP = 3          # 30004: Water Outlet Temperature (flow)
INPUT_OUTDOOR_TEMP = 12      # 30013: Outdoor Air Temperature
HOLDING_OP_MODE = 0          # 40001: Operating Mode
HOLDING_CONTROL_METHOD = 1   # 40002: Control Method
HOLDING_TARGET_TEMP = 2      # 40003: Target Temperature
HOLDING_ENERGY_STATE = 9     # 40010: Energy State Input

# Operating modes for display
ODU_MODES = {
    0: "Standby",
    1: "Cooling",
    2: "Heating",
    3: "Auto"
}

ENERGY_STATES = {
    0: "Not used",
    1: "Forced OFF",
    2: "Normal",
    3: "ON-Rec",
    4: "ON-Cmd",
    5: "ON-Cmd Step2",
    6: "ON-Rec Step1",
    7: "Energy Save",
    8: "Super Save"
}

# ============================================================================
# Connection Management
# ============================================================================

async def connect_gateway():
    """Connect to Modbus TCP gateway with error handling"""
    try:
        client = AsyncModbusTcpClient(
            host=GATEWAY_HOST,
            port=GATEWAY_PORT,
            timeout=TIMEOUT
        )

        connected = await client.connect()
        if not connected:
            print(f"❌ Failed to connect to gateway at {GATEWAY_HOST}:{GATEWAY_PORT}")
            return None

        print(f"✅ Connected to Waveshare gateway at {GATEWAY_HOST}:{GATEWAY_PORT}", flush=True)
        return client

    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


async def ensure_connection(client):
    """Ensure client is connected, reconnect if necessary"""
    try:
        # Try a simple operation to test connection
        if not client.connected:
            print("⚠️  Connection lost, reconnecting...")
            await client.close()
            await asyncio.sleep(2)

            new_client = await connect_gateway()
            if new_client is None:
                return None
            return new_client
        return client

    except Exception as e:
        print(f"⚠️  Connection check failed: {e}")
        try:
            await client.close()
        except:
            pass
        await asyncio.sleep(2)
        return await connect_gateway()


# ============================================================================
# Modbus Operations with Retry Logic
# ============================================================================

async def modbus_read_with_retry(client, read_func, address, count, max_retries=3):
    """Execute Modbus read operation with retry logic - handles all error types"""
    for attempt in range(max_retries):
        try:
            result = await read_func(address, count, slave=DEVICE_ID)

            # Check if result is valid
            if result.isError():
                if attempt < max_retries - 1:
                    delay = 2 * (attempt + 1)
                    await asyncio.sleep(delay)
                    continue
                return None

            # Verify we got the expected number of registers
            if hasattr(result, 'registers') and len(result.registers) != count:
                # Partial/corrupted response - likely bus collision
                if attempt < max_retries - 1:
                    delay = 2 * (attempt + 1)
                    await asyncio.sleep(delay)
                    continue
                return None

            return result

        except ModbusException as e:
            # Modbus protocol errors
            if attempt < max_retries - 1:
                delay = 2 * (attempt + 1)
                await asyncio.sleep(delay)
                continue
            return None

        except (IndexError, struct.error, ValueError) as e:
            # Corrupted response errors: list index out of range, unpack errors, etc.
            # These indicate bus interference or corrupted packets
            if attempt < max_retries - 1:
                delay = 2 * (attempt + 1)
                await asyncio.sleep(delay)
                continue
            return None

        except (ConnectionError, OSError, asyncio.TimeoutError) as e:
            # Connection/network errors
            if attempt < max_retries - 1:
                delay = 2 * (attempt + 1)
                await asyncio.sleep(delay)
                continue
            return None

        except Exception as e:
            # Catch-all for any other unexpected errors
            if attempt < max_retries - 1:
                delay = 2 * (attempt + 1)
                await asyncio.sleep(delay)
                continue
            return None

    return None


# ============================================================================
# Status Reading
# ============================================================================

async def read_status(client):
    """Read current heat pump status"""
    try:
        # Read input registers (need to read from 0 to get all registers up to 30013)
        input_result = await modbus_read_with_retry(
            client,
            client.read_input_registers,
            0,  # Start from 30001
            13  # Read 13 registers to include outdoor temp at 30013
        )

        if input_result is None:
            return None

        # Read holding registers (operating mode, control method, target temp)
        holding_result = await modbus_read_with_retry(
            client,
            client.read_holding_registers,
            HOLDING_OP_MODE,
            3  # Read 40001-40003 (op mode, control method, target temp)
        )

        if holding_result is None:
            return None

        # Read energy state separately (can't read 40001-40010 in one go efficiently)
        energy_result = await modbus_read_with_retry(
            client,
            client.read_holding_registers,
            HOLDING_ENERGY_STATE,
            1
        )

        if energy_result is None:
            return None

        # Parse temperatures (0.1°C × 10 format)
        regs = input_result.registers
        flow_temp = regs[INPUT_FLOW_TEMP] / 10.0
        return_temp = regs[INPUT_RETURN_TEMP] / 10.0
        outdoor_temp = regs[INPUT_OUTDOOR_TEMP] / 10.0
        operating_mode_odu = regs[INPUT_OPERATING_MODE]

        # Parse holding registers
        holding_regs = holding_result.registers
        operating_mode = holding_regs[HOLDING_OP_MODE]
        target_temp = holding_regs[HOLDING_TARGET_TEMP] / 10.0
        energy_state = energy_result.registers[0]

        return {
            'flow_temp': flow_temp,
            'return_temp': return_temp,
            'outdoor_temp': outdoor_temp,
            'target_temp': target_temp,
            'operating_mode': operating_mode_odu,  # Use ODU cycle for display
            'energy_state': energy_state
        }

    except Exception as e:
        return None


# ============================================================================
# Main Keep-Alive Loop
# ============================================================================

async def keep_alive():
    """Main keep-alive loop with continuous polling"""

    print("="*80, flush=True)
    print("LG Therma V R290 - Keep Alive Monitor", flush=True)
    print("="*80, flush=True)
    print(f"Gateway: {GATEWAY_HOST}:{GATEWAY_PORT}", flush=True)
    print(f"Device ID: {DEVICE_ID}", flush=True)
    print(f"Poll Interval: {POLL_INTERVAL} seconds", flush=True)
    print("="*80, flush=True)
    print(flush=True)

    # Connect to gateway
    client = await connect_gateway()
    if client is None:
        print("❌ Failed to establish initial connection")
        return 1

    print(flush=True)
    print("🔄 Starting continuous polling...", flush=True)
    print("   This keeps the heat pump in external control mode", flush=True)
    print("   Press Ctrl+C to stop", flush=True)
    print(flush=True)

    cycle = 0
    consecutive_failures = 0
    max_consecutive_failures = 5

    try:
        while True:
            cycle += 1
            elapsed = cycle * POLL_INTERVAL
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Ensure connection is alive
            client = await ensure_connection(client)
            if client is None:
                consecutive_failures += 1
                print(f"[{timestamp}] [{elapsed:4d}s] ❌ Connection failed ({consecutive_failures}/{max_consecutive_failures})")

                if consecutive_failures >= max_consecutive_failures:
                    print()
                    print(f"❌ Too many consecutive failures ({max_consecutive_failures})")
                    print("   Please check:")
                    print(f"   - Waveshare gateway is online at {GATEWAY_HOST}:{GATEWAY_PORT}")
                    print(f"   - LG Therma V is powered on with device ID {DEVICE_ID}")
                    print("   - RS-485 wiring is correct (A to A, B to B)")
                    print()
                    return 1

                await asyncio.sleep(POLL_INTERVAL)
                continue

            # Read status
            status = await read_status(client)

            if status is None:
                consecutive_failures += 1
                print(f"[{timestamp}] [{elapsed:4d}s] ❌ Read failed ({consecutive_failures}/{max_consecutive_failures})")

                if consecutive_failures >= max_consecutive_failures:
                    print()
                    print(f"❌ Too many consecutive read failures ({max_consecutive_failures})")
                    print("   The heat pump may have shut down or is not responding")
                    print()
                    return 1

                await asyncio.sleep(POLL_INTERVAL)
                continue

            # Success! Reset failure counter
            consecutive_failures = 0

            # Format status display
            mode_str = ODU_MODES.get(status['operating_mode'], f"Unknown({status['operating_mode']})")
            energy_str = ENERGY_STATES.get(status['energy_state'], f"Unknown({status['energy_state']})")

            print(f"[{timestamp}] [{elapsed:4d}s] "
                  f"Mode: {mode_str:8s} | "
                  f"Target: {status['target_temp']:4.1f}°C | "
                  f"Flow: {status['flow_temp']:5.1f}°C | "
                  f"Return: {status['return_temp']:5.1f}°C | "
                  f"ODU: {status['outdoor_temp']:5.1f}°C | "
                  f"Energy: {energy_str}", flush=True)

            # Wait for next poll
            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print()
        print()
        print("⚠️  Keep-alive stopped by user (Ctrl+C)")
        print()
        print("⚠️  WARNING: Heat pump will shut down within ~60 seconds")
        print("   without continuous Modbus communication!")
        print()
        return 0

    except Exception as e:
        print()
        print(f"❌ Unexpected error: {e}")
        print()
        return 1

    finally:
        if client:
            try:
                await client.close()
                print("✅ Connection closed")
            except:
                pass


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(keep_alive())
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
