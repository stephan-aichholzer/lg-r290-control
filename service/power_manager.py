"""
Power Management Module

Automatically controls heat pump power based on temperature conditions
to save energy when heating is not needed (~150W standby power).
"""

import asyncio
import json
import logging
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class PowerManager:
    def __init__(self, modbus_client, thermostat_api_url: str):
        self.modbus_client = modbus_client
        self.thermostat_api_url = thermostat_api_url
        self.enabled = False
        self.turn_off_when = {}
        self.turn_on_when = {}
        self.check_interval = 300

        self.load_config()

    def load_config(self):
        """Load configuration from config.json"""
        try:
            config_file = Path("/app/config.json")
            with open(config_file) as f:
                config = json.load(f).get('power_management', {})

            self.enabled = config.get('enabled', False)
            self.turn_off_when = config.get('turn_off_when', {})
            self.turn_on_when = config.get('turn_on_when', {})
            self.check_interval = config.get('check_interval_seconds', 300)

            logger.info(f"Power manager: enabled={self.enabled}")
        except Exception as e:
            logger.error(f"Failed to load power manager config: {e}")
            self.enabled = False

    async def _set_thermostat_mode(self, mode: str):
        """
        Set thermostat mode (AUTO/ECO/ON/OFF) via thermostat API.

        This syncs the thermostat state with power management decisions:
        - When turning heat pump OFF → Set mode to OFF (stops circulation pump)
        - When turning heat pump ON → Set mode to AUTO (enables automatic pump control)

        Args:
            mode: Thermostat mode to set ("AUTO", "ECO", "ON", or "OFF")
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get current config to preserve other settings
                resp = await client.get(f"{self.thermostat_api_url}/api/v1/thermostat/config")
                resp.raise_for_status()
                current_config = resp.json()

                # Update only the mode, preserve all other settings
                new_config = {
                    'mode': mode,
                    'target_temp': current_config.get('target_temp', 22.0),
                    'eco_temp': current_config.get('eco_temp', 19.0),
                    'hysteresis': current_config.get('hysteresis', 0.1),
                    'min_on_time': current_config.get('min_on_time', 40),
                    'min_off_time': current_config.get('min_off_time', 10),
                    'temp_sample_count': current_config.get('temp_sample_count', 4),
                    'control_interval': current_config.get('control_interval', 60)
                }

                # Set new config with updated mode
                resp = await client.post(
                    f"{self.thermostat_api_url}/api/v1/thermostat/config",
                    json=new_config
                )
                resp.raise_for_status()

                logger.info(f"✓ Thermostat mode set to {mode}")

        except Exception as e:
            logger.error(f"Failed to set thermostat mode to {mode}: {e}")

    async def check_and_control(self):
        """Check temperatures and control power"""
        if not self.enabled:
            return

        try:
            # Get outdoor temp from status.json
            with open("/app/status.json") as f:
                status = json.load(f)
                outdoor_temp = status.get('outdoor_temp')
                is_on = status.get('power_state') == 'ON'

            # Get room temp from thermostat
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.thermostat_api_url}/api/v1/thermostat/status")
                room_temp = resp.json().get('current_temp')

            if outdoor_temp is None or room_temp is None:
                return

            # Turn OFF logic
            if is_on:
                outdoor_ok = outdoor_temp >= self.turn_off_when.get('outdoor_temp_above_or_equal', 999)
                room_ok = room_temp >= self.turn_off_when.get('room_temp_above_or_equal', 999)

                if outdoor_ok and room_ok:
                    logger.info(f"💡 Turning OFF: outdoor={outdoor_temp:.1f}°C, room={room_temp:.1f}°C")

                    # Step 1: Set thermostat mode to OFF (stops circulation pump)
                    await self._set_thermostat_mode("OFF")

                    # Step 2: Turn off heat pump power
                    from lg_r290_modbus import set_power
                    await set_power(self.modbus_client, False)

            # Turn ON logic
            else:
                outdoor_ok = outdoor_temp < self.turn_on_when.get('outdoor_temp_below', -999)
                room_ok = room_temp < self.turn_on_when.get('room_temp_below', -999)

                if outdoor_ok and room_ok:
                    logger.info(f"💡 Turning ON: outdoor={outdoor_temp:.1f}°C, room={room_temp:.1f}°C")

                    # Step 1: Turn on heat pump power
                    from lg_r290_modbus import set_power
                    await set_power(self.modbus_client, True)

                    # Step 2: Set thermostat mode to AUTO (enables automatic pump control)
                    await self._set_thermostat_mode("AUTO")

        except Exception as e:
            logger.error(f"Power manager error: {e}")

    async def run(self):
        """Background task"""
        logger.info("Power manager started")
        while True:
            await self.check_and_control()
            await asyncio.sleep(self.check_interval)
