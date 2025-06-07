#!/bin/sh
set -e

PASSFILE="/mosquitto/config/passwordfile"

if [ ! -f "$PASSFILE" ]; then
  if [ -z "$MQTT_USERNAME" ] || [ -z "$MQTT_PASSWORD" ]; then
    echo "MQTT_USERNAME and MQTT_PASSWORD must be set!"
    exit 1
  fi
  echo "Creating Mosquitto password file..."
  mosquitto_passwd -b -c "$PASSFILE" "$MQTT_USERNAME" "$MQTT_PASSWORD"
else
  echo "Mosquitto password file already exists."
fi

exec "$@"