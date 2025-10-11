# Monitoring Scripts

Quick reference for system monitoring scripts.

## Available Scripts

### 🔍 system_status.sh
**Quick system overview** - Shows current status of all components at a glance.

```bash
./system_status.sh
```

**Displays:**
- Docker container status
- Heat pump status (power, temperature, mode)
- AI Mode status (enabled, curve, adjustments)
- Scheduler status (enabled, current time, timezone)
- Thermostat status (mode, temperatures, pump)
- Recent activity (last 10 events)
- Health check

**Use case:** Quick check to see if everything is working.

---

### 📅 monitor_scheduler.sh
**Detailed scheduler monitoring** - Shows scheduler activity and configuration.

```bash
./monitor_scheduler.sh
```

**Displays:**
- Scheduler status (enabled, current time, timezone)
- Current thermostat status (mode, target temp)
- Recent scheduler logs (last 20 entries)
- Schedule matches (when schedule triggered)
- Schedule skips (when ECO/OFF mode prevented schedule)
- Current schedule configuration (from schedule.json)

**Use case:** Debug scheduler behavior, verify schedules are triggering.

---

### 🤖 monitor_ai_mode.sh
**Detailed AI Mode monitoring** - Shows AI Mode decisions and heating curve activity.

```bash
./monitor_ai_mode.sh
```

**Displays:**
- AI Mode status (enabled, curve selected, adjustment needed)
- Heat pump status (flow/return temperatures)
- Target room temperature (from thermostat)
- Recent AI Mode logs (last 20 entries)
- Temperature adjustments (when AI Mode changed flow temp)
- Heating curve selections (ECO/Comfort/High)
- Outdoor temp cutoff/restart events
- Heating curve configuration (settings)

**Use case:** Debug AI Mode decisions, verify heating curve logic.

---

### 📺 watch_logs.sh
**Live log monitoring** - Real-time log streaming with filtering.

```bash
# Watch all important logs
./watch_logs.sh

# Watch only scheduler logs
./watch_logs.sh scheduler

# Watch only AI Mode logs
./watch_logs.sh ai

# Watch only errors
./watch_logs.sh errors
```

**Modes:**
- `all` (default): All important events (scheduler, AI Mode, errors)
- `scheduler`: Only scheduler events
- `ai` or `ai-mode`: Only AI Mode events
- `errors` or `err`: Only error messages

**Use case:** Real-time monitoring during testing or debugging.

---

## Usage Examples

### Morning Check
```bash
# Quick status check
./system_status.sh
```

### Verify Scheduler Working
```bash
# Check if schedule triggered at 05:00
./monitor_scheduler.sh | grep "Schedule match"

# Watch for next schedule trigger (live)
./watch_logs.sh scheduler
```

### Verify AI Mode Working
```bash
# Check recent AI Mode adjustments
./monitor_ai_mode.sh | grep "Adjusted flow"

# Watch AI Mode decisions live
./watch_logs.sh ai
```

### Debugging
```bash
# Check for errors
./watch_logs.sh errors

# Full scheduler details
./monitor_scheduler.sh

# Full AI Mode details
./monitor_ai_mode.sh
```

### Continuous Monitoring
```bash
# Open 3 terminal windows:

# Window 1: System overview (refresh every 10 seconds)
watch -n 10 ./system_status.sh

# Window 2: Scheduler logs
./watch_logs.sh scheduler

# Window 3: AI Mode logs
./watch_logs.sh ai
```

## Log Locations

All logs are read from Docker container using `docker logs`:

```bash
# Raw logs (all output)
docker logs lg_r290_service

# Follow logs live
docker logs -f lg_r290_service

# Last 100 lines
docker logs --tail 100 lg_r290_service

# Logs since 1 hour ago
docker logs --since 1h lg_r290_service
```

## Requirements

Scripts require:
- `docker` command
- `curl` command
- `jq` command (for JSON formatting)

**Install jq if missing:**
```bash
sudo apt install jq
```

## Troubleshooting

### "Container not running"
```bash
# Check container status
docker ps -a | grep lg_r290

# Start containers
docker-compose up -d
```

### "Failed to fetch status"
```bash
# Check if service is responding
curl http://localhost:8002/health

# Check container logs
docker logs lg_r290_service --tail 50
```

### "jq command not found"
```bash
# Install jq
sudo apt install jq
```

## Related Documentation

- [Scheduler Documentation](docs/SCHEDULER.md)
- [AI Mode Documentation](docs/AI_MODE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
