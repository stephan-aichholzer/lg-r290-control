FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared Modbus library from project root
COPY lg_r290_modbus.py /app/
COPY monitor_and_keep_alive.py /app/

# Copy application files
COPY service/main.py service/heating_curve.py service/adaptive_controller.py service/scheduler.py /app/
COPY service/heating_curve_config.json service/schedule.json /app/
COPY service/start.sh /app/

# Make start script executable
RUN chmod +x /app/start.sh

# Expose FastAPI port
EXPOSE 8000

# Run via startup script (starts monitor + FastAPI)
CMD ["/app/start.sh"]
