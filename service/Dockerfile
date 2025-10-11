FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py modbus_client.py heating_curve.py adaptive_controller.py scheduler.py /app/
COPY heating_curve_config.json schedule.json /app/

# Expose FastAPI port
EXPOSE 8000

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
