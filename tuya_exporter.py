import json
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from wsgiref.simple_server import make_server
import tinytuya
from threading import Thread

# Exporter Configuration
EXPORTER_PORT = 8757

# Device Configuration
with open('config.json', "r", encoding="utf-8") as json_file:
    DEVICE_CONFIGS = json.load(json_file)

# Prometheus Metrics
registry = CollectorRegistry()
metrics = {
    "current": Gauge("tuya_consumption_current", "Current in amps.", ["device_id", "ip", "name"], registry=registry),
    "power": Gauge("tuya_consumption_power", "Power in watts.", ["device_id", "ip", "name"], registry=registry),
    "voltage": Gauge("tuya_consumption_voltage", "Voltage in volts.", ["device_id", "ip", "name"], registry=registry),
}

device_metrics = {
    config["device_id"]: {
        "ip": config["ip"],
        "name": config["name"],
        "current": float("nan"),
        "power": float("nan"),
        "voltage": float("nan"),
    }
    for config in DEVICE_CONFIGS
}

def update_device_metrics(device_config):
    """Continuously fetch metrics for a device in the background."""
    device_id = device_config["device_id"]
    ip = device_config["ip"]
    name = device_config["name"]
    while True:
        try:
            device = tinytuya.OutletDevice(device_config["device_id"], device_config["ip"], device_config["local_key"])
            device.set_socketTimeout(3)
            for version in [3.5, 3.4, 3.3]:
                try:
                    device.set_version(version)
                    device.updatedps(["18", "19", "20"])
                    payload = device.generate_payload(tinytuya.UPDATEDPS)
                    device.send(payload)
                    data = device.status()
                    if "Error" not in data:
                        device_metrics[device_id] = {
                            "ip": ip,
                            "name": name,
                            "current": float(data["dps"].get("18", 0)) / 1000.0,
                            "power": float(data["dps"].get("19", 0)) / 10.0,
                            "voltage": float(data["dps"].get("20", 0)) / 10.0,
                        }
                        break
                except Exception:
                    continue
            else:
                raise Exception(f"Failed to connect to device {device_id}")
        except Exception as e:
            print(f"Error updating device {device_id}: {e}")
            device_metrics[device_id] = {
                "ip": ip,
                "name": name,
                "current": float("nan"),
                "power": float("nan"),
                "voltage": float("nan"),
            }
        #time.sleep(1)

def start_background_updater():
    """Start background threads to update metrics for all devices."""
    for config in DEVICE_CONFIGS:
        Thread(target=update_device_metrics, args=(config,), daemon=True).start()

def metrics_app(environ, start_response):
    """WSGI application for Prometheus metrics."""
    if environ["PATH_INFO"] == "/metrics":
        for device_id, metrics_data in device_metrics.items():
            ip = metrics_data["ip"]
            name = metrics_data["name"]
            metrics["current"].labels(device_id=device_id, ip=ip, name=name).set(metrics_data["current"])
            metrics["power"].labels(device_id=device_id, ip=ip, name=name).set(metrics_data["power"])
            metrics["voltage"].labels(device_id=device_id, ip=ip, name=name).set(metrics_data["voltage"])
        data = generate_latest(registry)
        start_response("200 OK", [("Content-type", CONTENT_TYPE_LATEST)])
        return [data]
    start_response("404 Not Found", [("Content-type", "text/plain")])
    return [b"Not Found"]

if __name__ == "__main__":
    print(f"Starting server on http://localhost:{EXPORTER_PORT}/metrics")
    start_background_updater()
    try:
        make_server("", EXPORTER_PORT, metrics_app).serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server.")