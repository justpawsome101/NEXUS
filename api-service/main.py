from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
import paho.mqtt.publish as publish
import json

app = FastAPI(docs_url=None, redoc_url=None)  # disable docs in prod

# same static token as web app — no scope separation
INTERNAL_TOKEN = "eff92ab3d1f4c8e7b2a09d3f6e1c5b8a"
MQTT_BROKER    = "mqtt-broker"
MQTT_PORT      = 1883
MQTT_USER      = "iotadmin"
MQTT_PASS      = "Str0ngP@ss!"

DEVICES = {
    "thermostat-01": {
        "name": "thermostat-01",
        "type": "smart_thermostat",
        "location": "Crestline Tower, floors 18-24",
        "status_topic": "devices/thermostat-01/status",
        "cmd_topic": "devices/thermostat-01/cmd",
        "config_topic": "devices/thermostat-01/config",
    },
    "pump-ctrl-01": {
        "name": "pump-ctrl-01",
        "type": "pump_controller",
        "location": "Crestline Tower, upper floor plant room",
        "status_topic": "devices/pump-ctrl-01/status",
        "cmd_topic": "devices/pump-ctrl-01/cmd",
        "config_topic": "devices/pump-ctrl-01/config",
    },
}


def verify_token(x_internal_token: str = Header(default="")):
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return x_internal_token


class CommandPayload(BaseModel):
    action: str
    params: dict = {}


@app.get("/v2/devices/list")
def list_devices(token=Depends(verify_token)):
    """
    Stage 5: discovered via ffuf enumeration.
    Returns device inventory for Crestline Tower.
    """
    return {"devices": list(DEVICES.values())}


@app.post("/v2/devices/{device_id}/cmd")
def send_command(device_id: str, payload: CommandPayload, token=Depends(verify_token)):
    """
    Stage 5: proxies command payload directly to MQTT.
    MISCONFIGURATION: no per-device authorisation, no rate limiting,
    no command allowlist — any action string is forwarded.
    """
    if device_id not in DEVICES:
        raise HTTPException(status_code=404, detail="Device not found")

    cmd_topic = DEVICES[device_id]["cmd_topic"]
    message   = json.dumps({"action": payload.action, **payload.params})

    try:
        publish.single(
            cmd_topic,
            payload=message,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth={"username": MQTT_USER, "password": MQTT_PASS},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MQTT publish failed: {e}")

    return {"status": "sent", "device": device_id, "topic": cmd_topic, "payload": message}


@app.get("/health")
def health():
    return {"status": "ok"}
