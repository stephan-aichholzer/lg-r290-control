#!/bin/bash
# LG R290 Heat Pump - Docker Stack Monitor
#
# Real-time monitoring dashboard for the Docker stack
#
# Usage:
#   ./monitor.sh [mode]
#
# Modes:
#   dashboard   - Full monitoring dashboard (default)
#   containers  - Container status only
#   api         - API status and recent activity
#   temps       - Temperature monitoring
#   ai          - AI Mode status
#
# Examples:
#   ./monitor.sh              # Full dashboard
#   ./monitor.sh temps        # Temperature monitoring
#   ./monitor.sh api          # API activity

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
API_URL="http://localhost:8002"
THERMOSTAT_URL="http://192.168.2.11:8001"
REFRESH_INTERVAL=5

# Check if jq is available
JQ_AVAILABLE=false
if command -v jq &> /dev/null; then
    JQ_AVAILABLE=true
fi

# Pretty print JSON if jq available
pretty_json() {
    if [ "$JQ_AVAILABLE" = true ]; then
        jq -C '.'
    else
        cat
    fi
}

# Clear screen
clear_screen() {
    clear
}

# Print header
print_header() {
    local title="$1"
    echo -e "${BOLD}${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║  ${title}$(printf '%*s' $((60 - ${#title})) '')║${NC}"
    echo -e "${BOLD}${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print section header
print_section() {
    local title="$1"
    echo ""
    echo -e "${BOLD}${CYAN}▶ ${title}${NC}"
    echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
}

# Check container status
check_container_status() {
    local containers=("lg_r290_service" "lg_r290_mock" "lg_r290_ui")
    local labels=("API Service" "Mock Server" "Web UI")

    print_section "Container Status"

    for i in "${!containers[@]}"; do
        local container="${containers[$i]}"
        local label="${labels[$i]}"

        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            local status=$(docker inspect -f '{{.State.Status}}' "$container")
            local health=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
            local uptime=$(docker inspect -f '{{.State.StartedAt}}' "$container" | xargs -I {} date -d {} +"%Y-%m-%d %H:%M:%S")

            echo -e "  ${GREEN}✓${NC} ${BOLD}${label}${NC} (${container})"
            echo -e "    Status: ${GREEN}running${NC}  |  Started: ${uptime}"

            # Show resource usage
            local stats=$(docker stats --no-stream --format "{{.CPUPerc}}\t{{.MemUsage}}" "$container" 2>/dev/null || echo "N/A\tN/A")
            local cpu=$(echo "$stats" | cut -f1)
            local mem=$(echo "$stats" | cut -f2)
            echo -e "    CPU: ${cpu}  |  Memory: ${mem}"
        elif docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "  ${RED}✗${NC} ${BOLD}${label}${NC} (${container})"
            echo -e "    Status: ${RED}stopped${NC}"
        else
            echo -e "  ${YELLOW}?${NC} ${BOLD}${label}${NC} (${container})"
            echo -e "    Status: ${YELLOW}not found${NC}"
        fi
        echo ""
    done
}

# Check API health
check_api_status() {
    print_section "API Health Check"

    if ! docker ps --format '{{.Names}}' | grep -q "^lg_r290_service$"; then
        echo -e "  ${RED}✗ API container not running${NC}"
        return
    fi

    # Health endpoint
    if response=$(curl -s -w "\n%{http_code}" "${API_URL}/health" 2>/dev/null); then
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" = "200" ]; then
            echo -e "  ${GREEN}✓${NC} Health endpoint: ${GREEN}OK${NC}"
            if [ "$JQ_AVAILABLE" = true ]; then
                local status=$(echo "$body" | jq -r '.status // "unknown"')
                local age=$(echo "$body" | jq -r '.status_age_seconds // 0')
                echo -e "    Status: ${status}  |  Data age: ${age}s"
            fi
        else
            echo -e "  ${RED}✗${NC} Health endpoint: ${RED}HTTP ${http_code}${NC}"
        fi
    else
        echo -e "  ${RED}✗${NC} Health endpoint: ${RED}unreachable${NC}"
    fi

    echo ""

    # Check OpenAPI docs availability
    if curl -s "${API_URL}/docs" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} API Documentation: ${CYAN}${API_URL}/docs${NC}"
    else
        echo -e "  ${YELLOW}?${NC} API Documentation: unreachable"
    fi
}

