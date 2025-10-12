#!/usr/bin/env python3
"""
LG Therma V Register Test - Read-Only Mode
Complete register mapping test based on official LG R290 documentation.

Connection:
- Gateway: 192.168.2.10:8899 (Waveshare RS485 to Ethernet)
- Device ID: 5 (LG Therma V)
- Mode: READ ONLY (Safe)
"""

import asyncio
import time
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


# Configuration
GATEWAY_IP = "192.168.2.10"
MODBUS_PORT = 8899
DEVICE_ID = 7  # LG Therma V (changed from 5 to avoid conflict with central control)

# Retry configuration for shared gateway
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds between retries
INTER_REQUEST_DELAY = 0.5  # delay between consecutive requests


def decode_temperature(value):
    """Decode temperature value (0.1°C x10 format)."""
    # Handle signed 16-bit values (for negative temps)
    if value > 32767:
        value = value - 65536
    return value / 10.0


def decode_flow_rate(value):
    """Decode flow rate (0.1 LPM x10 format)."""
    return value / 10.0


def decode_pressure(value):
    """Decode pressure (0.1 bar x10 format)."""
    return value / 10.0


async def read_with_retry(client, func, *args, description="register", **kwargs):
    """
    Read Modbus registers with retry logic for shared gateway.

    Args:
        client: AsyncModbusTcpClient instance
        func: Read function (read_input_registers, read_holding_registers, etc.)
        *args: Arguments to pass to func
        description: Description for logging
        **kwargs: Keyword arguments to pass to func

    Returns:
        Modbus response or None on failure
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Add delay between requests to reduce gateway congestion
            if attempt > 0:
                await asyncio.sleep(RETRY_DELAY * attempt)  # Exponential backoff

            result = await func(*args, **kwargs)

            if result.isError():
                print(f"  ⚠️  Attempt {attempt + 1}/{MAX_RETRIES}: Error reading {description}: {result}")
                if attempt < MAX_RETRIES - 1:
                    continue
                return None

            return result

        except asyncio.TimeoutError:
            print(f"  ⚠️  Attempt {attempt + 1}/{MAX_RETRIES}: Timeout reading {description}")
            if attempt < MAX_RETRIES - 1:
                continue
            return None
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1}/{MAX_RETRIES}: Exception reading {description}: {e}")
            if attempt < MAX_RETRIES - 1:
                continue
            return None

    return None


async def read_input_registers(client):
    """Read Input Registers (0x03) - Essential sensor readings only."""
    print("\n" + "="*80)
    print("INPUT REGISTERS (0x03) - Essential Sensors")
    print("="*80)

    try:
        # Read only essential registers: 30001-30004, 30013
        # These are: Error, Status, Water temps (inlet/outlet), Outdoor temp
        print("Reading essential input registers...")
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await read_with_retry(
            client,
            client.read_input_registers,
            0, 14,  # Read 0-13 to get outdoor temp at index 12
            description="essential input registers",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to read input registers after {MAX_RETRIES} attempts")
            return None

        regs = result.registers

        # Parse only essential registers
        print(f"✅ Successfully read essential registers:\n")

        print(f"  30001: Error Code                          = {regs[0]} {'✅ OK' if regs[0] == 0 else '⚠️ ERROR'}")

        odu_cycle = {0: "OFF/Standby", 1: "Cooling", 2: "Heating"}
        print(f"  30002: Operating Status                    = {odu_cycle.get(regs[1], 'Unknown')} ({regs[1]})")

        print(f"  30003: Water Inlet Temp (Return)           = {decode_temperature(regs[2]):6.1f}°C")
        print(f"  30004: Water Outlet Temp (Flow)            = {decode_temperature(regs[3]):6.1f}°C")
        print(f"  30013: Outdoor Air Temperature             = {decode_temperature(regs[12]):6.1f}°C")

        return regs

    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


async def read_holding_registers(client):
    """Read Holding Registers (0x04) - Essential settings only."""
    print("\n" + "="*80)
    print("HOLDING REGISTERS (0x04) - Essential Settings")
    print("="*80)

    try:
        # Read only essential registers: 40001 (mode), 40003 (target temp)
        print("Reading essential holding registers...")
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await read_with_retry(
            client,
            client.read_holding_registers,
            0, 4,  # Read 40001-40004 (mode, control method, target, room temp)
            description="essential holding registers",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to read holding registers after {MAX_RETRIES} attempts")
            return None

        regs = result.registers

        print(f"✅ Successfully read essential registers:\n")

        # Parse essential registers
        op_modes = {0: "Cooling", 3: "Auto", 4: "Heating"}
        print(f"  40001: Operating Mode                      = {op_modes.get(regs[0], 'Unknown')} ({regs[0]})")

        print(f"  40003: Target Flow Temperature             = {decode_temperature(regs[2]):6.1f}°C")

        return regs

    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


async def main():
    """Main test routine - read essential LG Therma V registers only."""

    print("\n" + "="*80)
    print("LG THERMA V - ESSENTIAL REGISTER TEST")
    print("="*80)
    print(f"Gateway:      {GATEWAY_IP}:{MODBUS_PORT}")
    print(f"Device ID:    {DEVICE_ID} (LG Therma V)")
    print(f"Mode:         READ ONLY (Safe)")
    print("="*80)

    # Create Modbus TCP client with long timeout for shared gateway
    # Multiple clients (WAGO energy meter + LG heat pump) share same RS-485 bus
    # Gateway serializes requests - we just need to be patient
    client = AsyncModbusTcpClient(
        host=GATEWAY_IP,
        port=MODBUS_PORT,
        timeout=30  # 30 seconds - handles queue delays from other polling scripts
    )

    # Connect to gateway
    print("\nConnecting to Waveshare gateway...")
    connected = await client.connect()

    if not connected:
        print(f"❌ FAILED: Could not connect to gateway at {GATEWAY_IP}:{MODBUS_PORT}")
        print("   Check network connectivity and gateway configuration")
        return

    print("✅ Connected to gateway successfully\n")

    try:
        # Read only essential registers
        input_regs = await read_input_registers(client)
        holding_regs = await read_holding_registers(client)

        # Display summary
        print("\n" + "="*80)
        print("SUMMARY - LG Therma V Status")
        print("="*80)

        if input_regs and holding_regs:
            print(f"\n  System Status:")
            odu_cycle = {0: "OFF/Standby", 1: "Cooling", 2: "HEATING"}
            print(f"    Heat Pump:          {odu_cycle.get(input_regs[1], 'Unknown')}")
            print(f"    Outdoor Temp:       {decode_temperature(input_regs[12]):6.1f}°C")
            print(f"    Flow Temp (Actual): {decode_temperature(input_regs[3]):6.1f}°C")
            print(f"    Flow Temp (Target): {decode_temperature(holding_regs[2]):6.1f}°C")
            print(f"    Return Temp:        {decode_temperature(input_regs[2]):6.1f}°C")
            print(f"    Error Code:         {input_regs[0]} {'✅ OK' if input_regs[0] == 0 else '⚠️ ERROR'}")
        else:
            print("\n  ⚠️  Could not read complete status")

        print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Always disconnect
        if client and client.connected:
            await client.close()
        print("Disconnected from gateway")


if __name__ == "__main__":
    print("\n🔒 SAFETY NOTE: This script only READS data - no changes will be made\n")
    asyncio.run(main())
