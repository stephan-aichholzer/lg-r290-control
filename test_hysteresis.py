#!/usr/bin/env python3
"""
Test script to demonstrate hysteresis behavior for outdoor temperature cutoff/restart.

This shows how the heat pump will behave with the new hysteresis logic:
- Cutoff: 16°C (turn OFF when outdoor >= 16°C while ON)
- Restart: 15°C (turn ON only when outdoor <= 15°C while OFF)
"""

import sys
sys.path.insert(0, 'service')

from heating_curve import HeatingCurveConfig

def test_hysteresis():
    """Simulate heat pump behavior across temperature range."""

    config = HeatingCurveConfig("service/heating_curve_config.json")
    target_room_temp = 22.0  # Comfort mode

    print("=" * 80)
    print("HYSTERESIS TEST: Outdoor Temperature Cutoff/Restart")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  - Cutoff temperature: 16°C (turn OFF when outdoor >= 16°C)")
    print(f"  - Restart temperature: 15°C (turn ON when outdoor <= 15°C)")
    print(f"  - Target room temperature: {target_room_temp}°C")
    print("=" * 80)
    print()

    # Test scenario 1: Heat pump ON, temperature rising
    print("SCENARIO 1: Heat pump ON, outdoor temperature RISING")
    print("-" * 80)
    current_power = True
    for outdoor_temp in [14.0, 15.0, 15.5, 15.9, 16.0, 16.5, 17.0]:
        flow_temp = config.calculate_flow_temp(outdoor_temp, target_room_temp, current_power)
        if flow_temp is None:
            print(f"  Outdoor: {outdoor_temp:4.1f}°C | Power: ON  → Should turn OFF")
            current_power = False
        else:
            print(f"  Outdoor: {outdoor_temp:4.1f}°C | Power: ON  → Flow: {flow_temp:.0f}°C")

    print()

    # Test scenario 2: Heat pump OFF, temperature falling
    print("SCENARIO 2: Heat pump OFF, outdoor temperature FALLING")
    print("-" * 80)
    current_power = False
    for outdoor_temp in [17.0, 16.5, 16.0, 15.5, 15.0, 14.5, 14.0]:
        flow_temp = config.calculate_flow_temp(outdoor_temp, target_room_temp, current_power)
        if flow_temp is None:
            print(f"  Outdoor: {outdoor_temp:4.1f}°C | Power: OFF → Stays OFF (hysteresis)")
        else:
            print(f"  Outdoor: {outdoor_temp:4.1f}°C | Power: OFF → Should turn ON, Flow: {flow_temp:.0f}°C")
            current_power = True

    print()
    print("=" * 80)
    print("KEY OBSERVATIONS:")
    print("=" * 80)
    print("1. When ON:  Turns OFF at 16.0°C (cutoff)")
    print("2. When OFF: Stays OFF until 15.0°C, then turns ON (restart)")
    print("3. Hysteresis prevents rapid ON/OFF cycling around 15.5-16.0°C")
    print("=" * 80)

if __name__ == "__main__":
    test_hysteresis()
