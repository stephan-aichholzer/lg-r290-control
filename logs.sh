#!/bin/bash
# LG R290 Heat Pump - Docker Stack Log Manager
#
# This script provides easy access to Docker container logs with various output modes.
#
# Usage:
#   ./logs.sh [command] [service] [options]
#
# Commands:
#   tail        - Follow logs in real-time (default)
#   dump        - Dump all logs to console
#   save        - Save logs to files
#   errors      - Show only errors/warnings
#   search      - Search logs for pattern
#   stats       - Show log statistics
#
# Services:
#   all         - All services (default)
#   service     - Heat pump API service
#   mock        - Mock Modbus server
#   ui          - Web UI (Nginx)
#
# Examples:
#   ./logs.sh                           # Tail all services
#   ./logs.sh tail service              # Tail only API service
#   ./logs.sh dump                      # Dump all logs to console
#   ./logs.sh save                      # Save logs to timestamped files
#   ./logs.sh errors                    # Show only errors/warnings
#   ./logs.sh search "temperature"      # Search for pattern
#   ./logs.sh stats                     # Show log statistics

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Container names
CONTAINERS=(
    "lg_r290_service"
    "lg_r290_mock"
    "lg_r290_ui"
)

CONTAINER_LABELS=(
    "API Service"
    "Mock Server"
    "Web UI"
)

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running${NC}"
        exit 1
    fi
}

# Check if containers exist
check_containers() {
    local missing=0
    for container in "${CONTAINERS[@]}"; do
        if ! docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "${YELLOW}⚠️  Container ${container} not found${NC}"
            missing=$((missing + 1))
        fi
    done

    if [ $missing -eq ${#CONTAINERS[@]} ]; then
        echo -e "${RED}❌ No containers found. Have you started the stack?${NC}"
        echo -e "${CYAN}Run: docker-compose up -d${NC}"
        exit 1
    fi
}

# Get container name from service alias
get_container_name() {
    local service="$1"
    case "$service" in
        service|api)
            echo "lg_r290_service"
            ;;
        mock|modbus)
            echo "lg_r290_mock"
            ;;
        ui|web|nginx)
            echo "lg_r290_ui"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Print header
print_header() {
    local title="$1"
    echo ""
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $title${NC}"
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Tail logs (follow in real-time)
tail_logs() {
    local service="${1:-all}"

    if [ "$service" = "all" ]; then
        print_header "Tailing All Services (Press Ctrl+C to stop)"
        echo -e "${CYAN}Services: API Service, Mock Server, Web UI${NC}"
        echo ""

        # Use docker-compose for colored output
        docker-compose logs -f --tail=50
    else
        local container=$(get_container_name "$service")
        if [ -z "$container" ]; then
            echo -e "${RED}❌ Unknown service: $service${NC}"
            echo -e "${CYAN}Available: service, mock, ui${NC}"
            exit 1
        fi

        if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "${YELLOW}⚠️  Container ${container} is not running${NC}"
            exit 1
        fi

        print_header "Tailing ${container} (Press Ctrl+C to stop)"
        docker logs -f --tail=50 "$container"
    fi
}

# Dump all logs to console
dump_logs() {
    local service="${1:-all}"
    local lines="${2:-all}"

    if [ "$service" = "all" ]; then
        print_header "Dumping All Logs"

        for i in "${!CONTAINERS[@]}"; do
            local container="${CONTAINERS[$i]}"
            local label="${CONTAINER_LABELS[$i]}"

            if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
                echo ""
                echo -e "${BOLD}${MAGENTA}▶ ${label} (${container})${NC}"
                echo -e "${CYAN}────────────────────────────────────────────────────${NC}"

                if [ "$lines" = "all" ]; then
                    docker logs "$container" 2>&1
                else
                    docker logs --tail="$lines" "$container" 2>&1
                fi

                echo ""
            else
                echo -e "${YELLOW}⚠️  ${label} (${container}) not found${NC}"
            fi
        done
    else
        local container=$(get_container_name "$service")
        if [ -z "$container" ]; then
            echo -e "${RED}❌ Unknown service: $service${NC}"
            exit 1
        fi

        print_header "Dumping ${container} Logs"

        if [ "$lines" = "all" ]; then
            docker logs "$container" 2>&1
        else
            docker logs --tail="$lines" "$container" 2>&1
        fi
    fi
}

# Save logs to files
save_logs() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local log_dir="logs_${timestamp}"

    mkdir -p "$log_dir"

    print_header "Saving Logs to ${log_dir}/"

    for i in "${!CONTAINERS[@]}"; do
        local container="${CONTAINERS[$i]}"
        local label="${CONTAINER_LABELS[$i]}"

        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            local log_file="${log_dir}/${container}.log"
            echo -e "${GREEN}✓${NC} Saving ${label} → ${log_file}"
            docker logs "$container" > "$log_file" 2>&1
        else
            echo -e "${YELLOW}⚠${NC} ${label} not found, skipping"
        fi
    done

    # Create combined log
    echo -e "${GREEN}✓${NC} Creating combined log → ${log_dir}/combined.log"
    for i in "${!CONTAINERS[@]}"; do
        local container="${CONTAINERS[$i]}"
        local log_file="${log_dir}/${container}.log"

        if [ -f "$log_file" ]; then
            echo "" >> "${log_dir}/combined.log"
            echo "═══════════════════════════════════════════════════════════════" >> "${log_dir}/combined.log"
            echo "  ${CONTAINER_LABELS[$i]} (${container})" >> "${log_dir}/combined.log"
            echo "═══════════════════════════════════════════════════════════════" >> "${log_dir}/combined.log"
            echo "" >> "${log_dir}/combined.log"
            cat "$log_file" >> "${log_dir}/combined.log"
        fi
    done

    echo ""
    echo -e "${BOLD}${GREEN}✅ Logs saved to: ${log_dir}/${NC}"
    echo ""
    ls -lh "$log_dir"
}

