"""
Thermostat Schedule Manager

Manages time-based temperature schedules that call the thermostat API
to set mode=AUTO and target temperature at scheduled times.

Schedule only applies when thermostat is in AUTO or ON mode.
ECO and OFF modes are not affected by the schedule.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class Scheduler:
    """Manages thermostat scheduling based on time-based rules."""

    def __init__(self, thermostat_api_url: str, schedule_file: str = "schedule.json", heatpump_api_url: str = "http://localhost:8000"):
        """
        Initialize scheduler.

        Args:
            thermostat_api_url: Base URL for thermostat API
            schedule_file: Path to schedule configuration JSON file
            heatpump_api_url: Base URL for heat pump API (for auto_offset control)
        """
        self.thermostat_api_url = thermostat_api_url
        self.heatpump_api_url = heatpump_api_url
        self.schedule_file = Path(schedule_file)
        self.schedules = []
        self.enabled = False
        self.last_check_minute = None

        # Load schedule on initialization
        self.load_schedule()

    def load_schedule(self) -> None:
        """Load schedule from JSON file."""
        try:
            if not self.schedule_file.exists():
                logger.warning(f"Schedule file not found: {self.schedule_file}")
                self.enabled = False
                return

            with open(self.schedule_file, 'r') as f:
                data = json.load(f)

            self.enabled = data.get('enabled', False)
            self.schedules = data.get('schedules', [])

            logger.info(f"Schedule loaded: enabled={self.enabled}, {len(self.schedules)} schedule(s)")

            # Validate schedule format
            self._validate_schedules()

        except Exception as e:
            logger.error(f"Failed to load schedule: {e}")
            self.enabled = False
            self.schedules = []

    def _validate_schedules(self) -> None:
        """Validate schedule format and log warnings for invalid entries."""
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        for idx, schedule in enumerate(self.schedules):
            if 'days' not in schedule or 'periods' not in schedule:
                logger.warning(f"Schedule {idx}: Missing 'days' or 'periods' field")
                continue

            # Validate days
            for day in schedule['days']:
                if day.lower() not in valid_days:
                    logger.warning(f"Schedule {idx}: Invalid day '{day}'")

            # Validate periods
            for period_idx, period in enumerate(schedule['periods']):
                if 'time' not in period or 'target_temp' not in period:
                    logger.warning(f"Schedule {idx}, period {period_idx}: Missing 'time' or 'target_temp'")
                    continue

                # Validate time format (HH:MM)
                try:
                    datetime.strptime(period['time'], '%H:%M')
                except ValueError:
                    logger.warning(f"Schedule {idx}, period {period_idx}: Invalid time format '{period['time']}' (expected HH:MM)")

                # Validate auto_offset if present
                if 'auto_offset' in period:
                    offset = period['auto_offset']
                    if not isinstance(offset, int) or not -5 <= offset <= 5:
                        logger.warning(f"Schedule {idx}, period {period_idx}: Invalid auto_offset '{offset}' (must be integer -5 to +5)")

    def get_current_schedule_action(self) -> Optional[Dict]:
        """
        Check if current time matches a scheduled period.

        Returns:
            Dict with 'target_temp' and 'auto_offset' if current time matches a schedule, None otherwise
        """
        if not self.enabled:
            return None

        now = datetime.now()
        current_day = now.strftime('%A').lower()  # 'monday', 'tuesday', etc.
        current_time = now.strftime('%H:%M')  # '05:00', '09:00', etc.

        # Check all schedules for matching day and time
        for schedule in self.schedules:
            if current_day in schedule['days']:
                for period in schedule['periods']:
                    if period['time'] == current_time:
                        auto_offset = period.get('auto_offset', 0)
                        logger.info(f"Schedule match: {current_day} {current_time} → {period['target_temp']}°C, auto_offset: {auto_offset:+d}K")
                        return {
                            'target_temp': period['target_temp'],
                            'auto_offset': auto_offset,
                            'day': current_day,
                            'time': current_time
                        }

        return None

    async def apply_schedule_action(self, action: Dict) -> bool:
        """
        Apply scheduled action by calling thermostat API and heat pump API.

        Only applies if current mode is AUTO or ON.
        ECO and OFF modes are not affected.

        Args:
            action: Dict with 'target_temp' and 'auto_offset' to apply

        Returns:
            True if schedule was applied, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Step 1: Get current thermostat config to check mode
                response = await client.get(
                    f"{self.thermostat_api_url}/api/v1/thermostat/config"
                )
                response.raise_for_status()
                current_config = response.json()

                current_mode = current_config.get('mode', 'OFF')

                # Step 2: Check if mode allows schedule application
                if current_mode not in ['AUTO', 'ON']:
                    logger.info(f"Schedule skipped: current mode is {current_mode} (only AUTO/ON are affected)")
                    return False

                # Step 3: Build new config with mode=AUTO and scheduled target_temp
                new_config = {
                    'target_temp': action['target_temp'],
                    'eco_temp': current_config.get('eco_temp', 19.0),
                    'mode': 'AUTO',  # Force AUTO mode
                    'hysteresis': current_config.get('hysteresis', 0.1),
                    'min_on_time': current_config.get('min_on_time', 40),
                    'min_off_time': current_config.get('min_off_time', 20),
                    'temp_sample_count': current_config.get('temp_sample_count', 4),
                    'control_interval': current_config.get('control_interval', 60)
                }

                # Step 4: Apply new thermostat config
                response = await client.post(
                    f"{self.thermostat_api_url}/api/v1/thermostat/config",
                    json=new_config
                )
                response.raise_for_status()

                logger.info(
                    f"✓ Schedule applied: mode=AUTO, target_temp={action['target_temp']}°C "
                    f"(was mode={current_mode})"
                )

                # Step 5: Set LG Auto mode offset via heat pump API
                auto_offset = action.get('auto_offset', 0)
                logger.info(f"Setting LG Auto mode offset to {auto_offset:+d}K via heat pump API")

                response = await client.post(
                    f"{self.heatpump_api_url}/auto-mode-offset",
                    json={'offset': auto_offset}
                )
                response.raise_for_status()

                logger.info(f"✓ LG Auto mode offset set to {auto_offset:+d}K")
                return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to apply schedule action: HTTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to apply schedule action: {e}")
            return False

    async def check_and_apply(self) -> None:
        """Check current time and apply schedule if needed."""
        now = datetime.now()
        current_minute = (now.hour, now.minute)

        # Only check once per minute (avoid duplicate triggers)
        if current_minute == self.last_check_minute:
            return

        self.last_check_minute = current_minute
        logger.debug(f"Scheduler check: {now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%A')})")

        # Check if current time matches a scheduled action
        action = self.get_current_schedule_action()
        if action:
            logger.info(f"Schedule action triggered: {action}")
            await self.apply_schedule_action(action)
        else:
            logger.debug(f"No schedule match for {now.strftime('%A %H:%M')}")

    async def run(self) -> None:
        """
        Background task that checks schedule every 60 seconds.

        This should be started as an asyncio task in the main application.
        """
        logger.info("Scheduler started")

        while True:
            try:
                await self.check_and_apply()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Check every 60 seconds
            await asyncio.sleep(60)

    def reload_schedule(self) -> Dict:
        """
        Reload schedule from JSON file.

        Returns:
            Dict with reload status and current schedule info
        """
        try:
            self.load_schedule()
            return {
                'success': True,
                'enabled': self.enabled,
                'schedule_count': len(self.schedules),
                'message': 'Schedule reloaded successfully'
            }
        except Exception as e:
            logger.error(f"Failed to reload schedule: {e}")
            return {
                'success': False,
                'message': f'Failed to reload: {str(e)}'
            }

    def get_status(self) -> Dict:
        """
        Get current scheduler status.

        Returns:
            Dict with scheduler status information
        """
        now = datetime.now()
        return {
            'enabled': self.enabled,
            'schedule_count': len(self.schedules),
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'current_day': now.strftime('%A'),
            'timezone': now.astimezone().tzinfo.tzname(now),
            'next_check': self.last_check_minute
        }
