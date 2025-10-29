#!/usr/bin/env python3
"""
LG Therma V R290 - Monitor and Keep-Alive Daemon

This script serves two purposes:
1. Maintains external control by polling every 10 seconds
2. Caches heat pump status to JSON file for fast API access

Without continuous polling, the heat pump shuts down within ~60 seconds as a safety feature.

The cached status file reduces Modbus traffic - other components (FastAPI, scripts)
read from the cache instead of querying Modbus directly.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from lg_r290_modbus import connect_gateway, read_all_registers

# ============================================================================
# Configuration
# ============================================================================

# Polling interval (seconds) - maintains external control
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '30'))

# Status cache file location
STATUS_FILE = Path("/app/status.json") if Path("/app").exists() else Path("status.json")

# Operating modes for display
ODU_MODES = {
    0: "Standby",
    1: "Cooling",
    2: "Heating",
    3: "Auto"
}

# ============================================================================
# Logging Configuration
# ============================================================================

from logging.handlers import RotatingFileHandler

# Suppress noisy pymodbus and asyncio errors from our logs
logging.getLogger('pymodbus').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)

# Main logger - clean monitoring data only
monitor_handler = RotatingFileHandler(
    '/app/monitor.log',
    maxBytes=1_000_000,  # 1MB ≈ 30 hours of logs
    backupCount=0        # No backup files, just truncate when full
)
monitor_handler.setLevel(logging.INFO)
monitor_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Error logger - exceptions and warnings
error_handler = RotatingFileHandler(
    '/app/error.log',
    maxBytes=1_000_000,  # 1MB
    backupCount=0        # No backup files
)
error_handler.setLevel(logging.WARNING)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[monitor_handler, error_handler]
)

logger = logging.getLogger(__name__)

# ============================================================================
# Status Cache Management
# ============================================================================

def write_status_to_file(status: dict, file_path: Path):
    """
    Write status to JSON file atomically.

    Uses atomic write (write to temp, then rename) to ensure
    readers never see partial/corrupted data.
    """
    try:
        # Add timestamp
        status['timestamp'] = datetime.now().isoformat()

        # Write to temporary file first
        temp_file = file_path.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(status, f, indent=2)

        # Atomic rename
        temp_file.rename(file_path)

        logger.debug(f"Status written to {file_path}")

    except Exception as e:
        logger.error(f"Error writing status file: {e}")


def format_status_line(status: dict) -> str:
    """Format status for console logging"""
    # Actual operating cycle (INPUT 30002)
    cycle_str = ODU_MODES.get(status['operating_mode'], f"Unknown ({status['operating_mode']})")

    # User-selected mode (HOLDING 40001)
    user_modes = {0: "Cool", 3: "Auto", 4: "Heat"}
    user_mode = user_modes.get(status['op_mode'], f"M{status['op_mode']}")

    # Auto mode offset (HOLDING 40005) - only relevant in Auto mode
    offset = status.get('auto_mode_offset', 0)
    offset_str = f"{offset:+d}K" if status['op_mode'] == 3 and offset != 0 else ""

    # Calculate delta (flow - return temperature) - handle missing values
    flow = status.get('flow_temp')
    return_temp = status.get('return_temp')

    if flow is not None and return_temp is not None:
        delta = flow - return_temp
        delta_str = f"{delta:+5.1f}°C"
        flow_str = f"{flow:5.1f}°C"
        return_str = f"{return_temp:5.1f}°C"
    else:
        delta_str = "   N/A  "
        flow_str = "  N/A°C"
        return_str = "  N/A°C"

    # Flow rate - handle missing value
    flow_rate = status.get('flow_rate')
    if flow_rate is not None:
        flow_rate_str = f"{flow_rate:4.1f}L"
    else:
        flow_rate_str = " N/A"

    return (
        f"[{status['power_state']:3s}] {cycle_str:8s}({user_mode:4s}{offset_str:4s}) | "
        f"Target: {status.get('target_temp', 0):4.1f}°C | "
        f"Flow: {flow_str} | "
        f"Return: {return_str} | "
        f"Delta: {delta_str} | "
        f"Rate: {flow_rate_str} | "
        f"ODU: {status.get('outdoor_temp', 0):5.1f}°C | "
        f"Error: {status.get('error_code', 0)}"
    )


# ============================================================================
# Main Monitoring Loop
# ============================================================================

async def monitoring_loop():
    """
    Main monitoring loop - runs continuously.

    - Polls heat pump every 10 seconds
    - Maintains external control mode
    - Caches status to JSON file
    - Logs status to console
    """
    logger.info("="*80)
    logger.info("LG Therma V R290 - Monitor and Keep-Alive Daemon")
    logger.info("="*80)
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
    logger.info(f"Status file: {STATUS_FILE}")
    logger.info("="*80)
    logger.info("")

    # Connect to gateway
    logger.info("Connecting to Modbus gateway...")
    client = await connect_gateway()

    if not client:
        logger.error("Failed to connect to gateway - exiting")
        return False

    logger.info("✅ Connected - starting continuous monitoring...")
    logger.info("")

    poll_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 5

    try:
        while True:
            poll_count += 1

            try:
                # Read all registers
                status = await read_all_registers(client)

                if status:
                    # Success - reset error counter
                    consecutive_errors = 0

                    # Write to cache file
                    write_status_to_file(status, STATUS_FILE)

                    # Log to console
                    status_line = format_status_line(status)
                    logger.info(f"[Poll #{poll_count:4d}] {status_line}")

                else:
                    # Failed to read - touch status file to prevent supervision timeout
                    STATUS_FILE.touch(exist_ok=True)

                    consecutive_errors += 1
                    logger.warning(
                        f"Failed to read registers "
                        f"({consecutive_errors}/{max_consecutive_errors})"
                    )

                    # Too many consecutive errors - try reconnecting
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive errors - attempting reconnect")
                        try:
                            client.close()
                        except Exception as close_err:
                            logger.debug(f"Error closing client: {close_err}")

                        await asyncio.sleep(2)

                        client = await connect_gateway()
                        if client:
                            logger.info("✅ Reconnected successfully")
                            consecutive_errors = 0
                        else:
                            logger.error("❌ Reconnection failed - will retry next cycle")

            except Exception as e:
                # Critical: Touch status file even on exception to prevent supervision timeout
                try:
                    STATUS_FILE.touch(exist_ok=True)
                except Exception as touch_err:
                    logger.critical(f"Cannot touch status file: {touch_err}")

                consecutive_errors += 1
                logger.error(f"Error in polling cycle (poll #{poll_count}): {e}", exc_info=True)

                # If we've lost the client connection, try to reconnect
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many exceptions - attempting full reconnect")
                    try:
                        if client:
                            client.close()
                    except Exception:
                        pass

                    client = await connect_gateway()
                    if client:
                        logger.info("✅ Reconnected after exceptions")
                        consecutive_errors = 0
                    else:
                        logger.error("❌ Reconnection failed after exceptions")

            # Wait for next poll interval
            await asyncio.sleep(POLL_INTERVAL)

    except asyncio.CancelledError:
        logger.info("Monitoring loop cancelled - shutting down")
    except KeyboardInterrupt:
        logger.info("Received interrupt - shutting down")
    finally:
        # Cleanup
        if client:
            client.close()
            logger.info("Modbus connection closed")

        logger.info("Monitoring daemon stopped")


# ============================================================================
# Entry Point
# ============================================================================

async def main():
    """Main entry point"""
    try:
        await monitoring_loop()
        return True
    except Exception as e:
        logger.critical(f"Fatal error - daemon crashed: {e}", exc_info=True)
        # Try to touch status file one last time before dying
        try:
            STATUS_FILE.touch(exist_ok=True)
        except Exception:
            pass
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(0)
