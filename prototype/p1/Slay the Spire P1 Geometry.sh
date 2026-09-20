#!/bin/sh
set -eu
PORTS=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec /bin/sh "$PORTS/SlayTheSpireGeometryP1/launch.sh" "$@"
