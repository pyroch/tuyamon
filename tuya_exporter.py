import json
import os
import sys
import time
import signal
from threading import Thread
from logger import log

import tinytuya
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from wsgiref.simple_server import make_server

# =========================
# CONFIG
# =========================
EXPORTER_PORT = 8757
DEVICES_FILE = "devices.json"

POLL_INTERVAL = 5      # seconds between poolings
MAX_RETRIES = 3        # retries after fail
RETRY_DELAY = 1        # seconds between retries
SOCKET_TIMEOUT = 3

# =========================
# LOAD CONFIG
# =========================
if not os.path.exists(DEVICES_FILE):
    raise RuntimeError("devices.json not found")

with open(DEVICES_FILE, "r", encoding="utf-8") as f:
    DEVICE_CONFIGS = json.load(f)

# =========================
# PROMETHEUS METRICS
# =========================
registry = CollectorRegistry()
metrics = {
    "current": Gauge(
        "tuya_consumption_current",
        "Current in amps",
        ["id", "ip", "name"],
        registry=registry,
    ),
    "power": Gauge(
        "tuya_consumption_power",
        "Power in watts",
        ["id", "ip", "name"],
        registry=registry,
    ),
    "voltage": Gauge(
        "tuya_consumption_voltage",
        "Voltage in volts",
        ["id", "ip", "name"],
        registry=registry,
    ),
}

device_metrics = {}

for d in DEVICE_CONFIGS:
    id = d.get("id")
    product_name = d.get("product_name", "")
    ip = d.get("ip", "")

    if not id or not ip or product_name != "Smart plug":
        log(f"[INFO] Skipping device: {d.get('name', 'Unknown')}")
        continue

    device_metrics[id] = {
        "ip": ip,
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
    product_name = device_config.get("product_name")

    if product_name != "Smart plug" or not ip:
        return

    log.info(f"[INFO] Started polling thread for {name} ({ip})")

    while True:
        success = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                device = tinytuya.OutletDevice(
                    device_config["id"],
                    device_config["ip"],
                    device_config["key"],
                )
                device.set_socketTimeout(SOCKET_TIMEOUT)
                device.set_version(3.5)

                device.updatedps(["18", "19", "20"])
                payload = device.generate_payload(tinytuya.UPDATEDPS)
                device.send(payload)

                data = device.status()
                if "Error" in data:
                    raise RuntimeError(data["Error"])

                device_metrics[id] = {
                    "ip": ip,
                    "name": name,
                    "current": float(data["dps"].get("18", 0)) / 1000.0,
                    "power": float(data["dps"].get("19", 0)) / 10.0,
                    "voltage": float(data["dps"].get("20", 0)) / 10.0,
                }

                success = True
                break

            except Exception as e:
                log(
                    f"[WARN] {name} ({ip}) attempt {attempt}/{MAX_RETRIES} failed: {e}"
                )
                time.sleep(RETRY_DELAY)

        if not success:
            log(f"[ERROR] {name} ({ip}) unreachable after {MAX_RETRIES} retries")
            device_metrics[id] = {
                "ip": ip,
                "name": name,
                "current": float("nan"),
                "power": float("nan"),
                "voltage": float("nan"),
            }

        time.sleep(POLL_INTERVAL)

def start_background_updater():
    started = set()

    for config in DEVICE_CONFIGS:
        id = config.get("id")
        if not id or id in started:
            continue

        Thread(
            target=update_device_metrics,
            args=(config,),
            daemon=True,
        ).start()

        started.add(id)

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
    log("[INFO] Shutdown signal received")
    sys.exit(0)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    log(f"[INFO] Exporter running on http://localhost:{EXPORTER_PORT}/metrics")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    start_background_updater()

    server = make_server("", EXPORTER_PORT, metrics_app)
    server.serve_forever()
