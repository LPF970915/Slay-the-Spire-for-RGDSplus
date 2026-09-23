#!/bin/sh
set -eu
PORTS=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$PORTS/Slay the Spire for RGDSplus/supervisor.py" --seconds 0 "$@"
