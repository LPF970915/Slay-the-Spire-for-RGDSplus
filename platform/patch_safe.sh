#!/bin/bash
set -eu

GAMEDIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
INPUT_ZIP=${1:-"$GAMEDIR/desktop-1.0.jar"}
OUTPUT_ZIP=${2:?output jar path is required}
WORK_DIR=${3:?work directory is required}
XDELTA=${XDELTA3:-xdelta3}
PYTHON=${PYTHON3:-python3}
if [ -z "${XDELTA3:-}" ] && [ -x "$GAMEDIR/tools/xdelta3" ]; then
    XDELTA="$GAMEDIR/tools/xdelta3"
fi
export LD_LIBRARY_PATH="$GAMEDIR/tools/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

for command in unzip zip "$XDELTA" "$PYTHON"; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "[patch] missing tool: $command" >&2
        exit 127
    }
done

[ -f "$INPUT_ZIP" ] || {
    echo "[patch] missing source: $INPUT_ZIP" >&2
    exit 2
}

mkdir -p "$WORK_DIR/assets"
CLEANED_ZIP="$WORK_DIR/cleaned.zip"
PATCHED_ZIP="$WORK_DIR/patched.zip"

echo "[patch] extracting assets"
unzip -q "$INPUT_ZIP" "font/*" "images/*" "audio/*" -d "$WORK_DIR/assets"
"$PYTHON" "$GAMEDIR/tools/ogg.py" "$WORK_DIR/assets/audio" \
    -b 12 --resample 11025 --downmix -v

echo "[patch] creating clean source copy"
cp "$INPUT_ZIP" "$CLEANED_ZIP"
(
    cd "$WORK_DIR"
    zip -q -d "$CLEANED_ZIP" "font/*" "images/*" "audio/*"
)

echo "[patch] applying xdelta"
"$XDELTA" -d -s "$CLEANED_ZIP" "$GAMEDIR/tools/steam.xdelta" "$PATCHED_ZIP"
rm -f "$CLEANED_ZIP"

# The desktop JAR carries an ARM OpenAL build that depends on libsndio,
# which is absent on RGDSplus. Keep the resource name required by LibGDX, but
# replace its contents with the firmware's compatible OpenAL implementation.
(
    cd "$WORK_DIR"
    zip -q -d "$PATCHED_ZIP" \
        "libopenal.so" "libopenal64.so"
    cp -fL /usr/lib/libopenal.so.1 "$WORK_DIR/libopenal.so"
    zip -q "$PATCHED_ZIP" "libopenal.so"
    rm -f "$WORK_DIR/libopenal.so"
)

echo "[patch] adding processed assets"
cp "$GAMEDIR/libgdx-controllers-desktop.so" "$WORK_DIR/assets/"
(
    cd "$WORK_DIR/assets"
    zip -q -r "$PATCHED_ZIP" font images audio libgdx-controllers-desktop.so
)

unzip -tq "$PATCHED_ZIP" >/dev/null
mkdir -p "$(dirname -- "$OUTPUT_ZIP")"
mv "$PATCHED_ZIP" "$OUTPUT_ZIP"
echo "[patch] committed $OUTPUT_ZIP"
