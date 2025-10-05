FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir pymodbus==3.6.4

# Copy application files
COPY modbus_server.py /app/
COPY registers.json /app/

# Expose Modbus TCP port
EXPOSE 502

# Run the mock server
CMD ["python", "modbus_server.py"]
