import paho.mqtt.client as mqtt
import json
import time
import random
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [thermostat-01] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

DEVICE_ID    = "thermostat-01"
BROKER       = "mqtt-broker"
PORT         = 1883
USERNAME     = "thermostat-01"
PASSWORD     = "th3rm0Secret"

TOPIC_STATUS = f"devices/{DEVICE_ID}/status"
TOPIC_CMD    = f"devices/{DEVICE_ID}/cmd"
TOPIC_CONFIG = f"devices/{DEVICE_ID}/config"

DEVICE_CONFIG = {
    "device_id":         DEVICE_ID,
    "type":              "smart_thermostat",
    "firmware":          "v2.1",
    "location":          "Crestline Tower, floors 18-24",
    "poll_interval_s":   5,
    "supported_cmds":    ["status", "reboot", "shutdown", "update_config"],
    "payload_format":    {"action": "<cmd>"},
    "telemetry_fields":  ["temperature", "setpoint", "humidity", "mode"],
}

state = {
    "temperature": 21.4,
    "setpoint":    21.0,
    "humidity":    48.0,
    "mode":        "heat",
    "online":      True,
}

client = mqtt.Client(client_id=DEVICE_ID, protocol=mqtt.MQTTv311)


def publish_config(c):
    """Publish retained capability profile on connect."""
    c.publish(
        TOPIC_CONFIG,
        payload=json.dumps(DEVICE_CONFIG),
        qos=1,
        retain=True,   
    )
    log.info("Published retained config to %s", TOPIC_CONFIG)


def publish_status(c):
    payload = {
        "device_id":   DEVICE_ID,
        "temperature": round(state["temperature"] + random.uniform(-0.3, 0.3), 2),
        "setpoint":    state["setpoint"],
        "humidity":    round(state["humidity"] + random.uniform(-0.5, 0.5), 2),
        "mode":        state["mode"],
        "timestamp":   int(time.time()),
    }
    c.publish(TOPIC_STATUS, payload=json.dumps(payload), qos=0)
    log.info("Status → temp=%.1f°C  setpoint=%.1f°C  humidity=%.1f%%  mode=%s",
             payload["temperature"], payload["setpoint"],
             payload["humidity"], payload["mode"])


def on_connect(c, userdata, flags, rc):
    if rc == 0:
        log.info("Connected to broker")
        publish_config(c)
        c.subscribe(TOPIC_CMD, qos=1)
        log.info("Subscribed to %s", TOPIC_CMD)
    else:
        log.error("Connection refused — rc=%d", rc)
        if rc == 5:
            log.error("CONNACK rc=5: credentials revoked — operator intervention required")
        sys.exit(1)


def on_disconnect(c, userdata, rc):
    if rc != 0:
        log.warning("Unexpected disconnect rc=%d — attempting reconnect", rc)


def on_message(c, userdata, msg):
    """
    MISCONFIGURATION M8: no command signing or sender verification.
    Any authenticated broker user publishing to this topic with a valid
    action string will have that command executed immediately.
    """
    raw = msg.payload.decode("utf-8", errors="replace")
    log.info("Command received on %s: %s", msg.topic, raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Malformed command payload — ignoring")
        return

    action = data.get("action", "").lower()

    if action == "status":
        publish_status(c)

    elif action == "reboot":
        log.warning("REBOOT command received — restarting simulator")
        time.sleep(1)
      
        c.disconnect()
        time.sleep(3)
        c.reconnect()

    elif action == "shutdown":
        log.warning("SHUTDOWN command received — device going offline")
        c.publish(
            TOPIC_STATUS,
            payload=json.dumps({
                "device_id": DEVICE_ID,
                "online":    False,
                "reason":    "shutdown command received",
                "timestamp": int(time.time()),
            }),
            qos=1,
        )
        time.sleep(0.5)
        c.disconnect()
        log.warning("thermostat-01 offline — climate control for floors 18-24 lost")
        sys.exit(0)

    elif action == "update_config":
        params = data.get("params", {})
        if "setpoint" in params:
            state["setpoint"] = float(params["setpoint"])
            log.info("Setpoint updated to %.1f°C", state["setpoint"])
        if "mode" in params:
            state["mode"] = params["mode"]
            log.info("Mode updated to %s", state["mode"])

    else:
        log.warning("Unknown action '%s' — ignoring", action)


def main():
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    log.info("Connecting to broker %s:%d", BROKER, PORT)

    connected = False
    for attempt in range(10):
        try:
            client.connect(BROKER, PORT, keepalive=60)
            connected = True
            break
        except Exception as e:
            log.warning("Connection attempt %d failed: %s — retrying in 5s", attempt + 1, e)
            time.sleep(5)

    if not connected:
        log.error("Could not connect to broker after 10 attempts — exiting")
        sys.exit(1)

    client.loop_start()

    log.info("thermostat-01 online — streaming telemetry every 5s")
    try:
        while True:
            publish_status(client)
            time.sleep(5)
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
