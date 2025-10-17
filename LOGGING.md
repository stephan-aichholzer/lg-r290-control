# Logging & Monitoring Reference

## Two Scripts Available

### 1. `./logs.sh` - Log Management
```bash
./logs.sh              # Tail all logs
./logs.sh tail service # Tail API only
./logs.sh dump         # Dump all to console
./logs.sh save         # Save to timestamped folder
./logs.sh errors       # Show only errors/warnings
./logs.sh search "AI"  # Search for pattern
./logs.sh stats        # Show statistics
./logs.sh help         # Show help
```

### 2. `./monitor.sh` - Live Monitoring
```bash
./monitor.sh           # Full dashboard (refreshes every 5s)
./monitor.sh temps     # Temperature monitoring
./monitor.sh ai        # AI Mode status
./monitor.sh once      # One-time snapshot
./monitor.sh containers# Container status
./monitor.sh help      # Show help
```

## Common Usage

```bash
# Check what's happening
./monitor.sh once

# Watch logs live
./logs.sh tail service

# Find issues
./logs.sh errors

# Search for something
./logs.sh search "temperature"
./logs.sh search "Modbus"
./logs.sh search "AI Mode"

# Save logs for analysis
./logs.sh save

# Monitor temperatures
./monitor.sh temps
```

## Traditional Docker Commands

```bash
docker-compose ps              # Container status
docker-compose logs -f         # Follow all logs
docker stats                   # Resource usage
docker-compose restart         # Restart services
```

## Log Levels

- **INFO** - Normal operations
- **WARNING** - Recoverable issues
- **ERROR** - Failures
- **DEBUG** - Detailed info (set LOG_LEVEL=DEBUG)
