#!/usr/bin/env python3
"""
Quick read-only test to verify Modbus connection to LG Therma V via Waveshare gateway.

Gateway: 192.168.2.10
Modbus Address: 0x05 (5)
Protocol: Modbus TCP (gateway converts to RS-485)

This script only READS registers - no writes, completely safe.
"""

import asyncio
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


async def test_read_registers():
    """Test reading various register ranges from LG Therma V."""

    GATEWAY_IP = "192.168.2.10"
    MODBUS_PORT = 8899  # Waveshare gateway port (not standard 502)

    # Multiple devices on bus:
    # - WAGO energy meter: Device ID 2
    # - LG Therma V: Device ID 5 (newly added)
    DEVICE_IDS_TO_TEST = [2, 5]  # Test both devices

    print("=" * 80)
    print("RS-485 BUS SCAN - Multiple Devices")
    print("=" * 80)
    print(f"Gateway IP:      {GATEWAY_IP}:{MODBUS_PORT}")
    print(f"Devices on bus:  WAGO Energy Meter (ID 2), LG Therma V (ID 5)")
    print(f"Mode:            READ ONLY (Safe)")
    print("=" * 80)
    print()

    # Create Modbus TCP client
    client = AsyncModbusTcpClient(
        host=GATEWAY_IP,
        port=MODBUS_PORT,
        timeout=10
    )

    # Connect to gateway
    print("Connecting to Waveshare gateway...")
    connected = await client.connect()

    if not connected:
        print("❌ FAILED: Could not connect to gateway")
        print(f"   Check that {GATEWAY_IP} is reachable on your network")
        client.close()
        return

    print("✅ Connected to gateway successfully")
    print()

    try:
        # Test each device on the bus
        for device_id in DEVICE_IDS_TO_TEST:
            device_name = "WAGO Energy Meter" if device_id == 2 else "LG Therma V"
            print(f"\n{'='*80}")
            print(f"TESTING DEVICE ID {device_id} ({device_name})")
            print(f"{'='*80}\n")

            # Test register ranges
            test_ranges = [
                ("Holding Registers (4x)", 0, 10, "read_holding_registers"),
                ("Input Registers (3x)", 0, 10, "read_input_registers"),
            ]

            for range_name, start_addr, count, method in test_ranges:
                print(f"  {range_name} - Address {start_addr}, Count {count}")
                print("  " + "-" * 76)

                try:
                    # Get the appropriate read method
                    read_func = getattr(client, method)

                    # Read registers - pymodbus 3.x uses 'device_id' parameter
                    result = await read_func(address=start_addr, count=count, device_id=device_id)

                    if result.isError():
                        print(f"     ⚠️  Error response: {result}")
                    else:
                        # Display results
                        if hasattr(result, 'registers'):
                            values = result.registers
                            print(f"     ✅ Success - Read {len(values)} registers:")
                            for i, val in enumerate(values):
                                print(f"        [{start_addr + i:4d}] = {val:5d} (0x{val:04X})")

                except asyncio.TimeoutError:
                    print(f"     ❌ Timeout - Device ID {device_id} not responding")
                except ModbusException as e:
                    print(f"     ❌ Modbus exception: {e}")
                except Exception as e:
                    print(f"     ❌ Error: {e}")

                print()

        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. If you see valid data above, the connection is working!")
        print("2. Note which register ranges returned data")
        print("3. We can then map specific registers to heat pump functions")
        print()

    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Always disconnect
        client.close()
        print("Disconnected from gateway")


if __name__ == "__main__":
    print()
    print("SAFETY NOTE: This script only READS data - no changes will be made")
    print()
    asyncio.run(test_read_registers())
