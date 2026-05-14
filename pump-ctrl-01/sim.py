import paho.mqtt.client as mqtt
import json
import time
import random
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pump-ctrl-01] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

DEVICE_ID    = "pump-ctrl-01"
BROKER       = "mqtt-broker"
PORT         = 1883
USERNAME     = "pump-ctrl-01"
PASSWORD     = "pumpSecret99"

TOPIC_STATUS = f"devices/{DEVICE_ID}/status"
TOPIC_CMD    = f"devices/{DEVICE_ID}/cmd"
TOPIC_CONFIG = f"devices/{DEVICE_ID}/config"

#  retained config published on boot, no TTL
DEVICE_CONFIG = {
    "device_id":         DEVICE_ID,
    "type":              "pump_controller",
    "firmware":          "v2.1",
    "location":          "Crestline Tower, upper floor plant room",
    "poll_interval_s":   5,
    "supported_cmds":    ["status", "reboot", "shutdown", "set_pressure", "toggle_valve"],
    "payload_format":    {"action": "<cmd>"},
    "telemetry_fields":  ["flow_rate", "pressure", "motor_rpm", "valve_state"],
    "nominal": {
        "pressure_bar":  3.2,
        "flow_lpm":      42.0,
        "motor_rpm":     2850,
    }
}

state = {
    "flow_rate":   42.0,
    "pressure":    3.2,
    "motor_rpm":   2850,
    "valve_state": "open",
    "online":      True,
}

client = mqtt.Client(client_id=DEVICE_ID, protocol=mqtt.MQTTv311)


def publish_config(c):
    """Publish retained capability profile on boot."""
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
        "flow_rate":   round(state["flow_rate"]  + random.uniform(-0.8, 0.8), 2),
        "pressure":    round(state["pressure"]   + random.uniform(-0.05, 0.05), 3),
        "motor_rpm":   int(state["motor_rpm"]    + random.randint(-15, 15)),
        "valve_state": state["valve_state"],
        "timestamp":   int(time.time()),
    }
    c.publish(TOPIC_STATUS, payload=json.dumps(payload), qos=0)
    log.info(
        "Status → flow=%.1f lpm  pressure=%.2f bar  rpm=%d  valve=%s",
        payload["flow_rate"], payload["pressure"],
        payload["motor_rpm"], payload["valve_state"]
    )


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
    Any authenticated broker user may publish any supported action.
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
        c.disconnect()
        time.sleep(3)
        c.reconnect()

    elif action == "shutdown":
        log.warning("SHUTDOWN command received — pump controller going offline")
        c.publish(
            TOPIC_STATUS,
            payload=json.dumps({
                "device_id":   DEVICE_ID,
                "flow_rate":   0.0,
                "pressure":    0.0,
                "motor_rpm":   0,
                "valve_state": "closed",
                "online":      False,
                "reason":      "shutdown command received",
                "timestamp":   int(time.time()),
            }),
            qos=1,
        )
        time.sleep(0.5)
        c.disconnect()
        log.warning("pump-ctrl-01 offline — upper floor water pressure lost")
        sys.exit(0)

    elif action == "set_pressure":
        target = data.get("target_bar")
        if target is not None:
            state["pressure"] = float(target)
            log.info("Pressure target updated to %.2f bar", state["pressure"])

    elif action == "toggle_valve":
        state["valve_state"] = "closed" if state["valve_state"] == "open" else "open"
        log.info("Valve toggled to %s", state["valve_state"])
        if state["valve_state"] == "closed":
            state["flow_rate"]  = 0.0
            state["motor_rpm"]  = 0
        else:
            state["flow_rate"]  = 42.0
            state["motor_rpm"]  = 2850

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

    log.info("pump-ctrl-01 online — streaming telemetry every 5s")
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
