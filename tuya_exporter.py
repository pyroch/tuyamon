import json
import os
import subprocess
import sys
import time
import signal
from threading import Thread

import tinytuya
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from wsgiref.simple_server import make_server

# =========================
# CONFIG
# =========================
EXPORTER_PORT = 8757
TINYTUTYA_CONFIG = "tinytuya.json"
DEVICES_FILE = "devices.json"
POLL_INTERVAL = 5  # seconds

# =========================
# RUN TINYTUYA WIZARD (AUTO)
# =========================
def run_wizard(cfg):
    print("Running tinytuya wizard automatically...")

    result = subprocess.run(
        [sys.executable, '-m', 'tinytuya', 'wizard', '-force', '10.10.1.0/24', '-yes'],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)

    print("Wizard finished")

# =========================
# LOAD CONFIG / BOOTSTRAP
# =========================
if os.path.exists(TINYTUTYA_CONFIG):
    with open(TINYTUTYA_CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # если devices.json нет — запускаем wizard
    if not os.path.exists(DEVICES_FILE):
        run_wizard(cfg)

if not os.path.exists(DEVICES_FILE):
    raise RuntimeError("devices.json not found")

with open(DEVICES_FILE, "r", encoding="utf-8") as f:
    DEVICE_CONFIGS = json.load(f)

# =========================
# PROMETHEUS METRICS
# =========================
registry = CollectorRegistry()
metrics = {
    "current": Gauge("tuya_consumption_current", "Current in amps", ["id", "ip", "name"], registry=registry),
    "power": Gauge("tuya_consumption_power", "Power in watts", ["id", "ip", "name"], registry=registry),
    "voltage": Gauge("tuya_consumption_voltage", "Voltage in volts", ["id", "ip", "name"], registry=registry),
}

device_metrics = {}

for d in DEVICE_CONFIGS:
    device_id = d.get("id")
    product_name = d.get("product_name", "")
    ip = d.get("ip", "")

    # Only Smart plug
    if not device_id or product_name != "Smart plug" or ip == "":
        print(f"[INFO] Skipping device (has no device id, ip, or not a Smart plug): {d.get('name', 'Unknown')}")
        continue

    device_metrics[device_id] = {
        "ip": d.get("ip", "0.0.0.0"),
        "name": d.get("name", "Unknown"),
        "current": float("nan"),
        "power": float("nan"),
        "voltage": float("nan"),
    }

# =========================
# DEVICE POLLING
# =========================
def update_device_metrics(device_config):
    id = device_config["id"]
    ip = device_config["ip"]
    name = device_config["name"]
    key = device_config["key"]
    product_name = device_config.get("product_name", "")
    if product_name != "Smart plug":
        return
    if ip == "":
        return

    versions = [device_config.get("version")] if device_config.get("version") else [3.5, 3.4, 3.3]

    device = tinytuya.OutletDevice(id, ip, key)
    device.set_socketTimeout(3)

    # Get Working version
    for v in versions:
        try:
            device.set_version(float(v))
            device.status()
            break
        except Exception:
            continue

    while True:
        try:
            data = device.status()
            if "dps" in data:
                device_metrics[id] = {
                    "ip": ip,
                    "name": name,
                    "current": float(data["dps"].get("18", 0)) / 1000.0,
                    "power": float(data["dps"].get("19", 0)) / 10.0,
                    "voltage": float(data["dps"].get("20", 0)) / 10.0,
                }
        except Exception as e:
            print(f"[{id}] error: {e}")
            device_metrics[id].update({
                "current": float("nan"),
                "power": float("nan"),
                "voltage": float("nan"),
            })

        time.sleep(POLL_INTERVAL)

def start_background_updater():
    for config in DEVICE_CONFIGS:
        Thread(target=update_device_metrics, args=(config,), daemon=True).start()

# =========================
# WSGI APP
# =========================
def metrics_app(environ, start_response):
    if environ["PATH_INFO"] == "/metrics":
        for id, data in device_metrics.items():
            metrics["current"].labels(id, data["ip"], data["name"]).set(data["current"])
            metrics["power"].labels(id, data["ip"], data["name"]).set(data["power"])
            metrics["voltage"].labels(id, data["ip"], data["name"]).set(data["voltage"])

        payload = generate_latest(registry)
        start_response("200 OK", [("Content-type", CONTENT_TYPE_LATEST)])
        return [payload]

    start_response("404 Not Found", [("Content-type", "text/plain")])
    return [b"Not Found"]

# =========================
# SIGNALS
# =========================
def handle_signal(signum, frame):
    print("Shutdown signal received")
    sys.exit(0)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print(f"Exporter running on http://localhost:{EXPORTER_PORT}/metrics")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    start_background_updater()
    server = make_server("", EXPORTER_PORT, metrics_app)
    server.serve_forever()
