"""
Power Management Module

Automatically controls heat pump power based on temperature conditions
to save energy when heating is not needed (~150W standby power).

Also handles offset override when room is warm (e.g., stove heating) to
reduce heat pump effort without full shutdown.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class PowerManager:
    def __init__(self, modbus_client, thermostat_api_url: str, scheduler=None):
        self.modbus_client = modbus_client
        self.thermostat_api_url = thermostat_api_url
        self.scheduler = scheduler  # Reference to scheduler for getting current active offset
        self.enabled = False
        self.sensor_sources = {}
        self.turn_off_when = {}
        self.turn_on_when = {}
        self.check_interval = 300

        # Offset override state (stove heating detection)
        self.offset_override_enabled = False
        self.offset_override_config = {}
        self.offset_override_active = False  # Track if override is currently in effect
        self.offset_override_check_interval = 60

        self.load_config()

    def load_config(self):
        """Load configuration from config.json"""
        try:
            config_file = Path("/app/config.json")
            with open(config_file) as f:
                full_config = json.load(f)

            # Power management config
            config = full_config.get('power_management', {})
            self.enabled = config.get('enabled', False)
            self.sensor_sources = config.get('sensor_sources', {
                'outdoor_temp': 'temp_odu',  # Default to heat pump ODU sensor
                'room_temp': 'temp_indoor'   # Default to Shelly indoor
            })
            self.turn_off_when = config.get('turn_off_when', {})
            self.turn_on_when = config.get('turn_on_when', {})
            self.check_interval = config.get('check_interval_seconds', 300)

            logger.info(f"Power manager: enabled={self.enabled}, sensors={self.sensor_sources}")

            # Offset override config (stove heating detection)
            offset_config = full_config.get('offset_override', {})
            self.offset_override_enabled = offset_config.get('enabled', False)
            self.offset_override_config = offset_config
            self.offset_override_check_interval = offset_config.get('check_interval_seconds', 60)

            if self.offset_override_enabled:
                override_threshold = offset_config.get('override_when', {}).get('room_temp_above_or_equal', 23.0)
                restore_threshold = offset_config.get('restore_when', {}).get('room_temp_below', 21.5)
                override_offset = offset_config.get('override_offset', -5)
                logger.info(f"Offset override: enabled, override at ≥{override_threshold}°C → offset={override_offset}, restore at <{restore_threshold}°C")

        except Exception as e:
            logger.error(f"Failed to load power manager config: {e}")
            self.enabled = False
            self.offset_override_enabled = False

    async def _get_temperature(self, sensor_source: str) -> float:
        """
        Get temperature from configured sensor source.

        Sensor sources:
        - temp_indoor: Shelly BLU indoor sensor (via thermostat API)
        - temp_outdoor: Shelly BLU outdoor sensor (via thermostat API)
        - temp_buffer: Shelly BLU buffer tank sensor (via thermostat API)
        - temp_odu: Heat pump outdoor unit sensor (via Modbus/status.json)

        Args:
            sensor_source: Sensor identifier (temp_indoor, temp_outdoor, temp_buffer, temp_odu)

        Returns:
            Temperature in °C, or None if sensor not available
        """
        try:
            # Heat pump ODU sensor from Modbus (status.json)
            if sensor_source == 'temp_odu':
                with open("/app/status.json") as f:
                    status = json.load(f)
                    return status.get('outdoor_temp')

            # Shelly BLU sensors from thermostat API
            elif sensor_source in ['temp_indoor', 'temp_outdoor', 'temp_buffer']:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{self.thermostat_api_url}/api/v1/thermostat/status")
                    resp.raise_for_status()
                    all_temps = resp.json().get('all_temps', {})
                    return all_temps.get(sensor_source)

            else:
                logger.error(f"Unknown sensor source: {sensor_source}")
                return None

        except Exception as e:
            logger.error(f"Error reading temperature from {sensor_source}: {e}")
            return None

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
                    'min_off_time': current_config.get('min_off_time', 20),
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
            # Get heat pump power state
            with open("/app/status.json") as f:
                status = json.load(f)
                is_on = status.get('power_state') == 'ON'

            # Get temperatures from configured sensor sources
            outdoor_source = self.sensor_sources.get('outdoor_temp', 'temp_odu')
            room_source = self.sensor_sources.get('room_temp', 'temp_indoor')

            outdoor_temp = await self._get_temperature(outdoor_source)
            room_temp = await self._get_temperature(room_source)

            if outdoor_temp is None or room_temp is None:
                logger.warning(f"Missing temperature data: outdoor={outdoor_temp} ({outdoor_source}), room={room_temp} ({room_source})")
                return

            # Turn OFF logic
            if is_on:
                outdoor_ok = outdoor_temp >= self.turn_off_when.get('outdoor_temp_above_or_equal', 999)
                room_ok = room_temp >= self.turn_off_when.get('room_temp_above_or_equal', 999)

                if outdoor_ok and room_ok:
                    logger.info(f"💡 Turning OFF: outdoor={outdoor_temp:.1f}°C ({outdoor_source}), room={room_temp:.1f}°C ({room_source})")

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
                    logger.info(f"💡 Turning ON: outdoor={outdoor_temp:.1f}°C ({outdoor_source}), room={room_temp:.1f}°C ({room_source})")

                    # Step 1: Turn on heat pump power
                    from lg_r290_modbus import set_power, set_lg_mode
                    await set_power(self.modbus_client, True)

                    # Step 2: Wait for heat pump to initialize after power on
                    await asyncio.sleep(5)

                    # Step 3: Set LG Auto mode (heat pump defaults to Heating mode after power cycle)
                    success = await set_lg_mode(self.modbus_client, 3)
                    if success:
                        logger.info("💡 LG Auto mode restored after power on")
                    else:
                        logger.error("💡 Failed to restore LG Auto mode after power on")

                    # Step 4: Restore scheduled offset
                    scheduled_offset = None
                    if self.scheduler:
                        scheduled_offset = self.scheduler.get_current_active_offset()
                    if scheduled_offset is not None:
                        await self._set_auto_mode_offset(scheduled_offset)
                        logger.info(f"💡 Scheduled offset restored: {scheduled_offset:+d}K")
                    else:
                        logger.info("💡 No active schedule, using default offset 0")
                        await self._set_auto_mode_offset(0)

                    # Step 5: Set thermostat mode to AUTO (enables automatic pump control)
                    await self._set_thermostat_mode("AUTO")

        except Exception as e:
            logger.error(f"Power manager error: {e}")

    async def _set_auto_mode_offset(self, offset: int) -> bool:
        """
        Set LG Auto mode offset via heat pump API.

        Args:
            offset: Offset value (-5 to +5)

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:8000/auto-mode-offset",
                    json={'offset': offset}
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to set auto mode offset to {offset}: {e}")
            return False

    async def check_offset_override(self):
        """
        Check room temperature and apply/restore offset override.

        When room is warm (e.g., stove heating), sets offset to minimum (-5)
        to reduce heat pump effort. When room cools down, restores scheduled offset.
        """
        if not self.offset_override_enabled:
            return

        try:
            # Get heat pump power state - no point in offset control if power is off
            with open("/app/status.json") as f:
                status = json.load(f)
                is_on = status.get('power_state') == 'ON'

            if not is_on:
                # Power is off, reset override state (will be re-evaluated when power comes on)
                if self.offset_override_active:
                    logger.info("🔥 Offset override: Power is OFF, clearing override state")
                    self.offset_override_active = False
                return

            # Get room temperature
            sensor_source = self.offset_override_config.get('sensor_source', 'temp_indoor')
            room_temp = await self._get_temperature(sensor_source)

            if room_temp is None:
                logger.warning(f"Offset override: Missing room temperature from {sensor_source}")
                return

            # Get thresholds
            override_threshold = self.offset_override_config.get('override_when', {}).get('room_temp_above_or_equal', 23.0)
            restore_threshold = self.offset_override_config.get('restore_when', {}).get('room_temp_below', 21.5)
            override_offset = self.offset_override_config.get('override_offset', -5)

            # Check if we should activate override
            if not self.offset_override_active and room_temp >= override_threshold:
                logger.info(f"🔥 Stove detected: room={room_temp:.1f}°C ≥ {override_threshold}°C → Setting offset to {override_offset}")
                success = await self._set_auto_mode_offset(override_offset)
                if success:
                    self.offset_override_active = True
                    logger.info(f"🔥 Offset override ACTIVATED (offset={override_offset})")

            # Check if we should deactivate override and restore scheduled offset
            elif self.offset_override_active and room_temp < restore_threshold:
                logger.info(f"🔥 Stove off: room={room_temp:.1f}°C < {restore_threshold}°C → Restoring scheduled offset")

                # Get current scheduled offset from scheduler
                scheduled_offset = None
                if self.scheduler:
                    scheduled_offset = self.scheduler.get_current_active_offset()

                if scheduled_offset is not None:
                    success = await self._set_auto_mode_offset(scheduled_offset)
                    if success:
                        self.offset_override_active = False
                        logger.info(f"🔥 Offset override DEACTIVATED, restored scheduled offset={scheduled_offset:+d}")
                else:
                    # No schedule active, use default offset (0)
                    success = await self._set_auto_mode_offset(0)
                    if success:
                        self.offset_override_active = False
                        logger.info(f"🔥 Offset override DEACTIVATED, restored default offset=0 (no active schedule)")

        except Exception as e:
            logger.error(f"Offset override error: {e}")

    async def run(self):
        """Background task - runs both power management and offset override checks"""
        logger.info("Power manager started")

        power_check_counter = 0
        # Calculate how many offset checks per power check
        power_check_ratio = max(1, self.check_interval // self.offset_override_check_interval)

        while True:
            # Always check offset override (runs every offset_override_check_interval)
            await self.check_offset_override()

            # Check power management less frequently
            power_check_counter += 1
            if power_check_counter >= power_check_ratio:
                await self.check_and_control()
                power_check_counter = 0

            await asyncio.sleep(self.offset_override_check_interval)
