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
POLL_INTERVAL = 30

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to stdout for Docker logs
    ]
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
    mode_str = ODU_MODES.get(status['operating_mode'], f"Unknown ({status['operating_mode']})")

    return (
        f"[{status['power_state']:3s}] {mode_str:8s} | "
        f"Target: {status['target_temp']:4.1f}°C | "
        f"Flow: {status['flow_temp']:5.1f}°C | "
        f"Return: {status['return_temp']:5.1f}°C | "
        f"ODU: {status['outdoor_temp']:5.1f}°C | "
        f"Error: {status['error_code']}"
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
                    # Failed to read
                    consecutive_errors += 1
                    logger.warning(
                        f"Failed to read registers "
                        f"({consecutive_errors}/{max_consecutive_errors})"
                    )

                    # Too many consecutive errors - try reconnecting
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive errors - attempting reconnect")
                        client.close()
                        await asyncio.sleep(2)

                        client = await connect_gateway()
                        if client:
                            logger.info("✅ Reconnected successfully")
                            consecutive_errors = 0
                        else:
                            logger.error("❌ Reconnection failed - will retry next cycle")

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in polling cycle: {e}", exc_info=True)

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
        logger.error(f"Fatal error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(0)
