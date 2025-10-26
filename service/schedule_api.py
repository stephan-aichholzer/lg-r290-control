"""
Schedule API Module

Provides all schedule-related REST API endpoints:
- GET /schedule - Get scheduler status (metadata only)
- POST /schedule/reload - Reload schedule from file
- GET /schedule/config - Get full schedule configuration
- POST /schedule/config - Update full schedule configuration

Separated from main.py to keep the codebase modular and maintainable.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create API router for all schedule endpoints
router = APIRouter(prefix="/schedule", tags=["Scheduler"])

# Module-level reference to scheduler instance (set by main.py)
_scheduler_instance: Optional[object] = None
_scheduler_enabled: bool = True


def set_scheduler_instance(scheduler: object, enabled: bool = True):
    """
    Set the scheduler instance for this module.

    Called by main.py during application startup.

    Args:
        scheduler: Scheduler instance
        enabled: Whether scheduler feature is enabled
    """
    global _scheduler_instance, _scheduler_enabled
    _scheduler_instance = scheduler
    _scheduler_enabled = enabled
    logger.info(f"Schedule API module initialized (enabled={enabled})")


# ============================================================================
# Pydantic Models
# ============================================================================

class SchedulePeriod(BaseModel):
    """Single time period within a schedule."""
    time: str = Field(
        description="Time in HH:MM format (24-hour)",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        examples=["05:00", "17:30", "22:00"]
    )
    target_temp: float = Field(
        description="Target room temperature in °C",
        ge=10.0,
        le=30.0,
        examples=[21.0, 22.0, 23.5]
    )
    auto_offset: int = Field(
        default=0,
        description="LG Auto mode offset adjustment in K",
        ge=-5,
        le=5,
        examples=[-2, 0, 2, 3]
    )


class SchedulePattern(BaseModel):
    """Schedule pattern for specific days of the week."""
    days: List[str] = Field(
        description="Days of week (lowercase: monday, tuesday, ...)",
        min_length=1,
        examples=[
            ["monday", "tuesday", "wednesday", "thursday", "friday"],
            ["saturday", "sunday"]
        ]
    )
    periods: List[SchedulePeriod] = Field(
        description="Time periods with temperature and offset settings",
        min_length=1
    )


class ScheduleConfiguration(BaseModel):
    """Complete schedule configuration (1:1 mapping to schedule.json)."""
    enabled: bool = Field(
        description="Enable/disable scheduler",
        examples=[True, False]
    )
    schedules: List[SchedulePattern] = Field(
        description="List of schedule patterns with days and time periods",
        examples=[[
            {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "periods": [
                    {"time": "05:00", "target_temp": 22.0, "auto_offset": 3},
                    {"time": "09:00", "target_temp": 21.8, "auto_offset": 1}
                ]
            }
        ]]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "enabled": True,
                "schedules": [
                    {
                        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                        "periods": [
                            {"time": "05:00", "target_temp": 22.0, "auto_offset": 3},
                            {"time": "09:00", "target_temp": 21.8, "auto_offset": 1},
                            {"time": "17:00", "target_temp": 22.0, "auto_offset": 2},
                            {"time": "22:00", "target_temp": 21.5, "auto_offset": -2}
                        ]
                    },
                    {
                        "days": ["saturday", "sunday"],
                        "periods": [
                            {"time": "06:00", "target_temp": 22.0, "auto_offset": 3},
                            {"time": "10:00", "target_temp": 21.8, "auto_offset": 1},
                            {"time": "17:00", "target_temp": 22.0, "auto_offset": 2},
                            {"time": "23:00", "target_temp": 21.5, "auto_offset": -2}
                        ]
                    }
                ]
            }]
        }
    }


# ============================================================================
# Configuration File Access
# ============================================================================

SCHEDULE_FILE = Path("/app/schedule.json")

# Valid day names (lowercase)
VALID_DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def validate_schedule_configuration(config: ScheduleConfiguration) -> None:
    """
    Validate schedule configuration structure and values.

    Raises HTTPException with detailed error message if validation fails.
    """
    for idx, schedule in enumerate(config.schedules):
        # Validate days
        for day in schedule.days:
            if day.lower() not in VALID_DAYS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Schedule {idx}: Invalid day '{day}'. Must be one of: {', '.join(VALID_DAYS)}"
                )

        # Validate periods
        for period_idx, period in enumerate(schedule.periods):
            # Validate time format (HH:MM)
            try:
                datetime.strptime(period.time, '%H:%M')
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Schedule {idx}, period {period_idx}: Invalid time format '{period.time}' (expected HH:MM, e.g., '05:00')"
                )

            # Warn about unusual temperatures (but don't reject)
            if period.target_temp < 18.0 or period.target_temp > 24.0:
                logger.warning(
                    f"Schedule {idx}, period {period_idx}: target_temp {period.target_temp}°C "
                    f"is outside typical range (18-24°C)"
                )


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "",
    summary="Get Scheduler Status",
    description="""
    Get scheduler **status and metadata** (not the full schedule configuration).

    **Returns**:
    - `enabled`: Scheduler state
    - `schedule_count`: Number of schedule patterns loaded
    - `current_time`: Current system time with timezone
    - `current_day`: Current day of week
    - `timezone`: System timezone
    - `next_check`: Last check time (hour, minute)

    **Note**: This does NOT return the actual schedule configuration (times, temperatures).
    To view the full schedule configuration, use `GET /schedule/config` instead.

    **Use Case**: Monitoring, debugging, verify scheduler is running.

    **Example Response**:
    ```json
    {
      "enabled": true,
      "schedule_count": 2,
      "current_time": "2025-10-26 19:44:15",
      "current_day": "Sunday",
      "timezone": "CET",
      "next_check": [19, 43]
    }
    ```
    """
)
async def get_schedule_status():
    """Get current scheduler status (metadata only)."""
    if not _scheduler_enabled:
        return {
            "enabled": False,
            "message": "Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
        }

    if not _scheduler_instance:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        status = _scheduler_instance.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/reload",
    summary="Reload Schedule Configuration",
    description="""
    Hot-reload schedule configuration from `schedule.json` without restarting the service.

    **Use Case**: Update schedule times or temperature setpoints without downtime.

    **Configuration File**: `service/schedule.json`

    **Effect**: Reloads schedule from disk into memory

    **Returns**:
    - `success`: Whether reload succeeded
    - `enabled`: Scheduler enabled state from config
    - `schedule_count`: Number of schedule patterns loaded
    - `message`: Status message

    **Example Response**:
    ```json
    {
      "success": true,
      "enabled": true,
      "schedule_count": 2,
      "message": "Schedule reloaded successfully"
    }
    ```
    """
)
async def reload_schedule_config():
    """Reload schedule configuration without restarting service."""
    if not _scheduler_enabled:
        raise HTTPException(
            status_code=503,
            detail="Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
        )

    if not _scheduler_instance:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    try:
        result = _scheduler_instance.reload_schedule()
        logger.info(
            f"Schedule configuration reloaded via API "
            f"(enabled: {result.get('enabled')}, schedules: {result.get('schedule_count')})"
        )
        return result
    except Exception as e:
        logger.error(f"Error reloading schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/config",
    response_model=ScheduleConfiguration,
    summary="Get Schedule Configuration",
    description="""
    Get the complete schedule configuration (1:1 mapping to schedule.json).

    **Returns**:
    - `enabled`: Scheduler enabled state
    - `schedules`: Array of schedule patterns
      - `days`: Array of day names (lowercase: monday, tuesday, ...)
      - `periods`: Array of time periods
        - `time`: Time in HH:MM format (24-hour)
        - `target_temp`: Target room temperature in °C
        - `auto_offset`: LG Auto mode offset adjustment (-5 to +5K)

    **Use Case**: Display current schedule in UI, backup configuration, debugging.

    **Note**: This returns the full schedule configuration. For just status info
    (enabled, count, current time), use `GET /schedule` instead.

    **Example Response**:
    ```json
    {
      "enabled": true,
      "schedules": [
        {
          "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
          "periods": [
            {"time": "05:00", "target_temp": 22.0, "auto_offset": 3},
            {"time": "09:00", "target_temp": 21.8, "auto_offset": 1}
          ]
        }
      ]
    }
    ```
    """
)
async def get_schedule_config():
    """Get complete schedule configuration from schedule.json."""
    if not SCHEDULE_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="Schedule configuration file not found"
        )

    try:
        with open(SCHEDULE_FILE, 'r') as f:
            config = json.load(f)

        # Validate that it matches our schema
        validated_config = ScheduleConfiguration(**config)

        return validated_config

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schedule.json: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in schedule file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error reading schedule config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/config",
    response_model=ScheduleConfiguration,
    summary="Update Schedule Configuration",
    description="""
    Update the schedule configuration and automatically reload the scheduler.

    **Method**: POST (not PUT) - posts the entire configuration

    **Request Body**: Complete schedule configuration (same format as schedule.json)

    **Validation**:
    - Days must be valid weekday names (monday-sunday, lowercase)
    - Time must be in HH:MM format (24-hour)
    - target_temp must be between 10.0-30.0°C (typical range: 18-24°C)
    - auto_offset must be integer -5 to +5

    **Effect**:
    - Writes to schedule.json file (persisted across restarts)
    - Automatically reloads scheduler (no service restart needed)
    - Changes take effect within 60 seconds (next scheduler check)

    **Returns**: The updated configuration (same as GET /schedule/config)

    **Security**: No authentication required (trusted LAN only)

    **Example Request**:
    ```bash
    curl -X POST http://localhost:8002/schedule/config \\
      -H "Content-Type: application/json" \\
      -d '{
        "enabled": true,
        "schedules": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "periods": [
              {"time": "06:00", "target_temp": 21.0, "auto_offset": 2},
              {"time": "22:00", "target_temp": 20.0, "auto_offset": -1}
            ]
          }
        ]
      }'
    ```
    """,
    responses={
        200: {
            "description": "Schedule configuration updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "enabled": True,
                        "schedules": [
                            {
                                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                                "periods": [
                                    {"time": "06:00", "target_temp": 21.0, "auto_offset": 2}
                                ]
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Validation error (invalid days, times, or values)"},
        500: {"description": "Failed to write configuration or reload scheduler"},
        503: {"description": "Scheduler not initialized or disabled"}
    }
)
async def update_schedule_config(config: ScheduleConfiguration):
    """
    Update schedule configuration and reload scheduler.

    Args:
        config: New schedule configuration
    """
    if not _scheduler_enabled:
        raise HTTPException(
            status_code=503,
            detail="Scheduler feature is disabled (ENABLE_SCHEDULER=False)"
        )

    # Validate configuration
    validate_schedule_configuration(config)

    try:
        # Convert to dict for JSON serialization
        config_dict = config.model_dump()

        # Write to file with pretty formatting
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(
            f"✓ Schedule configuration updated: enabled={config.enabled}, "
            f"{len(config.schedules)} schedule(s)"
        )

        # Automatically reload scheduler if instance provided
        if _scheduler_instance:
            reload_result = _scheduler_instance.reload_schedule()

            if not reload_result.get('success'):
                logger.error(
                    f"Failed to reload scheduler after config update: "
                    f"{reload_result.get('message')}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Configuration saved but reload failed: {reload_result.get('message')}"
                )

            logger.info("✓ Scheduler reloaded successfully after config update")
        else:
            logger.warning("Scheduler instance not provided - skipping automatic reload")

        # Return the updated configuration
        return config_dict

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"Error updating schedule config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Utility Functions (for potential future use)
# ============================================================================

def backup_schedule_config() -> Path:
    """
    Create a backup of the current schedule configuration.

    Returns:
        Path to backup file
    """
    if not SCHEDULE_FILE.exists():
        raise FileNotFoundError("Schedule file does not exist")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = SCHEDULE_FILE.parent / f"schedule.json.backup_{timestamp}"

    with open(SCHEDULE_FILE, 'r') as src:
        with open(backup_file, 'w') as dst:
            dst.write(src.read())

    logger.info(f"Schedule configuration backed up to {backup_file}")
    return backup_file


def restore_schedule_config(backup_file: Path) -> bool:
    """
    Restore schedule configuration from backup.

    Args:
        backup_file: Path to backup file

    Returns:
        True if restore successful, False otherwise
    """
    try:
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False

        # Validate backup file before restoring
        with open(backup_file, 'r') as f:
            config = json.load(f)

        ScheduleConfiguration(**config)  # Validate schema

        # Copy backup to main file
        with open(backup_file, 'r') as src:
            with open(SCHEDULE_FILE, 'w') as dst:
                dst.write(src.read())

        logger.info(f"Schedule configuration restored from {backup_file}")
        return True

    except Exception as e:
        logger.error(f"Failed to restore schedule config: {e}")
        return False
