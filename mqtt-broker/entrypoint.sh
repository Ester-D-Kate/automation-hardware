#!/bin/sh
set -e

PASSFILE="/mosquitto/config/passwordfile"
echo "Creating/updating Mosquitto password file at $PASSFILE ..."

rm -f "$PASSFILE"  # Always create fresh

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

if [ ! -s "$PASSFILE" ]; then
    echo "No users added! Please set at least MQTT_USER1 and MQTT_PASS1 in your .env."
    exit 1
fi

chmod 600 "$PASSFILE"
chown mosquitto:mosquitto "$PASSFILE" || true

exec "$@"