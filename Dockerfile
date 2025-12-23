# Base python alpine image
FROM python:alpine

# App working dir
WORKDIR /app

# Move requirements to working dir
COPY requirements.txt .

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy main script to work dir
COPY tuya_exporter.py .
COPY logger.py .

# Healthcheck for port 8757
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD /bin/bash -c "timeout 2 bash -c '</dev/tcp/localhost/8757'" || exit 1

# Run command
CMD ["python", "-u", "tuya_exporter.py"]