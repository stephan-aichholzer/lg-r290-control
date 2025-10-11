#!/bin/bash
# Watch Live Logs
# Real-time log monitoring with color highlighting

set -e

CONTAINER="lg_r290_service"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  LIVE LOG MONITOR"
echo "  Press Ctrl+C to exit"
echo "=========================================="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container ${CONTAINER} is not running"
    exit 1
fi

# Parse command line argument
MODE="${1:-all}"

case "$MODE" in
    scheduler|sched)
        echo "📅 Watching SCHEDULER logs..."
        echo ""
        docker logs -f ${CONTAINER} 2>&1 | grep --color=always -E "scheduler|Schedule"
        ;;
    ai|ai-mode)
        echo "🤖 Watching AI MODE logs..."
        echo ""
        docker logs -f ${CONTAINER} 2>&1 | grep --color=always -E "adaptive_controller|AI Mode|heating_curve"
        ;;
    errors|err)
        echo "❌ Watching ERROR logs..."
        echo ""
        docker logs -f ${CONTAINER} 2>&1 | grep --color=always -iE "error|fail|exception"
        ;;
    all|*)
        echo "📊 Watching ALL logs (filtered for important events)..."
        echo ""
        docker logs -f ${CONTAINER} 2>&1 | grep --color=always -E "scheduler|Schedule|adaptive_controller|AI Mode|error|ERROR|fail|FAIL"
        ;;
esac
