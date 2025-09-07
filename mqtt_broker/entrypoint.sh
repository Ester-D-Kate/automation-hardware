#!/bin/sh
set -e

PASSFILE="/mosquitto/config/passwordfile"
echo "Creating/updating Mosquitto password file at $PASSFILE ..."

# If the password file exists, remove it (only if Mosquitto is NOT running yet)
if [ ! -s "$PASSFILE" ]; then
  touch "$PASSFILE"
fi

# Add all users from environment, as many as are set
i=1
while :; do
    USER_VAR="MQTT_USER${i}"
    PASS_VAR="MQTT_PASS${i}"

    USER=$(eval echo "\$$USER_VAR")
    PASS=$(eval echo "\$$PASS_VAR")

    if [ -n "$USER" ] && [ -n "$PASS" ]; then
        if [ $i -eq 1 ]; then
            mosquitto_passwd -b -c "$PASSFILE" "$USER" "$PASS"
        else
            mosquitto_passwd -b "$PASSFILE" "$USER" "$PASS"
        fi
        echo "Added MQTT user: $USER"
    else
        break
    fi
    i=$((i+1))
done

chmod 600 "$PASSFILE"
chown mosquitto:mosquitto "$PASSFILE" || true

exec "$@"