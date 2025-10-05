#!/usr/bin/env python3
import asyncio
from pymodbus.client import AsyncModbusTcpClient

async def test_read():
    client = AsyncModbusTcpClient(host="localhost", port=5020)
    await client.connect()

    result = await client.read_input_registers(0, 14, slave=1)
    if not result.isError():
        print("Read input registers (0-13):")
        for i, val in enumerate(result.registers[:14]):
            print(f"  Index {i}: {val}")
    else:
        print(f"Error: {result}")

    client.close()

asyncio.run(test_read())
