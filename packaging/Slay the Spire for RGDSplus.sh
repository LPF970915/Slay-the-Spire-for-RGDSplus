#!/bin/bash
set -u
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/SlayTheSpire" && pwd -P) || exit 1
exec "$APP_DIR/launch.sh" "$@"
