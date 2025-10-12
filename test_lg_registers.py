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
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


# Configuration
GATEWAY_IP = "192.168.2.10"
MODBUS_PORT = 8899
DEVICE_ID = 5  # LG Therma V


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


async def read_input_registers(client):
    """Read Input Registers (0x03) - Sensor readings."""
    print("\n" + "="*80)
    print("INPUT REGISTERS (0x03) - Sensor Readings (Read-Only)")
    print("="*80)

    try:
        # Read first 14 registers (30001-30014)
        result = await client.read_input_registers(0, 14, slave=DEVICE_ID)

        if result.isError():
            print(f"❌ Error reading input registers: {result}")
            return

        print(f"✅ Successfully read {len(result.registers)} input registers:\n")

        regs = result.registers

        # Parse each register according to documentation
        print(f"  30001: Error Code                          = {regs[0]} (0=No Error)")

        odu_cycle = {0: "Standby (OFF)", 1: "Cooling", 2: "Heating"}
        print(f"  30002: ODU Operating Cycle                 = {odu_cycle.get(regs[1], 'Unknown')} ({regs[1]})")

        print(f"  30003: Water Inlet Temperature             = {decode_temperature(regs[2]):6.1f}°C")
        print(f"  30004: Water Outlet Temperature (Flow)     = {decode_temperature(regs[3]):6.1f}°C")
        print(f"  30005: Backup Heater Outlet Temperature    = {decode_temperature(regs[4]):6.1f}°C")
        print(f"  30006: DHW Tank Temperature                = {decode_temperature(regs[5]):6.1f}°C")
        print(f"  30007: Solar Collector Temperature         = {decode_temperature(regs[6]):6.1f}°C")
        print(f"  30008: Room Air Temperature (Circuit 1)    = {decode_temperature(regs[7]):6.1f}°C")
        print(f"  30009: Current Flow Rate                   = {decode_flow_rate(regs[8]):6.1f} LPM")
        print(f"  30010: Flow Temperature (Circuit 2)        = {decode_temperature(regs[9]):6.1f}°C")
        print(f"  30011: Room Air Temperature (Circuit 2)    = {decode_temperature(regs[10]):6.1f}°C")
        print(f"  30012: Energy State Input                  = {regs[11]}")
        print(f"  30013: Outdoor Air Temperature             = {decode_temperature(regs[12]):6.1f}°C")
        print(f"  30014: Water Pressure                      = {decode_pressure(regs[13]):6.1f} bar")

        # Read device info registers (39998-39999)
        print("\n  Device Information:")
        result_info = await client.read_input_registers(39997, 2, slave=DEVICE_ID)
        if not result_info.isError():
            device_group = result_info.registers[0]
            device_info = result_info.registers[1]
            device_types = {0: "Split", 3: "Monoblock", 4: "High Temp", 5: "Medium Temp", 6: "System Boiler"}
            print(f"  39998: Device Group                        = 0x{device_group:04X}")
            print(f"  39999: Device Type                         = {device_types.get(device_info, 'Unknown')} ({device_info})")

    except Exception as e:
        print(f"❌ Exception: {e}")


async def read_holding_registers(client):
    """Read Holding Registers (0x04) - Settings (read/write, but we only read)."""
    print("\n" + "="*80)
    print("HOLDING REGISTERS (0x04) - Settings (Read-Only in this test)")
    print("="*80)

    try:
        # Read first 10 registers (40001-40010)
        result = await client.read_holding_registers(0, 10, slave=DEVICE_ID)

        if result.isError():
            print(f"❌ Error reading holding registers: {result}")
            return

        print(f"✅ Successfully read {len(result.registers)} holding registers:\n")

        regs = result.registers

        # Parse each register according to documentation
        op_modes = {0: "Cooling", 3: "Auto", 4: "Heating"}
        print(f"  40001: Operating Mode                      = {op_modes.get(regs[0], 'Unknown')} ({regs[0]})")

        control_methods = {
            0: "Water Outlet Temp Control",
            1: "Water Inlet Temp Control",
            2: "Room Air Control"
        }
        print(f"  40002: Control Method (Circuit 1/2)        = {control_methods.get(regs[1], 'Unknown')} ({regs[1]})")

        print(f"  40003: Target Temp (Heating/Cooling) C1    = {decode_temperature(regs[2]):6.1f}°C")
        print(f"  40004: Room Air Temperature Circuit 1      = {decode_temperature(regs[3]):6.1f}°C")
        print(f"  40005: Auto Mode Switch Value Circuit 1    = {regs[4]}K")
        print(f"  40006: Target Temp (Heating/Cooling) C2    = {decode_temperature(regs[5]):6.1f}°C")
        print(f"  40007: Room Air Temperature Circuit 2      = {decode_temperature(regs[6]):6.1f}°C")
        print(f"  40008: Auto Mode Switch Value Circuit 2    = {regs[7]}K")
        print(f"  40009: DHW Target Temperature              = {decode_temperature(regs[8]):6.1f}°C")
        print(f"  40010: Energy State Input                  = {regs[9]}")

        # Read power limitation register (40025)
        result_power = await client.read_holding_registers(24, 1, slave=DEVICE_ID)
        if not result_power.isError():
            power_limit = result_power.registers[0] / 10.0
            print(f"  40025: Power Limitation Value              = {power_limit:6.1f} kW")

    except Exception as e:
        print(f"❌ Exception: {e}")


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
        # Read only essential registers (skip coils and discrete inputs)
        await read_input_registers(client)
        await read_holding_registers(client)

        print("\n" + "="*80)
        print("SUMMARY - LG Therma V Status")
        print("="*80)

        # Read current status for summary
        result_input = await client.read_input_registers(0, 14, slave=DEVICE_ID)
        result_holding = await client.read_holding_registers(0, 10, slave=DEVICE_ID)

        if not result_input.isError() and not result_holding.isError():
            inp = result_input.registers
            hold = result_holding.registers

            print(f"\n  System Status:")
            odu_cycle = {0: "OFF/Standby", 1: "Cooling", 2: "HEATING"}
            print(f"    Heat Pump:          {odu_cycle.get(inp[1], 'Unknown')}")
            print(f"    Outdoor Temp:       {decode_temperature(inp[12]):6.1f}°C")
            print(f"    Flow Temp (Actual): {decode_temperature(inp[3]):6.1f}°C")
            print(f"    Flow Temp (Target): {decode_temperature(hold[2]):6.1f}°C")
            print(f"    Room Temp:          {decode_temperature(inp[7]):6.1f}°C")
            print(f"    Flow Rate:          {decode_flow_rate(inp[8]):6.1f} LPM")
            print(f"    Water Pressure:     {decode_pressure(inp[13]):6.1f} bar")
            print(f"    Error Code:         {inp[0]} {'✅ OK' if inp[0] == 0 else '⚠️ ERROR'}")

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
