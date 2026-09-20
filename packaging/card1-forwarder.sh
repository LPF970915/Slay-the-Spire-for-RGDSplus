#!/bin/bash
set -u
if ! mountpoint -q /mnt/sdcard; then
    echo "Slay the Spire: insert card 2 before launching."
    exit 3
fi
APP_DIR=/mnt/sdcard/Ports/SlayTheSpire
if [ ! -f "$APP_DIR/launch.sh" ]; then
    echo "Slay the Spire adapter not found on card 2."
    exit 3
fi
exec /bin/bash "$APP_DIR/launch.sh" "$@"
