#!/usr/bin/env python3
"""
LG Therma V Fallback Control Script
Emergency/manual control when Docker stack is down or ThinQ unavailable.

This is your insurance policy - simple, standalone control without any dependencies
on the Docker stack, AI mode, scheduler, or cloud services.

Usage:
    python3 fallback_control.py status              # Show current status
    python3 fallback_control.py on                  # Turn heat pump ON
    python3 fallback_control.py off                 # Turn heat pump OFF
    python3 fallback_control.py temp <value>        # Set target temperature (20-60°C)
    python3 fallback_control.py set <temp> on       # Set temp AND turn ON
    python3 fallback_control.py set <temp> off      # Set temp AND turn OFF

Examples:
    python3 fallback_control.py status
    python3 fallback_control.py on
    python3 fallback_control.py temp 40
    python3 fallback_control.py set 40 on           # Set to 40°C and turn ON
    python3 fallback_control.py off
"""

import asyncio
import sys
from pymodbus.client import AsyncModbusTcpClient


# Configuration - Adjust these for your setup
GATEWAY_IP = "192.168.2.10"
MODBUS_PORT = 8899
DEVICE_ID = 7  # LG Therma V

# Retry configuration for shared gateway
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds between retries
INTER_REQUEST_DELAY = 0.5  # delay between consecutive requests

# Register definitions
COIL_POWER = 0              # 00001: Enable/Disable
HOLDING_OP_MODE = 0         # 40001: Operating Mode (0=Cooling, 3=Auto, 4=Heating)
HOLDING_CONTROL_METHOD = 1  # 40002: Control Method (0=Water outlet, 1=Water inlet, 2=Room air)
HOLDING_TARGET_TEMP = 2     # 40003: Target Temperature Circuit 1
HOLDING_ENERGY_STATE = 9    # 40010: Energy State Input (0=Not used, 2=Normal, 4=ON-Command)
INPUT_ERROR_CODE = 0        # 30001: Error Code
INPUT_OPERATING_MODE = 1    # 30002: ODU Operating Cycle
INPUT_RETURN_TEMP = 2       # 30003: Water Inlet Temperature
INPUT_FLOW_TEMP = 3         # 30004: Water Outlet Temperature
INPUT_OUTDOOR_TEMP = 12     # 30013: Outdoor Air Temperature


def decode_temperature(value):
    """Decode temperature value (0.1°C x10 format)."""
    if value > 32767:
        value = value - 65536
    return value / 10.0


