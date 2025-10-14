#!/bin/bash
# Docker healthcheck script
# Verifies monitor daemon is alive by checking status.json timestamp

STATUS_FILE="/app/status.json"
MAX_AGE=60  # Allow up to 60 seconds for errors/retries

# Check if status.json exists (should always exist - created at startup)
if [ ! -f "$STATUS_FILE" ]; then
    echo "UNHEALTHY: status.json missing (should be created at startup)"
    exit 1
fi

# Check file age (monitor daemon updates every 10s)
FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$STATUS_FILE") ))

if [ $FILE_AGE -gt $MAX_AGE ]; then
    echo "UNHEALTHY: status.json stale (${FILE_AGE}s old, max ${MAX_AGE}s) - monitor daemon crashed"
    exit 1
fi

# Healthy
echo "HEALTHY: status.json fresh (${FILE_AGE}s old)"
exit 0
