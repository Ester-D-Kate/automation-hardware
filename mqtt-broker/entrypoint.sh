#!/bin/sh
set -e

PASSFILE="/mosquitto/config/passwordfile"

# Always generate passwordfile from env
if [ -n "$MQTT_USERNAME" ] && [ -n "$MQTT_PASSWORD" ]; then
  echo "Creating/updating Mosquitto password file..."
  mosquitto_passwd -b -c "$PASSFILE" "$MQTT_USERNAME" "$MQTT_PASSWORD"
else
  echo "MQTT_USERNAME and MQTT_PASSWORD env vars must be set!"
  exit 1
fi

exec "$@"