# Show temperature data
show_temperatures() {
    print_section "Temperature Monitoring"

    if ! docker ps --format '{{.Names}}' | grep -q "^lg_r290_service$"; then
        echo -e "  ${RED}✗ API container not running${NC}"
        return
    fi

    if response=$(curl -s "${API_URL}/status" 2>/dev/null); then
        if [ "$JQ_AVAILABLE" = true ]; then
            local flow=$(echo "$response" | jq -r '.flow_temperature // 0')
            local return_temp=$(echo "$response" | jq -r '.return_temperature // 0')
            local outdoor=$(echo "$response" | jq -r '.outdoor_temperature // 0')
            local target=$(echo "$response" | jq -r '.target_temperature // 0')
            local power=$(echo "$response" | jq -r '.is_on // false')
            local mode=$(echo "$response" | jq -r '.operating_mode // "Unknown"')

            echo -e "  ${BOLD}Power:${NC}         $(if [ "$power" = "true" ]; then echo -e "${GREEN}ON${NC}"; else echo -e "${YELLOW}OFF${NC}"; fi)"
            echo -e "  ${BOLD}Mode:${NC}          ${mode}"
            echo ""
            echo -e "  ${BOLD}Target Temp:${NC}   ${target}°C"
            echo -e "  ${BOLD}Flow Temp:${NC}     ${RED}${flow}°C${NC} (water outlet)"
            echo -e "  ${BOLD}Return Temp:${NC}   ${BLUE}${return_temp}°C${NC} (water inlet)"
            echo -e "  ${BOLD}Outdoor Temp:${NC}  ${CYAN}${outdoor}°C${NC}"

            # Calculate delta
            local delta=$(echo "$flow - $return_temp" | bc 2>/dev/null || echo "N/A")
            if [ "$delta" != "N/A" ]; then
                echo ""
                echo -e "  ${BOLD}ΔT (Flow-Return):${NC} ${delta}°C"
            fi
        else
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        fi
    else
        echo -e "  ${RED}✗ Failed to fetch temperature data${NC}"
    fi
}

# Show AI Mode status
show_ai_mode() {
    print_section "AI Mode Status"

    if ! docker ps --format '{{.Names}}' | grep -q "^lg_r290_service$"; then
        echo -e "  ${RED}✗ API container not running${NC}"
        return
    fi

    if response=$(curl -s "${API_URL}/ai-mode" 2>/dev/null); then
        if [ "$JQ_AVAILABLE" = true ]; then
            local enabled=$(echo "$response" | jq -r '.enabled // false')
            local outdoor=$(echo "$response" | jq -r '.outdoor_temperature // null')
            local target_room=$(echo "$response" | jq -r '.target_room_temperature // null')
            local calc_flow=$(echo "$response" | jq -r '.calculated_flow_temperature // null')
            local curve_name=$(echo "$response" | jq -r '.heating_curve.name // "N/A"')
            local last_update=$(echo "$response" | jq -r '.last_update // "never"')

            echo -e "  ${BOLD}Enabled:${NC}       $(if [ "$enabled" = "true" ]; then echo -e "${GREEN}YES${NC}"; else echo -e "${YELLOW}NO${NC}"; fi)"
            echo -e "  ${BOLD}Last Update:${NC}   ${last_update}"
            echo ""

            if [ "$enabled" = "true" ] && [ "$outdoor" != "null" ]; then
                echo -e "  ${BOLD}Outdoor Temp:${NC}       ${outdoor}°C"
                echo -e "  ${BOLD}Target Room Temp:${NC}   ${target_room}°C"
                echo -e "  ${BOLD}Calculated Flow:${NC}    ${calc_flow}°C"
                echo -e "  ${BOLD}Heating Curve:${NC}      ${curve_name}"
            else
                echo -e "  ${YELLOW}AI Mode is disabled or no data available${NC}"
            fi
        else
            echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
        fi
    else
        echo -e "  ${RED}✗ Failed to fetch AI Mode data${NC}"
    fi
}

# Show recent API activity from logs
show_api_activity() {
    print_section "Recent API Activity (Last 20 lines)"

    if ! docker ps --format '{{.Names}}' | grep -q "^lg_r290_service$"; then
        echo -e "  ${RED}✗ API container not running${NC}"
        return
    fi

    docker logs --tail=20 lg_r290_service 2>&1 | while IFS= read -r line; do
        # Colorize log levels
        if echo "$line" | grep -q "ERROR"; then
            echo -e "  ${RED}${line}${NC}"
        elif echo "$line" | grep -q "WARNING"; then
            echo -e "  ${YELLOW}${line}${NC}"
        elif echo "$line" | grep -q "INFO"; then
            echo -e "  ${GREEN}${line}${NC}"
        else
            echo "  ${line}"
        fi
    done
}