# Show only errors and warnings
show_errors() {
    local service="${1:-all}"

    print_header "Errors and Warnings"

    if [ "$service" = "all" ]; then
        for i in "${!CONTAINERS[@]}"; do
            local container="${CONTAINERS[$i]}"
            local label="${CONTAINER_LABELS[$i]}"

            if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
                echo ""
                echo -e "${BOLD}${MAGENTA}▶ ${label}${NC}"
                echo -e "${CYAN}────────────────────────────────────────────────────${NC}"

                docker logs "$container" 2>&1 | grep -iE "(error|warning|critical|exception|failed|❌|⚠️)" || echo -e "${GREEN}No errors found${NC}"
            fi
        done
    else
        local container=$(get_container_name "$service")
        if [ -z "$container" ]; then
            echo -e "${RED}❌ Unknown service: $service${NC}"
            exit 1
        fi

        docker logs "$container" 2>&1 | grep -iE "(error|warning|critical|exception|failed|❌|⚠️)" || echo -e "${GREEN}No errors found${NC}"
    fi
}

# Search logs for pattern
search_logs() {
    local pattern="$1"
    local service="${2:-all}"

    print_header "Searching for: ${pattern}"

    if [ "$service" = "all" ]; then
        for i in "${!CONTAINERS[@]}"; do
            local container="${CONTAINERS[$i]}"
            local label="${CONTAINER_LABELS[$i]}"

            if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
                echo ""
                echo -e "${BOLD}${MAGENTA}▶ ${label}${NC}"
                echo -e "${CYAN}────────────────────────────────────────────────────${NC}"

                docker logs "$container" 2>&1 | grep -i "$pattern" --color=always || echo -e "${YELLOW}No matches found${NC}"
            fi
        done
    else
        local container=$(get_container_name "$service")
        if [ -z "$container" ]; then
            echo -e "${RED}❌ Unknown service: $service${NC}"
            exit 1
        fi

        docker logs "$container" 2>&1 | grep -i "$pattern" --color=always || echo -e "${YELLOW}No matches found${NC}"
    fi
}

