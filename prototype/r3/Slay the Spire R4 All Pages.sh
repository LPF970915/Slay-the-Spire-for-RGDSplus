#!/bin/sh
set -eu
PORTS=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$PORTS/SlayTheSpireDualR4/supervisor.py" "$@"
