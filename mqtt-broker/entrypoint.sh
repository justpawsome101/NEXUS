#!/bin/sh
set -e

echo "[mqtt-broker] Generating password file..."


mosquitto_passwd -b -c /mosquitto/config/passwd iotadmin    "Str0ngP@ss!"
mosquitto_passwd -b    /mosquitto/config/passwd thermostat-01 "th3rm0Secret"
mosquitto_passwd -b    /mosquitto/config/passwd pump-ctrl-01  "pumpSecret99"


# A hardened setup would use chmod 600 owned by mosquitto only
chmod 644 /mosquitto/config/passwd
chmod 644 /mosquitto/config/acl

echo "[mqtt-broker] Password file ready. Starting broker..."

exec mosquitto -c /mosquitto/config/mosquitto.conf
