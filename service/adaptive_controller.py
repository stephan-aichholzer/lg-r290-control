"""
Adaptive Heating Controller - AI Mode for automatic flow temperature adjustment
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
import httpx

from heating_curve import get_heating_curve_config, HeatingCurveConfig
from modbus_client import HeatPumpModbusClient

logger = logging.getLogger(__name__)


class AdaptiveController:
    """
    Adaptive heating controller that automatically adjusts flow temperature
    based on outdoor temperature and target room temperature using heating curves.
    """

    def __init__(
        self,
        modbus_client: HeatPumpModbusClient,
        thermostat_api_url: str = "http://192.168.2.11:8001"
    ):
        """
        Initialize adaptive controller.

        Args:
            modbus_client: Heat pump Modbus client instance
            thermostat_api_url: Base URL for thermostat API
        """
        self.modbus_client = modbus_client
        self.thermostat_api_url = thermostat_api_url.rstrip('/')

        # Load heating curve configuration
        self.heating_curve: HeatingCurveConfig = get_heating_curve_config(
            "heating_curve_config.json"
        )

        # AI Mode state - enabled by default for deterministic heating curve control
        self.enabled = True
        self.last_update: Optional[datetime] = None
        self.last_outdoor_temp: Optional[float] = None
        self.last_target_room_temp: Optional[float] = None
        self.last_calculated_flow_temp: Optional[float] = None

        # Control loop task
        self._control_task: Optional[asyncio.Task] = None

        # Settings from config
        self.update_interval = self.heating_curve.get_settings()['update_interval_seconds']
        self.adjustment_threshold = self.heating_curve.get_settings()['adjustment_threshold']

    def start(self):
        """Start the adaptive control loop."""
        if self._control_task is None or self._control_task.done():
            self._control_task = asyncio.create_task(self._control_loop())
            logger.info(f"Adaptive controller started (AI Mode: {'enabled' if self.enabled else 'disabled'} by default)")

    def stop(self):
        """Stop the adaptive control loop."""
        if self._control_task and not self._control_task.done():
            self._control_task.cancel()
            logger.info("Adaptive controller stopped")

    async def _control_loop(self):
        """Background task - runs periodically when AI mode is enabled."""
        while True:
            try:
                if self.enabled:
                    await self._adjust_flow_temperature()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                logger.info("Adaptive control loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in adaptive control loop: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)

    async def _adjust_flow_temperature(self):
        """
        Main control logic:
        1. Read outdoor temperature from heat pump
        2. Read target room temperature from thermostat
        3. Calculate optimal flow temperature
        4. Adjust heat pump if needed
        """
        try:
            # Get current temperatures
            outdoor_temp = await self._get_outdoor_temperature()
            target_room_temp = await self._get_target_room_temperature()

            if outdoor_temp is None or target_room_temp is None:
                logger.warning(
                    f"Cannot adjust: outdoor_temp={outdoor_temp}, "
                    f"target_room_temp={target_room_temp}"
                )
                return

            # Store for status reporting
            self.last_outdoor_temp = outdoor_temp
            self.last_target_room_temp = target_room_temp

            # Get current heat pump status (needed for hysteresis logic)
            status = self.modbus_client.get_cached_status()
            current_power = status.get('is_on', False)
            current_setpoint = status.get('target_temperature', 0.0)

            # Calculate optimal flow temperature with hysteresis
            optimal_flow_temp = self.heating_curve.calculate_flow_temp(
                outdoor_temp,
                target_room_temp,
                current_power
            )

            self.last_calculated_flow_temp = optimal_flow_temp
            self.last_update = datetime.now()

            # Check if heat pump should be turned off (or stay off)
            if optimal_flow_temp is None:
                if current_power:
                    logger.info(
                        f"AI Mode: Outdoor temp {outdoor_temp:.1f}°C - Turning heat pump OFF"
                    )
                    await self.modbus_client.set_power(False)
                return

            # Check if adjustment is needed
            temp_diff = abs(current_setpoint - optimal_flow_temp)

            if temp_diff >= self.adjustment_threshold:
                # Ensure heat pump is on
                if not current_power:
                    logger.info("AI Mode: Turning heat pump ON")
                    await self.modbus_client.set_power(True)
                    await asyncio.sleep(2)  # Wait for power on

                # Adjust setpoint
                success = await self.modbus_client.set_target_temperature(optimal_flow_temp)

                if success:
                    logger.info(
                        f"AI Mode: Adjusted flow temperature "
                        f"{current_setpoint:.1f}°C → {optimal_flow_temp:.1f}°C "
                        f"(outdoor: {outdoor_temp:.1f}°C, target room: {target_room_temp:.1f}°C)"
                    )
                else:
                    logger.error("AI Mode: Failed to adjust flow temperature")
            else:
                logger.debug(
                    f"AI Mode: No adjustment needed "
                    f"(current: {current_setpoint:.1f}°C, optimal: {optimal_flow_temp:.1f}°C, "
                    f"diff: {temp_diff:.1f}°C < threshold: {self.adjustment_threshold}°C)"
                )

        except Exception as e:
            logger.error(f"Error adjusting flow temperature: {e}", exc_info=True)

    async def _get_outdoor_temperature(self) -> Optional[float]:
        """Get outdoor temperature from thermostat API (Shelly sensor) with heat pump fallback."""
        try:
            # Primary source: Thermostat API (Shelly outdoor sensor)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.thermostat_api_url}/api/v1/thermostat/status"
                )
                response.raise_for_status()
                data = response.json()

                # Extract outdoor temperature from all_temps
                outdoor_temp = data.get('all_temps', {}).get('temp_outdoor')

                if outdoor_temp is not None:
                    logger.debug(f"Outdoor temperature from Shelly sensor: {outdoor_temp}°C")
                    return float(outdoor_temp)

                logger.warning("Outdoor temperature not found in thermostat response")

        except httpx.HTTPError as e:
            logger.warning(f"Thermostat API not accessible for outdoor temp: {e}")
        except Exception as e:
            logger.warning(f"Error getting outdoor temperature from thermostat: {e}")

        # Fallback: Try heat pump outdoor sensor
        try:
            status = self.modbus_client.get_cached_status()
            outdoor_temp = status.get('outdoor_temperature')

            if outdoor_temp is not None and outdoor_temp != 0.0:
                logger.info(f"Using heat pump outdoor temperature (fallback): {outdoor_temp}°C")
                return outdoor_temp

            logger.warning("Outdoor temperature not available from any source")
            return None

        except Exception as e:
            logger.error(f"Error getting outdoor temperature from heat pump: {e}")
            return None

    async def _get_target_room_temperature(self) -> Optional[float]:
        """Get target room temperature from thermostat API with fallback to default."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.thermostat_api_url}/api/v1/thermostat/status"
                )
                response.raise_for_status()
                data = response.json()

                # Extract target temperature from config
                target_temp = data.get('config', {}).get('target_temp')

                if target_temp is not None:
                    logger.debug(f"Target room temperature from thermostat: {target_temp}°C")
                    return float(target_temp)

                logger.warning("Target temperature not found in thermostat response")

        except httpx.HTTPError as e:
            logger.warning(f"Thermostat API not accessible: {e}")
        except Exception as e:
            logger.warning(f"Error getting target room temperature: {e}")

        # Fallback to default from configuration
        default_temp = self.heating_curve.get_settings().get('default_target_room_temp', 21)
        logger.info(f"Using default target room temperature: {default_temp}°C (thermostat not available)")
        return float(default_temp)

    def get_status(self) -> dict:
        """Get current AI mode status."""
        curve_info = None
        if self.last_target_room_temp is not None:
            curve_info = self.heating_curve.get_curve_info(self.last_target_room_temp)

        return {
            'enabled': self.enabled,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'outdoor_temperature': self.last_outdoor_temp,
            'target_room_temperature': self.last_target_room_temp,
            'calculated_flow_temperature': self.last_calculated_flow_temp,
            'heating_curve': curve_info,
            'update_interval_seconds': self.update_interval,
            'adjustment_threshold': self.adjustment_threshold
        }

    def reload_config(self):
        """Reload heating curve configuration."""
        changed = self.heating_curve.reload_config()

        # Update settings from new config
        settings = self.heating_curve.get_settings()
        self.update_interval = settings['update_interval_seconds']
        self.adjustment_threshold = settings['adjustment_threshold']

        logger.info(
            f"Configuration reloaded (changed: {changed}) - "
            f"interval: {self.update_interval}s, threshold: {self.adjustment_threshold}°C"
        )

        return changed