# Show log statistics
show_stats() {
    print_header "Log Statistics"

    for i in "${!CONTAINERS[@]}"; do
        local container="${CONTAINERS[$i]}"
        local label="${CONTAINER_LABELS[$i]}"

        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "${BOLD}${MAGENTA}▶ ${label}${NC}"

            local total_lines=$(docker logs "$container" 2>&1 | wc -l)
            local errors=$(docker logs "$container" 2>&1 | grep -ic "error" || echo 0)
            local warnings=$(docker logs "$container" 2>&1 | grep -ic "warning" || echo 0)
            local info=$(docker logs "$container" 2>&1 | grep -ic "info" || echo 0)

            # Container status
            local status=$(docker inspect -f '{{.State.Status}}' "$container")
            local running_time=""
            if [ "$status" = "running" ]; then
                running_time=$(docker inspect -f '{{.State.StartedAt}}' "$container" | xargs -I {} date -d {} +"%Y-%m-%d %H:%M:%S")
            fi

            echo -e "  ${CYAN}Status:${NC}        ${status}"
            if [ -n "$running_time" ]; then
                echo -e "  ${CYAN}Started:${NC}       ${running_time}"
            fi
            echo -e "  ${CYAN}Total lines:${NC}   ${total_lines}"
            echo -e "  ${GREEN}INFO:${NC}          ${info}"
            echo -e "  ${YELLOW}WARNINGS:${NC}      ${warnings}"
            echo -e "  ${RED}ERRORS:${NC}        ${errors}"
            echo ""
        else
            echo -e "${YELLOW}⚠️  ${label} not found${NC}"
            echo ""
        fi
    done
}

# Show usage
show_usage() {
    cat << EOF
${BOLD}LG R290 Heat Pump - Docker Stack Log Manager${NC}

${BOLD}USAGE:${NC}
    ./logs.sh [command] [service] [options]

${BOLD}COMMANDS:${NC}
    ${GREEN}tail${NC}        Follow logs in real-time (default)
    ${GREEN}dump${NC}        Dump all logs to console
    ${GREEN}save${NC}        Save logs to timestamped directory
    ${GREEN}errors${NC}      Show only errors and warnings
    ${GREEN}search${NC}      Search logs for pattern
    ${GREEN}stats${NC}       Show log statistics and container info
    ${GREEN}help${NC}        Show this help message

${BOLD}SERVICES:${NC}
    ${CYAN}all${NC}         All services (default)
    ${CYAN}service${NC}     Heat pump API service (FastAPI)
    ${CYAN}mock${NC}        Mock Modbus server (development)
    ${CYAN}ui${NC}          Web UI (Nginx)

${BOLD}EXAMPLES:${NC}
    ${YELLOW}# Tail all services in real-time${NC}
    ./logs.sh
    ./logs.sh tail

    ${YELLOW}# Tail specific service${NC}
    ./logs.sh tail service
    ./logs.sh tail mock

    ${YELLOW}# Dump all logs to console${NC}
    ./logs.sh dump

    ${YELLOW}# Dump last 100 lines${NC}
    ./logs.sh dump all 100

    ${YELLOW}# Save logs to files${NC}
    ./logs.sh save

    ${YELLOW}# Show only errors and warnings${NC}
    ./logs.sh errors
    ./logs.sh errors service

    ${YELLOW}# Search for specific pattern${NC}
    ./logs.sh search "temperature"
    ./logs.sh search "Modbus" service

    ${YELLOW}# Show log statistics${NC}
    ./logs.sh stats

${BOLD}LOG LEVELS YOU'LL SEE:${NC}
    ${GREEN}INFO${NC}        Normal operations, status updates
    ${YELLOW}WARNING${NC}     Recoverable issues, retries
    ${RED}ERROR${NC}       Failures, exceptions
    ${CYAN}DEBUG${NC}       Detailed operation info (if enabled)

${BOLD}COMMON PATTERNS TO SEARCH:${NC}
    - "temperature"      Temperature readings and adjustments
    - "Modbus"           Modbus communication details
    - "AI Mode"          Adaptive controller activity
    - "power"            Power state changes
    - "connected"        Connection status
    - "failed"           Operation failures
    - "retry"            Retry attempts

EOF
}

# Main script logic
main() {
    check_docker
    check_containers

    local command="${1:-tail}"

    case "$command" in
        tail)
            tail_logs "${2:-all}"
            ;;
        dump)
            dump_logs "${2:-all}" "${3:-all}"
            ;;
        save)
            save_logs
            ;;
        errors|error)
            show_errors "${2:-all}"
            ;;
        search|grep|find)
            if [ -z "${2:-}" ]; then
                echo -e "${RED}❌ Search pattern required${NC}"
                echo -e "${CYAN}Usage: ./logs.sh search <pattern> [service]${NC}"
                exit 1
            fi
            search_logs "$2" "${3:-all}"
            ;;
        stats|status|info)
            show_stats
            ;;
        help|-h|--help)
            show_usage
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $command${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
