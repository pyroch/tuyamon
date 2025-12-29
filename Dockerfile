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

# Healthcheck for port 8757
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --quiet --spider --tries=1 --timeout=5 http://localhost:8757/metrics || exit 1

# Run command
CMD ["python", "-u", "tuya_exporter.py"]