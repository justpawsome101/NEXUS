from flask import Flask, render_template, request, jsonify
import threading
import time
import json
import paho.mqtt.client as mqtt
import requests as req

app = Flask(__name__)

INTERNAL_TOKEN = "eff92ab3d1f4c8e7b2a09d3f6e1c5b8a"

# MISCONFIGURATION M4: MQTT credentials in plaintext runtime config
# Returned by debug endpoint — never disabled in production
RUNTIME_CONFIG = {
    "environment": "production",
    "version": "2.4.1",
    "debug": True,
    "mqtt": {
        "broker": "mqtt-broker",
        "port": 1883,
        "username": "iotadmin",
        "password": "Str0ngP@ss!",
        "base_topic": "devices/#"
    },
    "api": {
        "internal_host": "api-service",
        "internal_port": 8080,
        "token": INTERNAL_TOKEN
    }
}

# ── Live device state cache ──────────────────────────
# Updated by background MQTT subscriber thread
device_state = {
    "thermostat-01": {
        "online": False,
        "temperature": None,
        "setpoint": None,
        "humidity": None,
        "mode": None,
        "last_seen": None,
    },
    "pump-ctrl-01": {
        "online": False,
        "flow_rate": None,
        "pressure": None,
        "motor_rpm": None,
        "valve_state": None,
        "last_seen": None,
    }
}
state_lock = threading.Lock()


def mqtt_on_connect(c, u, f, rc):
    if rc == 0:
        c.subscribe("devices/+/status")


def mqtt_on_message(c, u, msg):
    try:
        data = json.loads(msg.payload.decode())
        device_id = data.get("device_id")
        if not device_id or device_id not in device_state:
            return
        with state_lock:
            device_state[device_id]["online"] = data.get("online", True)
            device_state[device_id]["last_seen"] = int(time.time())
            if device_id == "thermostat-01":
                device_state[device_id]["temperature"] = data.get("temperature")
                device_state[device_id]["setpoint"]    = data.get("setpoint")
                device_state[device_id]["humidity"]    = data.get("humidity")
                device_state[device_id]["mode"]        = data.get("mode")
            elif device_id == "pump-ctrl-01":
                device_state[device_id]["flow_rate"]   = data.get("flow_rate")
                device_state[device_id]["pressure"]    = data.get("pressure")
                device_state[device_id]["motor_rpm"]   = data.get("motor_rpm")
                device_state[device_id]["valve_state"] = data.get("valve_state")
            # If device publishes online: False it's shutting down
            if data.get("online") is False:
                device_state[device_id]["online"] = False
    except Exception:
        pass


def mqtt_stale_checker():
    """Mark devices offline if no message received in 15 seconds."""
    while True:
        time.sleep(5)
        now = int(time.time())
        with state_lock:
            for dev_id, state in device_state.items():
                if state["last_seen"] and (now - state["last_seen"]) > 15:
                    state["online"] = False


def start_mqtt_subscriber():
    client = mqtt.Client(client_id="nexus-webapp", protocol=mqtt.MQTTv311)
    client.username_pw_set("iotadmin", "Str0ngP@ss!")
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    while True:
        try:
            client.connect("mqtt-broker", 1883, keepalive=30)
            client.loop_forever()
        except Exception:
            time.sleep(5)


# Start background threads
threading.Thread(target=start_mqtt_subscriber, daemon=True).start()
threading.Thread(target=mqtt_stale_checker, daemon=True).start()


# ── Public routes ────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        error = "Invalid credentials. Please contact your building manager."
    return render_template("login.html", error=error)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/portal/device-status")
def device_status():
    """Live device status polled by homepage JavaScript every 3 seconds."""
    with state_lock:
        return jsonify(device_state)


# ── Internal admin routes ────────────────────────────
# Blocked by proxy ACL for direct requests.
# Reachable only via HTTP Request Smuggling (TE.CL) — Stage 3.

@app.route("/nx-internal/devicemanager/runtime-cfg")
def admin_config():
    """
    MISCONFIGURATION M4: debug config endpoint left in production.
    Returns plaintext MQTT credentials and internal token.
    Requires X-Internal-Token header (recovered from git history in Stage 2).
    """
    token = request.headers.get("X-Internal-Token", "")
    if token != INTERNAL_TOKEN:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(RUNTIME_CONFIG), 200


@app.route("/nx-internal/devicemanager/health")
def admin_health():
    token = request.headers.get("X-Internal-Token", "")
    if token != INTERNAL_TOKEN:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"status": "ok", "uptime": "3d 14h 22m"}), 200


# ── API proxy routes ─────────────────────────────────
# Player discovers these via ffuf in Stage 5.

@app.route("/v2/devices/<path:subpath>", methods=["GET", "POST"])
def devices_proxy(subpath):
    token = request.headers.get("X-Internal-Token", "")
    if token != INTERNAL_TOKEN:
        return jsonify({"error": "Forbidden"}), 403
    url = f"http://api-service:8080/v2/devices/{subpath}"
    if request.method == "POST":
        r = req.post(url, json=request.get_json(),
                     headers={"X-Internal-Token": token})
    else:
        r = req.get(url, headers={"X-Internal-Token": token})
    return r.content, r.status_code, {"Content-Type": r.headers["Content-Type"]}


# ── Static .git serving ──────────────────────────────
import os
from flask import send_from_directory

@app.route("/.git/", defaults={"filename": ""})
@app.route("/.git/<path:filename>")
def serve_git(filename):
    git_dir = os.path.join(app.root_path, "static", ".git")

    try:
        return send_from_directory(git_dir, filename)
    except Exception:
        try:
            files = os.listdir(git_dir)
            links = "".join(f'<a href="{f}">{f}</a><br>' for f in sorted(files))
            return f"<html><body>{links}</body></html>", 200
        except Exception:
            return "Not found", 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