async def modbus_operation_with_retry(client, func, *args, operation_name="operation", **kwargs):
    """
    Execute Modbus operation with retry logic for shared gateway.

    Args:
        client: AsyncModbusTcpClient instance
        func: Modbus function to call
        *args: Arguments to pass to func
        operation_name: Description for error messages
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
                if attempt < MAX_RETRIES - 1:
                    print(f"  ⚠️  Attempt {attempt + 1}/{MAX_RETRIES} failed, retrying...")
                    continue
                return None

            return result

        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES - 1:
                print(f"  ⚠️  Timeout on attempt {attempt + 1}/{MAX_RETRIES}, retrying...")
                continue
            return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"  ⚠️  Error on attempt {attempt + 1}/{MAX_RETRIES}: {e}, retrying...")
                continue
            return None

    return None


async def connect_gateway():
    """Connect to Modbus gateway."""
    client = AsyncModbusTcpClient(
        host=GATEWAY_IP,
        port=MODBUS_PORT,
        timeout=30
    )
    await client.connect()
    if not client.connected:
        print(f"❌ ERROR: Cannot connect to gateway at {GATEWAY_IP}:{MODBUS_PORT}")
        sys.exit(1)
    return client


async def read_status(client):
    """Read current heat pump status."""
    try:
        # Read input registers with retry
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.read_input_registers,
            0, 14,
            operation_name="read input registers",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to read input registers after {MAX_RETRIES} attempts")
            return None

        regs = result.registers

        # Read holding registers (40001-40010) with retry
        await asyncio.sleep(INTER_REQUEST_DELAY)
        holding_result = await modbus_operation_with_retry(
            client,
            client.read_holding_registers,
            0, 10,  # Read registers 40001-40010 (including energy state)
            operation_name="read holding registers",
            slave=DEVICE_ID
        )

        if holding_result is None:
            print(f"❌ Failed to read holding registers after {MAX_RETRIES} attempts")
            return None

        holding_regs = holding_result.registers

        # Read power state with retry
        await asyncio.sleep(INTER_REQUEST_DELAY)
        coil_result = await modbus_operation_with_retry(
            client,
            client.read_coils,
            COIL_POWER, 1,
            operation_name="read coils",
            slave=DEVICE_ID
        )

        if coil_result is None:
            power_state = "Unknown"
        else:
            power_state = "ON" if coil_result.bits[0] else "OFF"

        return {
            'error_code': regs[INPUT_ERROR_CODE],
            'operating_mode': regs[INPUT_OPERATING_MODE],
            'flow_temp': decode_temperature(regs[INPUT_FLOW_TEMP]),
            'return_temp': decode_temperature(regs[INPUT_RETURN_TEMP]),
            'outdoor_temp': decode_temperature(regs[INPUT_OUTDOOR_TEMP]),
            'op_mode': holding_regs[HOLDING_OP_MODE],
            'control_method': holding_regs[HOLDING_CONTROL_METHOD],
            'target_temp': decode_temperature(holding_regs[HOLDING_TARGET_TEMP]),
            'energy_state': holding_regs[HOLDING_ENERGY_STATE],
            'power_state': power_state
        }

    except Exception as e:
        print(f"❌ Exception: {e}")
        return None


def display_status(status):
    """Display heat pump status."""
    if not status:
        print("❌ Failed to read status")
        return

    odu_modes = {0: "Standby", 1: "Cooling", 2: "Heating"}
    mode_str = odu_modes.get(status['operating_mode'], f"Unknown ({status['operating_mode']})")

    op_modes = {0: "Cooling", 3: "Auto", 4: "Heating"}
    op_mode_str = op_modes.get(status['op_mode'], f"Unknown ({status['op_mode']})")

    control_methods = {0: "Water outlet", 1: "Water inlet", 2: "Room air"}
    control_str = control_methods.get(status['control_method'], f"Unknown ({status['control_method']})")

    energy_states = {0: "Not used", 1: "Forced OFF", 2: "Normal", 3: "ON-Rec", 4: "ON-Cmd", 5: "ON-Cmd Step2", 6: "ON-Rec Step1", 7: "Energy Save", 8: "Super Save"}
    energy_str = energy_states.get(status['energy_state'], f"Unknown ({status['energy_state']})")

    print("\n" + "="*60)
    print("LG THERMA V - CURRENT STATUS")
    print("="*60)
    print(f"  Power State:        {status['power_state']}")
    print(f"  ODU Cycle:          {mode_str}")
    print(f"  Error Code:         {status['error_code']} {'✅' if status['error_code'] == 0 else '⚠️'}")
    print()
    print(f"  Op Mode (40001):    {op_mode_str} ({status['op_mode']})")
    print(f"  Control (40002):    {control_str} ({status['control_method']})")
    print(f"  Energy State (40010): {energy_str} ({status['energy_state']}) ⭐")
    print()
    print(f"  Target Flow Temp:   {status['target_temp']:5.1f}°C")
    print(f"  Actual Flow Temp:   {status['flow_temp']:5.1f}°C")
    print(f"  Return Temp:        {status['return_temp']:5.1f}°C")
    print(f"  Outdoor Temp:       {status['outdoor_temp']:5.1f}°C")
    print("="*60 + "\n")


async def cmd_show_status():
    """Command: Show current heat pump status."""
    client = await connect_gateway()

    try:
        status = await read_status(client)
        display_status(status)
        if not status:
            sys.exit(1)

    finally:
        await client.close()


async def cmd_set_power(power_on: bool):
    """Command: Turn heat pump ON or OFF."""
    client = await connect_gateway()

    try:
        print(f"\n{'Turning ON' if power_on else 'Turning OFF'} heat pump...")

        if power_on:
            # STEP 1: Set Energy State to ON-Command Step2 (5) - Required for external control!
            await asyncio.sleep(INTER_REQUEST_DELAY)
            energy_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_ENERGY_STATE, 5,  # 5 = ON-Command Step2 (++ power consumption)
                operation_name="write register (energy state)",
                slave=DEVICE_ID
            )

            if energy_result is None:
                print(f"❌ Failed to set energy state after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Energy state set to ON-Command Step2 (5)")

            # STEP 2: Set Control Method to Water outlet (0)
            await asyncio.sleep(INTER_REQUEST_DELAY)
            control_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_CONTROL_METHOD, 0,  # 0 = Water outlet control
                operation_name="write register (control method)",
                slave=DEVICE_ID
            )

            if control_result is None:
                print(f"❌ Failed to set control method after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Control method set to Water outlet (0)")

            # STEP 3: Set Operating mode to Heating (4)
            await asyncio.sleep(INTER_REQUEST_DELAY)
            mode_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_OP_MODE, 4,  # 4 = Heating mode
                operation_name="write register (heating mode)",
                slave=DEVICE_ID
            )

            if mode_result is None:
                print(f"❌ Failed to set heating mode after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Operating mode set to Heating (4)")

        # STEP 4: Set power ON/OFF
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_coil,
            COIL_POWER, power_on,
            operation_name="write coil (power)",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to set power after {MAX_RETRIES} attempts")
            sys.exit(1)

        print(f"✅ Heat pump turned {'ON' if power_on else 'OFF'}")

        if power_on:
            print("\n⚠️  IMPORTANT: Run keep_alive.py to maintain external control!")
            print("   The heat pump will shut down without continuous Modbus polling.")

        # Show updated status
        await asyncio.sleep(2)
        status = await read_status(client)
        display_status(status)

    finally:
        await client.close()


async def cmd_set_temperature(temp: float):
    """Command: Set target flow temperature."""
    if temp < 20.0 or temp > 60.0:
        print(f"❌ Temperature {temp}°C out of range (20-60°C)")
        sys.exit(1)

    client = await connect_gateway()

    try:
        print(f"\nSetting target temperature to {temp}°C...")

        temp_value = int(temp * 10)
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_register,
            HOLDING_TARGET_TEMP, temp_value,
            operation_name="write register (temperature)",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to set temperature after {MAX_RETRIES} attempts")
            sys.exit(1)

        print(f"✅ Target temperature set to {temp}°C")

        # Wait for change to take effect
        await asyncio.sleep(2)

        # Show updated status
        status = await read_status(client)
        display_status(status)

    finally:
        await client.close()


async def cmd_set_temp_and_power(temp: float, power_on: bool):
    """Command: Set temperature and power state together."""
    if temp < 20.0 or temp > 60.0:
        print(f"❌ Temperature {temp}°C out of range (20-60°C)")
        sys.exit(1)

    client = await connect_gateway()

    try:
        print(f"\nSetting temperature to {temp}°C and turning {'ON' if power_on else 'OFF'}...")

        if power_on:
            # STEP 1: Set Energy State to ON-Command Step2 (5) - Required for external control!
            await asyncio.sleep(INTER_REQUEST_DELAY)
            energy_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_ENERGY_STATE, 5,  # 5 = ON-Command Step2 (++ power consumption)
                operation_name="write register (energy state)",
                slave=DEVICE_ID
            )

            if energy_result is None:
                print(f"❌ Failed to set energy state after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Energy state set to ON-Command Step2 (5)")

            # STEP 2: Set Control Method to Water outlet (0)
            await asyncio.sleep(INTER_REQUEST_DELAY)
            control_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_CONTROL_METHOD, 0,  # 0 = Water outlet control
                operation_name="write register (control method)",
                slave=DEVICE_ID
            )

            if control_result is None:
                print(f"❌ Failed to set control method after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Control method set to Water outlet (0)")

            # STEP 3: Set Operating mode to Heating (4)
            await asyncio.sleep(INTER_REQUEST_DELAY)
            mode_result = await modbus_operation_with_retry(
                client,
                client.write_register,
                HOLDING_OP_MODE, 4,  # 4 = Heating mode
                operation_name="write register (heating mode)",
                slave=DEVICE_ID
            )

            if mode_result is None:
                print(f"❌ Failed to set heating mode after {MAX_RETRIES} attempts")
                sys.exit(1)

            print(f"✅ Operating mode set to Heating (4)")

        # Set temperature
        temp_value = int(temp * 10)
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_register,
            HOLDING_TARGET_TEMP, temp_value,
            operation_name="write register (temperature)",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to set temperature after {MAX_RETRIES} attempts")
            sys.exit(1)

        print(f"✅ Target temperature set to {temp}°C")

        # Then set power ON/OFF
        await asyncio.sleep(INTER_REQUEST_DELAY)
        result = await modbus_operation_with_retry(
            client,
            client.write_coil,
            COIL_POWER, power_on,
            operation_name="write coil (power)",
            slave=DEVICE_ID
        )

        if result is None:
            print(f"❌ Failed to set power after {MAX_RETRIES} attempts")
            sys.exit(1)

        print(f"✅ Heat pump turned {'ON' if power_on else 'OFF'}")

        if power_on:
            print("\n⚠️  IMPORTANT: Run keep_alive.py to maintain external control!")
            print("   The heat pump will shut down without continuous Modbus polling.")

        # Show updated status
        await asyncio.sleep(2)
        status = await read_status(client)
        display_status(status)

    finally:
        await client.close()


def print_usage():
    """Print usage instructions."""
    print(__doc__)
    sys.exit(0)


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()

    command = sys.argv[1].lower()

    if command in ['help', '-h', '--help']:
        print_usage()

    elif command == 'status':
        await cmd_show_status()

    elif command == 'on':
        await cmd_set_power(True)

    elif command == 'off':
        await cmd_set_power(False)

    elif command == 'temp':
        if len(sys.argv) < 3:
            print("❌ ERROR: Missing temperature value")
            print("Usage: fallback_control.py temp <value>")
            sys.exit(1)
        try:
            temp = float(sys.argv[2])
            await cmd_set_temperature(temp)
        except ValueError:
            print(f"❌ ERROR: Invalid temperature '{sys.argv[2]}'")
            sys.exit(1)

    elif command == 'set':
        if len(sys.argv) < 4:
            print("❌ ERROR: Missing arguments")
            print("Usage: fallback_control.py set <temp> <on|off>")
            sys.exit(1)
        try:
            temp = float(sys.argv[2])
            power = sys.argv[3].lower()
            if power not in ['on', 'off']:
                print(f"❌ ERROR: Power must be 'on' or 'off', not '{power}'")
                sys.exit(1)
            await cmd_set_temp_and_power(temp, power == 'on')
        except ValueError:
            print(f"❌ ERROR: Invalid temperature '{sys.argv[2]}'")
            sys.exit(1)

    else:
        print(f"❌ ERROR: Unknown command '{command}'")
        print("\nValid commands: status, on, off, temp, set")
        print("Use 'fallback_control.py help' for more information")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)
