FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (procps for ps/pgrep/pkill)
RUN apt-get update && \
    apt-get install -y --no-install-recommends procps && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared Modbus library from project root
COPY lg_r290_modbus.py /app/
COPY monitor_and_keep_alive.py /app/

# Copy application files
COPY service/main.py service/scheduler.py /app/
COPY service/config.json service/schedule.json /app/
COPY service/start.sh /app/
COPY service/healthcheck.sh /app/

# Make scripts executable
RUN chmod +x /app/start.sh /app/healthcheck.sh

# Expose FastAPI port
EXPOSE 8000

# Health check - verifies monitor daemon is alive by checking status.json timestamp
# File is created at startup, then updated every 10s by monitor daemon
# If file becomes stale (>60s), daemon crashed and container will restart
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["/app/healthcheck.sh"]

# Run via startup script (starts monitor + FastAPI)
CMD ["/app/start.sh"]
