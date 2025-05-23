Prometheus exporter for tuya sockets via tinytuya
1. Download docker-compose.yml and config.json
wget https://raw.githubusercontent.com/pyroch/tuyamon/refs/heads/main/docker-compose.yml && wget https://raw.githubusercontent.com/pyroch/tuyamon/refs/heads/main/config.json
2. Change config.json
3. Run: docker compose up -d
4. Go to http://localhost:8757/metrics

metrics:
tuya_consumption_current Current in amps.
tuya_consumption_power Power in watts.
tuya_consumption_voltage Voltage in volts.
