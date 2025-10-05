#!/usr/bin/env python3
"""
LG R290 Heat Pump Modbus TCP Mock Server
Simulates the Modbus interface of an LG R290 heat pump using pymodbus.
Register values are backed by a JSON file for easy testing and modification.
"""

import json
import logging
import asyncio
from pathlib import Path
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JSONBackedDataStore:
    """Manages Modbus register values backed by a JSON file."""

    def __init__(self, json_file: str = "registers.json"):
        self.json_file = Path(json_file)
        self.data = self.load_registers()
        logger.info(f"Loaded registers from {self.json_file}")

    def load_registers(self) -> dict:
        """Load register values from JSON file."""
        try:
            with open(self.json_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Register file {self.json_file} not found!")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.json_file}: {e}")
            raise

    def save_registers(self):
        """Save current register values back to JSON file."""
        try:
            with open(self.json_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug(f"Saved registers to {self.json_file}")
        except Exception as e:
            logger.error(f"Failed to save registers: {e}")

    def get_coil_values(self) -> list:
        """Get coil values as a list (0-based addressing).

        Note: Prepends a dummy value at index 0 to account for Modbus 1-based addressing.
        """
        max_addr = max(int(c['address']) for c in self.data['coils'].values())
        values = [False] * (max_addr + 2)  # +2 for dummy value and actual max
        # Offset all values by +1 to account for 1-based Modbus addressing
        for coil in self.data['coils'].values():
            values[coil['address'] + 1] = coil['value']
        return values

    def get_discrete_input_values(self) -> list:
        """Get discrete input values as a list (0-based addressing).

        Note: Prepends a dummy value at index 0 to account for Modbus 1-based addressing.
        """
        if not self.data['discrete_inputs']:
            return [False] * 20
        max_addr = max(int(di['address']) for di in self.data['discrete_inputs'].values())
        size = max(max_addr + 2, 20)  # +2 for dummy value and actual max
        values = [False] * size
        # Offset all values by +1 to account for 1-based Modbus addressing
        for di in self.data['discrete_inputs'].values():
            values[di['address'] + 1] = di['value']
        return values

    def get_input_register_values(self) -> list:
        """Get input register values as a list (0-based addressing).

        Note: Prepends a dummy value at index 0 to account for Modbus 1-based addressing.
        """
        if not self.data['input_registers']:
            return [0] * 20
        max_addr = max(int(ir['address']) for ir in self.data['input_registers'].values())
        size = max(max_addr + 2, 20)  # +2 for dummy value and actual max
        values = [0] * size
        # Offset all values by +1 to account for 1-based Modbus addressing
        for ir in self.data['input_registers'].values():
            values[ir['address'] + 1] = ir['value']
        return values

    def get_holding_register_values(self) -> list:
        """Get holding register values as a list (0-based addressing).

        Note: Prepends a dummy value at index 0 to account for Modbus 1-based addressing.
        """
        max_addr = max(int(hr['address']) for hr in self.data['holding_registers'].values())
        values = [0] * (max_addr + 2)  # +2 for dummy value and actual max
        # Offset all values by +1 to account for 1-based Modbus addressing
        for hr in self.data['holding_registers'].values():
            values[hr['address'] + 1] = hr['value']
        return values


class CustomModbusSlaveContext(ModbusSlaveContext):
    """Custom slave context that syncs writes back to JSON file."""

    def __init__(self, datastore: JSONBackedDataStore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.datastore = datastore

    def setValues(self, fx_code, address, values):
        """Override setValues to sync writes to JSON file."""
        super().setValues(fx_code, address, values)

        # Sync back to JSON for coils (fx=1) and holding registers (fx=3)
        if fx_code == 1:  # Coils
            for reg_id, reg_data in self.datastore.data['coils'].items():
                if reg_data.get('writable', False):
                    addr = reg_data['address']
                    if address <= addr < address + len(values):
                        reg_data['value'] = bool(values[addr - address])
                        logger.info(f"Coil {reg_id} (addr={addr}) updated to {reg_data['value']}")
            self.datastore.save_registers()

        elif fx_code == 3:  # Holding Registers
            for reg_id, reg_data in self.datastore.data['holding_registers'].items():
                if reg_data.get('writable', False):
                    addr = reg_data['address']
                    if address <= addr < address + len(values):
                        reg_data['value'] = int(values[addr - address])
                        logger.info(f"Holding Register {reg_id} (addr={addr}) updated to {reg_data['value']}")
            self.datastore.save_registers()


async def run_server(host: str = "0.0.0.0", port: int = 502):
    """Start the Modbus TCP server."""

    # Load data from JSON
    datastore = JSONBackedDataStore("/app/registers.json")

    # Create data blocks starting at address 0
    coil_block = ModbusSequentialDataBlock(0, datastore.get_coil_values())
    discrete_block = ModbusSequentialDataBlock(0, datastore.get_discrete_input_values())
    input_block = ModbusSequentialDataBlock(0, datastore.get_input_register_values())
    holding_block = ModbusSequentialDataBlock(0, datastore.get_holding_register_values())

    # Create slave context with custom sync functionality
    slave_context = CustomModbusSlaveContext(
        datastore=datastore,
        di=discrete_block,  # Discrete Inputs
        co=coil_block,      # Coils
        hr=holding_block,   # Holding Registers
        ir=input_block      # Input Registers
    )

    # Create server context (unit ID = 1)
    context = ModbusServerContext(slaves={1: slave_context}, single=False)

    # Device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'LG Electronics'
    identity.ProductCode = 'R290'
    identity.VendorUrl = 'http://www.lg.com'
    identity.ProductName = 'LG R290 7kW Heat Pump (MOCK)'
    identity.ModelName = 'R290 MOCK'
    identity.MajorMinorRevision = '1.0.0'

    logger.info(f"Starting Modbus TCP Mock Server on {host}:{port}")
    logger.info("Ready to accept connections...")

    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=(host, port)
    )


if __name__ == "__main__":
    asyncio.run(run_server())
