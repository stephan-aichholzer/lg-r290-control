#!/usr/bin/env python3
"""
Modbus TCP Client for LG R290 Heat Pump
Handles communication with the heat pump via Modbus TCP protocol.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

logger = logging.getLogger(__name__)


class HeatPumpModbusClient:
    """Async Modbus TCP client for LG R290 heat pump."""

    # Register definitions based on LG R290 manual
    COIL_POWER = 0          # Coil 00001: Enable/Disable (Heating/Cooling)

    DISCRETE_WATER_PUMP = 1      # 10002: Water Pump Status
    DISCRETE_COMPRESSOR = 3      # 10004: Compressor Status
    DISCRETE_ERROR = 13          # 10014: Error Message

    INPUT_ERROR_CODE = 0         # 30001: Error Code
    INPUT_OPERATING_MODE = 1     # 30002: ODU Operating Cycle
    INPUT_RETURN_TEMP = 2        # 30003: Water Inlet Temperature (colder, return from system)
    INPUT_FLOW_TEMP = 3          # 30004: Water Outlet Temperature (hotter, flow to system)
    INPUT_FLOW_RATE = 8          # 30009: Current Flow Rate
    INPUT_OUTDOOR_TEMP = 12      # 30013: Outdoor Air Temperature
    INPUT_WATER_PRESSURE = 13    # 30014: Water Pressure

    HOLDING_OP_MODE = 0          # 40001: Operating Mode
    HOLDING_TARGET_TEMP = 2      # 40003: Target Temperature Circuit 1

    def __init__(self, host: str, port: int = 502, unit_id: int = 1, poll_interval: int = 5):
        """Initialize Modbus client.

        Args:
            host: Modbus TCP host address
            port: Modbus TCP port
            unit_id: Modbus unit/slave ID
            poll_interval: Polling interval in seconds
        """
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.poll_interval = poll_interval

        self.client: Optional[AsyncModbusTcpClient] = None
        self.is_connected = False
        self._poll_task: Optional[asyncio.Task] = None
        self._cached_data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to Modbus TCP server."""
        try:
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=10
            )
            await self.client.connect()
            self.is_connected = self.client.connected
            if self.is_connected:
                logger.info(f"Connected to Modbus TCP at {self.host}:{self.port}")
            else:
                logger.error(f"Failed to connect to {self.host}:{self.port}")
            return self.is_connected
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """Disconnect from Modbus TCP server."""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Disconnected from Modbus TCP")

    def start_polling(self):
        """Start background polling task."""
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())
            logger.info(f"Started polling task (interval: {self.poll_interval}s)")

    def stop_polling(self):
        """Stop background polling task."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            logger.info("Stopped polling task")

    async def _poll_loop(self):
        """Background task to poll Modbus registers periodically."""
        while True:
            try:
                await self._update_cached_data()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _update_cached_data(self):
        """Read all registers and update cached data."""
        if not self.is_connected or not self.client:
            logger.warning("Cannot poll: not connected")
            return

        async with self._lock:
            try:
                # Read coils
                coil_result = await self.client.read_coils(self.COIL_POWER, 1, slave=self.unit_id)
                if not coil_result.isError():
                    self._cached_data['is_on'] = coil_result.bits[0]

                # Read discrete inputs
                discrete_result = await self.client.read_discrete_inputs(0, 14, slave=self.unit_id)
                if not discrete_result.isError():
                    self._cached_data['water_pump_running'] = discrete_result.bits[self.DISCRETE_WATER_PUMP]
                    self._cached_data['compressor_running'] = discrete_result.bits[self.DISCRETE_COMPRESSOR]
                    self._cached_data['has_error'] = discrete_result.bits[self.DISCRETE_ERROR]

                # Read input registers
                input_result = await self.client.read_input_registers(0, 14, slave=self.unit_id)
                if not input_result.isError():
                    regs = input_result.registers
                    logger.info(f"Read input registers: {regs[:14]}")
                    self._cached_data['error_code'] = regs[self.INPUT_ERROR_CODE]
                    op_mode_val = regs[self.INPUT_OPERATING_MODE]
                    self._cached_data['operating_mode'] = self._decode_operating_mode(op_mode_val)
                    self._cached_data['flow_temperature'] = regs[self.INPUT_FLOW_TEMP] / 10.0
                    self._cached_data['return_temperature'] = regs[self.INPUT_RETURN_TEMP] / 10.0
                    self._cached_data['flow_rate'] = regs[self.INPUT_FLOW_RATE] / 10.0
                    self._cached_data['outdoor_temperature'] = regs[self.INPUT_OUTDOOR_TEMP] / 10.0
                    self._cached_data['water_pressure'] = regs[self.INPUT_WATER_PRESSURE] / 10.0
                else:
                    logger.error(f"Error reading input registers: {input_result}")

                # Read holding registers (target temperature, operating mode)
                holding_result = await self.client.read_holding_registers(0, 3, slave=self.unit_id)
                if not holding_result.isError():
                    holding_regs = holding_result.registers
                    logger.info(f"Read holding registers: {holding_regs[:3]}")
                    self._cached_data['target_temperature'] = holding_regs[self.HOLDING_TARGET_TEMP] / 10.0
                    self._cached_data['configured_mode'] = holding_regs[self.HOLDING_OP_MODE]
                else:
                    logger.error(f"Error reading holding registers: {holding_result}")

                logger.debug(f"Updated cache: {self._cached_data}")

            except ModbusException as e:
                logger.error(f"Modbus error during polling: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")

    def get_cached_status(self) -> Dict[str, Any]:
        """Get cached status data (non-blocking)."""
        return {
            'is_on': self._cached_data.get('is_on', False),
            'water_pump_running': self._cached_data.get('water_pump_running', False),
            'compressor_running': self._cached_data.get('compressor_running', False),
            'operating_mode': self._cached_data.get('operating_mode', 'Unknown'),
            'target_temperature': self._cached_data.get('target_temperature', 0.0),
            'flow_temperature': self._cached_data.get('flow_temperature', 0.0),
            'return_temperature': self._cached_data.get('return_temperature', 0.0),
            'flow_rate': self._cached_data.get('flow_rate', 0.0),
            'outdoor_temperature': self._cached_data.get('outdoor_temperature', 0.0),
            'water_pressure': self._cached_data.get('water_pressure', 0.0),
            'error_code': self._cached_data.get('error_code', 0),
            'has_error': self._cached_data.get('has_error', False)
        }

    def get_raw_registers(self) -> Dict[str, Any]:
        """Get raw cached register data."""
        return dict(self._cached_data)

    async def set_power(self, power_on: bool) -> bool:
        """Set heat pump power state.

        Args:
            power_on: True to turn on, False to turn off

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.client:
            logger.error("Cannot set power: not connected")
            return False

        try:
            result = await self.client.write_coil(self.COIL_POWER, power_on, slave=self.unit_id)
            if not result.isError():
                logger.info(f"Set power to {'ON' if power_on else 'OFF'}")
                # Update cache immediately
                self._cached_data['is_on'] = power_on
                return True
            else:
                logger.error(f"Failed to set power: {result}")
                return False
        except Exception as e:
            logger.error(f"Error setting power: {e}")
            return False

    async def set_target_temperature(self, temperature: float) -> bool:
        """Set target temperature setpoint.

        Args:
            temperature: Target temperature in °C (20.0 - 60.0)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.client:
            logger.error("Cannot set temperature: not connected")
            return False

        # Convert to register value (0.1°C resolution)
        temp_value = int(temperature * 10)

        try:
            result = await self.client.write_register(
                self.HOLDING_TARGET_TEMP,
                temp_value,
                slave=self.unit_id
            )
            if not result.isError():
                logger.info(f"Set target temperature to {temperature}°C")
                return True
            else:
                logger.error(f"Failed to set temperature: {result}")
                return False
        except Exception as e:
            logger.error(f"Error setting temperature: {e}")
            return False

    @staticmethod
    def _decode_operating_mode(mode_value: int) -> str:
        """Decode operating mode value to string."""
        modes = {
            0: "Standby",
            1: "Cooling",
            2: "Heating"
        }
        return modes.get(mode_value, f"Unknown ({mode_value})")