# Full dashboard
show_dashboard() {
    while true; do
        clear_screen
        print_header "LG R290 Heat Pump - Monitoring Dashboard"
        echo -e "${CYAN}Refresh: ${REFRESH_INTERVAL}s  |  Time: $(date '+%Y-%m-%d %H:%M:%S')  |  Press Ctrl+C to exit${NC}"

        check_container_status
        check_api_status
        show_temperatures
        show_ai_mode

        echo ""
        echo -e "${CYAN}Refreshing in ${REFRESH_INTERVAL} seconds...${NC}"

        sleep "$REFRESH_INTERVAL"
    done
}

# Temperature monitoring loop
monitor_temps() {
    while true; do
        clear_screen
        print_header "Temperature Monitoring"
        echo -e "${CYAN}Refresh: ${REFRESH_INTERVAL}s  |  Time: $(date '+%Y-%m-%d %H:%M:%S')  |  Press Ctrl+C to exit${NC}"

        show_temperatures

        echo ""
        echo -e "${CYAN}Refreshing in ${REFRESH_INTERVAL} seconds...${NC}"

        sleep "$REFRESH_INTERVAL"
    done
}

# Show usage
show_usage() {
    cat << EOF
${BOLD}LG R290 Heat Pump - Docker Stack Monitor${NC}

${BOLD}USAGE:${NC}
    ./monitor.sh [mode]

${BOLD}MODES:${NC}
    ${GREEN}dashboard${NC}   Full monitoring dashboard (default)
    ${GREEN}containers${NC}  Container status only
    ${GREEN}api${NC}         API status and recent activity
    ${GREEN}temps${NC}       Temperature monitoring (live)
    ${GREEN}ai${NC}          AI Mode status
    ${GREEN}once${NC}        Show dashboard once (no refresh)
    ${GREEN}help${NC}        Show this help message

${BOLD}EXAMPLES:${NC}
    ${YELLOW}# Full dashboard (auto-refresh)${NC}
    ./monitor.sh
    ./monitor.sh dashboard

    ${YELLOW}# Monitor temperatures only${NC}
    ./monitor.sh temps

    ${YELLOW}# Check API activity${NC}
    ./monitor.sh api

    ${YELLOW}# One-time status check${NC}
    ./monitor.sh once

${BOLD}REQUIREMENTS:${NC}
    - Docker and docker-compose
    - jq (optional, for better JSON formatting)
      Install: ${CYAN}sudo apt-get install jq${NC}

${BOLD}RELATED COMMANDS:${NC}
    ${CYAN}./logs.sh${NC}              View/tail container logs
    ${CYAN}docker-compose ps${NC}      Container status
    ${CYAN}docker stats${NC}           Resource usage
    ${CYAN}curl ${API_URL}/docs${NC}
                            API documentation

EOF
}

# Main
main() {
    local mode="${1:-dashboard}"

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running${NC}"
        exit 1
    fi

    # Warn if jq not available
    if [ "$JQ_AVAILABLE" = false ]; then
        echo -e "${YELLOW}⚠️  'jq' not installed - output may be less readable${NC}"
        echo -e "${CYAN}Install with: sudo apt-get install jq${NC}"
        echo ""
        sleep 2
    fi

    case "$mode" in
        dashboard)
            show_dashboard
            ;;
        containers|status)
            clear_screen
            print_header "Container Status"
            check_container_status
            ;;
        api|activity)
            clear_screen
            print_header "API Status"
            check_api_status
            show_api_activity
            ;;
        temps|temperature|temperatures)
            monitor_temps
            ;;
        ai|ai-mode|adaptive)
            clear_screen
            print_header "AI Mode Status"
            show_ai_mode
            ;;
        once|single|snapshot)
            clear_screen
            print_header "System Snapshot - $(date '+%Y-%m-%d %H:%M:%S')"
            check_container_status
            check_api_status
            show_temperatures
            show_ai_mode
            echo ""
            ;;
        help|-h|--help)
            show_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown mode: $mode${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
