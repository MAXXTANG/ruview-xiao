#!/usr/bin/env bash
# Flash prebuilt RuView-XIAO firmware. Usage: ./tools/flash.sh <s3|c6|c5> <port>
set -euo pipefail
# Usage: flash.sh <s3|c6|c5> <port> [bin-dir]
# bin-dir defaults to ./prebuilt/<board> or ./<board> (e.g. an extracted release zip).
BOARD="${1:?usage: flash.sh <s3|c6|c5> <port> [bin-dir]}"
PORT="${2:?usage: flash.sh <s3|c6|c5> <port> [bin-dir]}"
DIR="${3:-}"
if [ -z "$DIR" ]; then
  for cand in "./prebuilt/$BOARD" "./$BOARD" "$(cd "$(dirname "$0")/.." && pwd)/prebuilt/$BOARD"; do
    [ -f "$cand/esp32-csi-node.bin" ] && { DIR="$cand"; break; }
  done
fi
[ -n "$DIR" ] && [ -f "$DIR/esp32-csi-node.bin" ] || {
  echo "no binaries for '$BOARD'. Download a release zip, extract it, and pass its dir:"
  echo "  ./tools/flash.sh $BOARD $PORT path/to/$BOARD"; exit 1; }

case "$BOARD" in
  s3) CHIP=esp32s3; BOOT=0x0;    MODE="--flash_mode dio  --flash_freq 80m --flash_size 8MB" ;;
  c6) CHIP=esp32c6; BOOT=0x2000; MODE="--flash_mode dio  --flash_freq 80m --flash_size 4MB" ;;
  c5) CHIP=esp32c5; BOOT=0x2000; MODE="--flash_mode dout --flash_freq 40m --flash_size 4MB" ;;  # C5 Puya flash
  *)  echo "unknown board '$BOARD'"; exit 1 ;;
esac

# C5 in a crash-loop may need a few connection retries (USB-JTAG reset).
exec python -m esptool --chip "$CHIP" -p "$PORT" -b 230400 \
  --before default-reset --after hard-reset write-flash $MODE \
  "$BOOT" "$DIR/bootloader.bin" \
  0x8000 "$DIR/partition-table.bin" \
  0xf000 "$DIR/ota_data_initial.bin" \
  0x20000 "$DIR/esp32-csi-node.bin"
