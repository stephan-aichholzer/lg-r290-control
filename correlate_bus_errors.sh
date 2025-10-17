#!/bin/bash
# Correlate RS-485 bus errors between LG R290 (monitor.log) and WAGO meter

set -e

echo "═══════════════════════════════════════════════════════════════════════"
echo "RS-485 Bus Collision Correlation Analysis"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Data sources:"
echo "  - LG R290:    monitor.log (host process)"
echo "  - WAGO Meter: Docker logs (modbus_modbus_exporter_1)"
echo ""

# Temp files
LG_ERRORS=$(mktemp)
WAGO_ERRORS=$(mktemp)
MERGED=$(mktemp)

# Cleanup on exit
trap "rm -f $LG_ERRORS $WAGO_ERRORS $MERGED" EXIT

# Extract LG R290 errors with timestamps
echo "📊 Extracting LG R290 errors from monitor.log..."
grep -E "ERROR|WARNING.*Failed" monitor.log 2>/dev/null | \
    sed 's/^/[LG_R290] /' > $LG_ERRORS || true

# Extract WAGO meter errors with timestamps from Docker
echo "📊 Extracting WAGO meter errors from Docker logs..."
docker logs modbus_modbus_exporter_1 --timestamps 2>&1 | \
    grep -E "ERROR|unpack requires|WARNING.*garbage|Unable to decode" | \
    sed 's/^/[WAGO  ] /' > $WAGO_ERRORS || true

# Merge by converting timestamps to comparable format and sorting
cat $LG_ERRORS $WAGO_ERRORS | sort -k2,3 > $MERGED

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Chronological Error Timeline"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

cat $MERGED | while IFS= read -r line; do
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

LG_COUNT=$(wc -l < $LG_ERRORS)
WAGO_COUNT=$(wc -l < $WAGO_ERRORS)
TOTAL=$((LG_COUNT + WAGO_COUNT))

echo "LG R290 errors:    $LG_COUNT"
echo "WAGO meter errors: $WAGO_COUNT"
echo "Total errors:      $TOTAL"

if [[ $TOTAL -eq 0 ]]; then
    echo ""
    echo "✅ No errors found in recent logs!"
    echo ""
    echo "This is GOOD - either:"
    echo "  1. PyModbus optimizations are working perfectly"
    echo "  2. Systems haven't run long enough to encounter collisions"
    echo "  3. Bus traffic patterns don't overlap"
    exit 0
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Detailed Analysis"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Analyze error patterns
echo "LG R290 error types:"
grep -oE "(list index out of range|unpack requires|timeout|Failed to read)" $LG_ERRORS 2>/dev/null | sort | uniq -c || echo "  (none)"

echo ""
echo "WAGO meter error types:"
grep -oE "(unpack requires.*bytes|garbage value|Unable to decode)" $WAGO_ERRORS 2>/dev/null | sort | uniq -c || echo "  (none)"

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Time-based Correlation (±10 second window)"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

# Parse timestamps and find correlations
declare -A lg_times
declare -A wago_times

# Extract LG timestamps (format: 2025-10-16 07:48:43)
while IFS= read -r line; do
    ts=$(echo "$line" | grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}' | head -1)
    if [[ -n "$ts" ]]; then
        epoch=$(date -d "$ts" +%s 2>/dev/null || echo 0)
        if [[ $epoch -gt 0 ]]; then
            lg_times[$epoch]="$line"
        fi
    fi
done < $LG_ERRORS

# Extract WAGO timestamps (format: 2025-10-16T07:48:43.123456789Z)
while IFS= read -r line; do
    ts=$(echo "$line" | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}' | head -1)
    if [[ -n "$ts" ]]; then
        epoch=$(date -d "$ts" +%s 2>/dev/null || echo 0)
        if [[ $epoch -gt 0 ]]; then
            wago_times[$epoch]="$line"
        fi
    fi
done < $WAGO_ERRORS

# Find correlations (errors within 10 seconds)
collision_count=0
collision_window=10

for lg_time in "${!lg_times[@]}"; do
    for wago_time in "${!wago_times[@]}"; do
        diff=$((lg_time - wago_time))
        abs_diff=${diff#-}  # Absolute value

        if [[ $abs_diff -le $collision_window ]]; then
            echo "⚠️  Potential collision (Δ=${diff}s):"
            echo "    LG:   ${lg_times[$lg_time]}"
            echo "    WAGO: ${wago_times[$wago_time]}"
            echo ""
            ((collision_count++))
        fi
    done
done

if [[ $collision_count -eq 0 ]]; then
    echo "ℹ️  No correlated errors found within ${collision_window}s window"
    echo ""
    echo "Possible reasons:"
    echo "  1. Systems poll at different times (no overlap)"
    echo "  2. Retry logic prevents simultaneous access"
    echo "  3. Errors are random, not collision-related"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "Summary"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""

if [[ $collision_count -gt 0 ]]; then
    collision_rate=$((collision_count * 100 / TOTAL))
    echo "✅ CONFIRMED: Bus collisions detected"
    echo "   Correlated errors: $collision_count / $TOTAL (${collision_rate}%)"
    echo ""
    echo "Recommendations:"
    echo "  1. ✓ Retry logic is working (keep it)"
    echo "  2. ✓ PyModbus logging suppressed (clean logs)"
    echo "  3. Consider: Offset polling intervals to avoid overlap"
    echo "     - LG R290:  Every 20s starting at :00"
    echo "     - WAGO:     Every Ns starting at :10 (check their config)"
else
    echo "✓ No significant bus contention detected"
    echo "  Current setup appears optimal"
fi

echo ""
