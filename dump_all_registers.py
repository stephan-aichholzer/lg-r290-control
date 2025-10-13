#!/usr/bin/env python3
"""
Dump ALL readable registers from LG Therma V
This captures the complete state for comparison
"""

import asyncio
from pymodbus.client import AsyncModbusTcpClient

GATEWAY_IP = "192.168.2.10"
MODBUS_PORT = 8899
DEVICE_ID = 7

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0
INTER_REQUEST_DELAY = 0.5

def decode_temperature(value):
    """Decode temperature value (0.1°C x10 format)."""
    if value > 32767:
        value = value - 65536
    return value / 10.0

async def read_with_retry(client, func, *args, description="register", **kwargs):
    """Read with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                await asyncio.sleep(RETRY_DELAY * attempt)
            result = await func(*args, **kwargs)
            if result.isError():
                if attempt < MAX_RETRIES - 1:
                    continue
                return None
            return result
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                continue
            return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                continue
            return None
    return None

async def main():
    client = AsyncModbusTcpClient(host=GATEWAY_IP, port=MODBUS_PORT, timeout=30)
    await client.connect()

    if not client.connected:
        print("❌ Failed to connect")
        return

    print("="*80)
    print("LG THERMA V - COMPLETE REGISTER DUMP")
    print("="*80)
    print()

    # ========================================================================
    # COIL REGISTERS (0x01) - Control bits (SKIPPED - write-only on LG)
    # ========================================================================
    print("="*80)
    print("COIL REGISTERS (0x01) - Control Bits")
    print("="*80)
    print("⚠️  Skipping coils - typically write-only on LG Therma V")
    print("    These are only used for WRITING commands (power on/off, etc.)")
    print()

    # ========================================================================
    # DISCRETE INPUT REGISTERS (0x02) - Status bits
    # ========================================================================
    print("="*80)
    print("DISCRETE INPUT REGISTERS (0x02) - Operational Status")
    print("="*80)
    await asyncio.sleep(INTER_REQUEST_DELAY)
    result = await read_with_retry(client, client.read_discrete_inputs, 0, 17, description="discrete inputs", slave=DEVICE_ID)
    if result:
        bits = result.bits[:17]
        print(f"10001 (Water Flow Status):       {bits[0]:1d} (0=OK, 1=TOO LOW) ⭐")
        print(f"10002 (Water Pump):              {bits[1]:1d} (0=OFF, 1=ON)")
        print(f"10003 (Ext. Water Pump):         {bits[2]:1d} (0=OFF, 1=ON) ⭐⭐⭐")
        print(f"10004 (Compressor):              {bits[3]:1d} (0=OFF, 1=ON) ⭐")
        print(f"10005 (Defrost):                 {bits[4]:1d} (0=OFF, 1=ON)")
        print(f"10006 (DHW Heating):             {bits[5]:1d} (0=OFF, 1=ON)")
        print(f"10007 (DHW Disinfection):        {bits[6]:1d} (0=OFF, 1=ON)")
        print(f"10008 (Quiet Mode):              {bits[7]:1d} (0=OFF, 1=ON)")
        print(f"10009 (Cooling Status):          {bits[8]:1d} (0=OFF, 1=COOLING) ⭐⭐⭐")
        print(f"10010 (Solar Pump):              {bits[9]:1d} (0=OFF, 1=ON)")
        print(f"10011 (Backup Heater 1):         {bits[10]:1d} (0=OFF, 1=ON)")
        print(f"10012 (Backup Heater 2):         {bits[11]:1d} (0=OFF, 1=ON)")
        print(f"10013 (DHW Booster):             {bits[12]:1d} (0=OFF, 1=ON)")
        print(f"10014 (Error Message):           {bits[13]:1d} (0=OK, 1=ERROR) ⭐")
        print(f"10015 (Emergency Op Available):  {bits[14]:1d} (0=NO, 1=YES)")
        print(f"10016 (Emergency DHW Available): {bits[15]:1d} (0=NO, 1=YES)")
        print(f"10017 (Mixing Pump):             {bits[16]:1d} (0=OFF, 1=ON)")
    else:
        print("⚠️  Failed to read discrete inputs after retries")
    print()

    # ========================================================================
    # INPUT REGISTERS (0x03) - Sensor readings
    # ========================================================================
    print("="*80)
    print("INPUT REGISTERS (0x03) - Sensor Readings")
    print("="*80)
    await asyncio.sleep(INTER_REQUEST_DELAY)
    result = await read_with_retry(client, client.read_input_registers, 0, 14, description="input registers", slave=DEVICE_ID)
    if result:
        regs = result.registers
        print(f"30001 (Error Code):              {regs[0]:5d} ⭐")
        odu_modes = {0: "Standby", 1: "Cooling", 2: "Heating"}
        print(f"30002 (ODU Operating Cycle):     {regs[1]:5d} ({odu_modes.get(regs[1], 'Unknown')}) ⭐⭐⭐")
        print(f"30003 (Water Inlet Temp):        {decode_temperature(regs[2]):6.1f}°C (return)")
        print(f"30004 (Water Outlet Temp):       {decode_temperature(regs[3]):6.1f}°C (flow) ⭐")
        print(f"30005 (Backup Heater Outlet):    {decode_temperature(regs[4]):6.1f}°C")
        print(f"30006 (DHW Tank Temp):           {decode_temperature(regs[5]):6.1f}°C")
        print(f"30007 (Solar Collector Temp):    {decode_temperature(regs[6]):6.1f}°C")
        print(f"30008 (Room Air Temp Circuit 1): {decode_temperature(regs[7]):6.1f}°C")
        print(f"30009 (Flow Rate):               {regs[8]/10.0:6.1f} LPM")
        print(f"30010 (Flow Temp Circuit 2):     {decode_temperature(regs[9]):6.1f}°C")
        print(f"30011 (Room Air Temp Circuit 2): {decode_temperature(regs[10]):6.1f}°C")
        print(f"30012 (Energy State Input):      {regs[11]:5d}")
        print(f"30013 (Outdoor Air Temp):        {decode_temperature(regs[12]):6.1f}°C ⭐")
        print(f"30014 (Water Pressure):          {regs[13]/10.0:6.1f} bar")
    else:
        print("⚠️  Failed to read input registers after retries")
    print()

    # ========================================================================
    # HOLDING REGISTERS (0x04) - Settings
    # ========================================================================
    print("="*80)
    print("HOLDING REGISTERS (0x04) - Configuration Settings")
    print("="*80)
    await asyncio.sleep(INTER_REQUEST_DELAY)
    result = await read_with_retry(client, client.read_holding_registers, 0, 10, description="holding registers", slave=DEVICE_ID)
    if result:
        regs = result.registers
        op_modes = {0: "Cooling", 3: "Auto", 4: "Heating"}
        print(f"40001 (Operating Mode):          {regs[0]:5d} ({op_modes.get(regs[0], 'Unknown')}) ⭐⭐⭐")

        control_methods = {0: "Water outlet", 1: "Water inlet", 2: "Room air"}
        print(f"40002 (Control Method):          {regs[1]:5d} ({control_methods.get(regs[1], 'Unknown')}) ⭐")

        print(f"40003 (Target Temp Circuit 1):   {decode_temperature(regs[2]):6.1f}°C ⭐⭐")
        print(f"40004 (Room Air Temp Circuit 1): {decode_temperature(regs[3]):6.1f}°C")
        print(f"40005 (Auto Mode Switch C1):     {regs[4]:5d} K")
        print(f"40006 (Target Temp Circuit 2):   {decode_temperature(regs[5]):6.1f}°C")
        print(f"40007 (Room Air Temp Circuit 2): {decode_temperature(regs[6]):6.1f}°C")
        print(f"40008 (Auto Mode Switch C2):     {regs[7]:5d} K")
        print(f"40009 (DHW Target Temp):         {decode_temperature(regs[8]):6.1f}°C")
        print(f"40010 (Energy State Input):      {regs[9]:5d} ⭐⭐")
        print(f"      0=Not used, 1=Forced OFF, 2=Normal, 3=ON-Recommendation")
        print(f"      4=ON-Command, 5=ON-Command Step2, 6=ON-Rec Step1")
        print(f"      7=Energy Save, 8=Super Energy Save")
    else:
        print("⚠️  Failed to read holding registers after retries")

    # Try to read 40025 (power limitation)
    await asyncio.sleep(INTER_REQUEST_DELAY)
    result = await read_with_retry(client, client.read_holding_registers, 24, 1, description="power limit", slave=DEVICE_ID)
    if result:
        print(f"40025 (Power Limitation Value):  {result.registers[0]/10.0:6.1f} kW")
    else:
        print(f"40025 (Power Limitation Value):  (Cannot read)")

    print()
    print("="*80)
    print("DUMP COMPLETE")
    print("="*80)
    print("\n⭐ = Important for basic operation")
    print("⭐⭐ = Critical for heating control")
    print("⭐⭐⭐ = KEY SUSPECTS - Check these first!")
    print()
    print("Compare values when:")
    print("1. System working via ThinQ/Touchscreen")
    print("2. System not working via Modbus")
    print()

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
