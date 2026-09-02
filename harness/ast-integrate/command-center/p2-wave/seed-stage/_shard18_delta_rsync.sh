#!/usr/bin/env bash
set -u
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
# Delta rsync of shard-18 surfaces. Ignore OOM dirs (AUD-0090 deps).
rsync -a --checksum \
  --exclude AUD-0090 \
  --exclude node_modules \
  --exclude __pycache__ \
  --exclude .git \
  "$SRC/tools/" "$DST/tools/"
rsync -a --checksum "$SRC/marketplace/" "$DST/marketplace/"
mkdir -p "$DST/command-center/lib"
if [ -d "$SRC/command-center/lib" ]; then
  rsync -a --checksum "$SRC/command-center/lib/" "$DST/command-center/lib/"
fi
rsync -a --checksum "$SRC/command-center/p2-wave/seed-stage/" "$DST/command-center/p2-wave/seed-stage/"
rsync -a --checksum "$SRC/command-center/p2-wave/_measure_one_delivered.py" "$DST/command-center/p2-wave/_measure_one_delivered.py"
while IFS= read -r id; do
  [ -z "$id" ] && continue
  rsync -a --checksum "$SRC/command-center/p2-wave/probes/$id/" "$DST/command-center/p2-wave/probes/$id/"
done < "$SRC/command-center/p2-wave/seed-stage/_shard18_ids.txt"
rsync -a --checksum "$SRC/command-center/adversarial/" "$DST/command-center/adversarial/"
rsync -a --checksum "$SRC/command-center/receipts/" "$DST/command-center/receipts/"
rsync -a --checksum "$SRC/command-center/research/" "$DST/command-center/research/"
rsync -a --checksum "$SRC/command-center/audit/" "$DST/command-center/audit/"
rsync -a --checksum "$SRC/command-center/phase3/" "$DST/command-center/phase3/"
rsync -a --checksum "$SRC/command-center/wfa/" "$DST/command-center/wfa/"
rsync -a --checksum "$SRC/command-center/foundry/" "$DST/command-center/foundry/"
rsync -a --checksum "$SRC/command-center/design/council/" "$DST/command-center/design/council/"
rsync -a --checksum "$SRC/skills/four-voice-prompt/" "$DST/skills/four-voice-prompt/"
rsync -a --checksum "$SRC/council/" "$DST/council/"
rsync -a --checksum "$SRC/bench/" "$DST/bench/"
rsync -a --checksum "$SRC/router/" "$DST/router/"
echo DELTA-RSYNC-OK
