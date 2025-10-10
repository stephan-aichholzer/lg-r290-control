"""
Heating Curve Module - Adaptive flow temperature calculation based on outdoor temperature
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class HeatingCurveConfig:
    """Load and manage heating curve configuration"""

    def __init__(self, config_path: str = "heating_curve_config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()

    def load_config(self) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded heating curve config from {self.config_path}")
            self._validate_config(config)
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return self._get_default_config()
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            return self._get_default_config()

    def _validate_config(self, config: dict):
        """Validate configuration structure"""
        required_keys = ['heating_curves', 'settings']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key: {key}")

        # Validate heating curves
        required_curve_names = ['eco', 'comfort', 'high']
        for curve_name in required_curve_names:
            if curve_name not in config['heating_curves']:
                raise ValueError(f"Missing heating curve: {curve_name}")

        # Validate settings
        required_settings = [
            'outdoor_cutoff_temp', 'outdoor_restart_temp',
            'update_interval_seconds', 'min_flow_temp',
            'max_flow_temp', 'adjustment_threshold'
        ]
        for setting in required_settings:
            if setting not in config['settings']:
                raise ValueError(f"Missing setting: {setting}")

    def reload_config(self):
        """Hot-reload configuration without restarting service"""
        old_config = self.config
        self.config = self.load_config()
        logger.info("Configuration reloaded successfully")
        return self.config != old_config

    def _get_default_config(self) -> dict:
        """Return default configuration as fallback"""
        logger.warning("Using default heating curve configuration")
        return {
            "heating_curves": {
                "eco": {
                    "name": "ECO Mode (≤21°C)",
                    "target_temp_range": [0, 21.0],
                    "curve": [
                        {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 46.0},
                        {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 43.0},
                        {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 38.0},
                        {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 33.0}
                    ]
                },
                "comfort": {
                    "name": "Comfort Mode (21-23°C)",
                    "target_temp_range": [21.0, 23.0],
                    "curve": [
                        {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 48.0},
                        {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 45.0},
                        {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 40.0},
                        {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 35.0}
                    ]
                },
                "high": {
                    "name": "High Demand (>23°C)",
                    "target_temp_range": [23.0, 999],
                    "curve": [
                        {"outdoor_min": -999, "outdoor_max": -10, "flow_temp": 50.0},
                        {"outdoor_min": -10, "outdoor_max": 0, "flow_temp": 47.0},
                        {"outdoor_min": 0, "outdoor_max": 10, "flow_temp": 42.0},
                        {"outdoor_min": 10, "outdoor_max": 18, "flow_temp": 37.0}
                    ]
                }
            },
            "settings": {
                "outdoor_cutoff_temp": 18.0,
                "outdoor_restart_temp": 17.0,
                "update_interval_seconds": 600,
                "min_flow_temp": 30.0,
                "max_flow_temp": 50.0,
                "adjustment_threshold": 2.0,
                "hysteresis_outdoor": 1.0
            }
        }

    def calculate_flow_temp(
        self,
        outdoor_temp: float,
        target_room_temp: float
    ) -> Optional[float]:
        """
        Calculate optimal flow temperature based on heating curve

        Args:
            outdoor_temp: Current outdoor temperature in °C
            target_room_temp: Desired room temperature in °C

        Returns:
            Optimal flow temperature in °C, or None if heat pump should be OFF
        """
        settings = self.config['settings']

        # Check cutoff temperature with hysteresis
        if outdoor_temp >= settings['outdoor_cutoff_temp']:
            logger.info(
                f"Outdoor temp {outdoor_temp:.1f}°C >= cutoff "
                f"{settings['outdoor_cutoff_temp']}°C - Heat pump should be OFF"
            )
            return None

        # Select appropriate heating curve based on target room temperature
        selected_curve = self._select_heating_curve(target_room_temp)

        if not selected_curve:
            logger.warning(
                f"No heating curve found for target room temp {target_room_temp}°C"
            )
            return None

        logger.debug(
            f"Using heating curve: {selected_curve['name']} "
            f"(target: {target_room_temp}°C, outdoor: {outdoor_temp}°C)"
        )

        # Find matching outdoor temperature range in the curve
        flow_temp = self._find_flow_temp_from_curve(
            selected_curve['curve'],
            outdoor_temp
        )

        if flow_temp is None:
            logger.warning(
                f"No matching temperature range found for outdoor temp {outdoor_temp}°C"
            )
            return None

        # Apply safety limits
        original_temp = flow_temp
        flow_temp = max(
            settings['min_flow_temp'],
            min(settings['max_flow_temp'], flow_temp)
        )

        # Round to whole number (no decimals for flow temperature)
        flow_temp = round(flow_temp)

        if flow_temp != original_temp:
            logger.info(
                f"Flow temp adjusted from {original_temp}°C to {flow_temp}°C "
                f"(limits: {settings['min_flow_temp']}-{settings['max_flow_temp']}°C)"
            )

        return float(flow_temp)

    def _select_heating_curve(self, target_room_temp: float) -> Optional[Dict]:
        """Select the appropriate heating curve based on target room temperature"""
        curves = self.config['heating_curves']

        for curve_name, curve_data in curves.items():
            temp_min, temp_max = curve_data['target_temp_range']
            if temp_min <= target_room_temp <= temp_max:
                return curve_data

        return None

    def _find_flow_temp_from_curve(
        self,
        curve: list,
        outdoor_temp: float
    ) -> Optional[float]:
        """Find the flow temperature from curve based on outdoor temperature"""
        for point in curve:
            if point['outdoor_min'] <= outdoor_temp < point['outdoor_max']:
                return point['flow_temp']

        return None

    def get_curve_info(self, target_room_temp: float) -> Optional[Dict]:
        """Get information about which heating curve would be used"""
        selected_curve = self._select_heating_curve(target_room_temp)
        if selected_curve:
            return {
                'name': selected_curve['name'],
                'target_temp_range': selected_curve['target_temp_range']
            }
        return None

    def get_settings(self) -> Dict:
        """Get current settings"""
        return self.config['settings'].copy()


# Module-level instance for easy import
heating_curve_config = None


def get_heating_curve_config(config_path: str = "heating_curve_config.json") -> HeatingCurveConfig:
    """Get or create the heating curve configuration instance"""
    global heating_curve_config
    if heating_curve_config is None:
        heating_curve_config = HeatingCurveConfig(config_path)
    return heating_curve_config
