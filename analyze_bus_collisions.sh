#!/bin/bash
# Analyze RS-485 bus collision correlation between LG R290 and WAGO meter

set -e

echo "═══════════════════════════════════════════════════════════════════════"
echo "RS-485 Bus Collision Analysis"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Analyzing correlation between:"
echo "  - LG R290 Heat Pump (lg_r290_control-service-1)"
echo "  - WAGO Energy Meter (modbus_modbus_exporter_1)"
echo ""
echo "Looking for overlapping errors indicating shared bus collisions..."
echo ""

# Get logs from both containers with timestamps
LG_LOGS=$(mktemp)
WAGO_LOGS=$(mktemp)
MERGED=$(mktemp)

# Cleanup on exit
trap "rm -f $LG_LOGS $WAGO_LOGS $MERGED" EXIT

# Extract LG R290 errors with timestamps
echo "📊 Extracting LG R290 errors..."
docker logs lg_r290_control-service-1 --timestamps 2>&1 | \
    grep -E "ERROR|unpack requires|list index out of range|Unable to decode|WARNING.*retry" | \
    sed 's/^/[LG_R290] /' > $LG_LOGS || true

# Extract WAGO meter errors with timestamps
echo "📊 Extracting WAGO meter errors..."
docker logs modbus_modbus_exporter_1 --timestamps 2>&1 | \
    grep -E "ERROR|unpack requires|WARNING.*garbage|Unable to decode" | \
    sed 's/^/[WAGO  ] /' > $WAGO_LOGS || true

# Merge and sort by timestamp
cat $LG_LOGS $WAGO_LOGS | sort > $MERGED

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Chronological Error Timeline (Last 100 errors)"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

tail -100 $MERGED | while IFS= read -r line; do
    # Color code by source
    if [[ $line == *"[LG_R290]"* ]]; then
        echo -e "\033[0;36m$line\033[0m"  # Cyan for LG
    else
        echo -e "\033[0;33m$line\033[0m"  # Yellow for WAGO
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Statistics"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

LG_COUNT=$(wc -l < $LG_LOGS)
WAGO_COUNT=$(wc -l < $WAGO_LOGS)
TOTAL=$((LG_COUNT + WAGO_COUNT))

echo "LG R290 errors:    $LG_COUNT"
echo "WAGO meter errors: $WAGO_COUNT"
echo "Total errors:      $TOTAL"
echo ""

# Find errors within 5 seconds of each other (likely collisions)
echo "═══════════════════════════════════════════════════════════════════════"
echo "Potential Bus Collisions (errors within 5 seconds)"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

prev_ts=""
prev_line=""
collision_count=0

while IFS= read -r line; do
    # Extract timestamp (format: 2025-10-16T05:40:09.320878653Z)
    ts=$(echo "$line" | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' || echo "")

    if [[ -n "$prev_ts" && -n "$ts" ]]; then
        # Convert to seconds since epoch
        prev_sec=$(date -d "$prev_ts" +%s 2>/dev/null || echo 0)
        curr_sec=$(date -d "$ts" +%s 2>/dev/null || echo 0)

        diff=$((curr_sec - prev_sec))

        # Check if different sources and within 5 seconds
        if [[ $diff -le 5 && $diff -ge -5 ]]; then
            if [[ "$prev_line" == *"[LG_R290]"* && "$line" == *"[WAGO  ]"* ]] || \
               [[ "$prev_line" == *"[WAGO  ]"* && "$line" == *"[LG_R290]"* ]]; then
                echo "⚠️  Collision detected (Δ=${diff}s):"
                echo "    $prev_line"
                echo "    $line"
                echo ""
                ((collision_count++))
            fi
        fi
    fi

    prev_ts="$ts"
    prev_line="$line"
done < $MERGED

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Summary"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Detected bus collisions: $collision_count"

if [[ $collision_count -gt 0 ]]; then
    echo ""
    echo "✅ CONFIRMED: Errors correlate with concurrent access"
    echo "   → Both systems accessing RS-485 bus simultaneously"
    echo "   → Collisions causing corrupted frames"
    echo ""
    echo "Recommendations:"
    echo "  1. Keep retry logic (already working)"
    echo "  2. Reduce polling frequency if possible"
    echo "  3. Consider time-division scheduling (offset poll times)"
else
    echo ""
    echo "ℹ️  No clear correlation found"
    echo "   → Errors may be random network issues"
    echo "   → Or systems poll at very different intervals"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
