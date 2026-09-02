#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
rsync -a "$SRC/command-center/p2-wave/_g1_shard17_refresh_sha.py" "$DST/command-center/p2-wave/_g1_shard17_refresh_sha.py"
rsync -a "$SRC/command-center/p2-wave/_g1_shard17_run.py" "$DST/command-center/p2-wave/_g1_shard17_run.py"
mkdir -p "$DST/command-center/blueprints/security"
rsync -a --exclude __pycache__ "$SRC/command-center/blueprints/security/" "$DST/command-center/blueprints/security/"
mkdir -p "$DST/tools/discovery"
rsync -a --exclude __pycache__ "$SRC/tools/discovery/" "$DST/tools/discovery/"
mkdir -p "$DST/command-center/p2-wave/probes/IMP-0245/fixtures"
rsync -a "$SRC/command-center/p2-wave/probes/IMP-0245/fixtures/" "$DST/command-center/p2-wave/probes/IMP-0245/fixtures/"
mkdir -p "$DST/tools/package_gate"
if [ -d "$SRC/tools/package_gate" ]; then
  rsync -a --exclude __pycache__ "$SRC/tools/package_gate/" "$DST/tools/package_gate/"
fi
mkdir -p "$DST/tools/artifact_cache"
if [ -d "$SRC/tools/artifact_cache" ]; then
  rsync -a --exclude __pycache__ "$SRC/tools/artifact_cache/" "$DST/tools/artifact_cache/"
fi
mkdir -p "$DST/tools/council/participants"
if [ -d "$SRC/tools/council/participants" ]; then
  rsync -a --exclude __pycache__ "$SRC/tools/council/participants/" "$DST/tools/council/participants/"
fi
mkdir -p "$DST/command-center/lib/evidence_snapshot"
if [ -d "$SRC/command-center/lib/evidence_snapshot" ]; then
  rsync -a --exclude __pycache__ "$SRC/command-center/lib/evidence_snapshot/" "$DST/command-center/lib/evidence_snapshot/"
fi
# retire stub modules that block packages
if [ -f "$DST/tools/discovery.py" ]; then
  mkdir -p "$DST/command-center/p2-wave/_retired-mods"
  mv -f "$DST/tools/discovery.py" "$DST/command-center/p2-wave/_retired-mods/discovery.py.stub"
fi
if [ -f "$DST/tools/artifact_cache.py" ]; then
  mkdir -p "$DST/command-center/p2-wave/_retired-mods"
  mv -f "$DST/tools/artifact_cache.py" "$DST/command-center/p2-wave/_retired-mods/artifact_cache.py.stub"
fi
if [ -f "$DST/tools/package_gate.py" ]; then
  mkdir -p "$DST/command-center/p2-wave/_retired-mods"
  mv -f "$DST/tools/package_gate.py" "$DST/command-center/p2-wave/_retired-mods/package_gate.py.stub"
fi
if [ -f "$DST/command-center/lib/evidence_snapshot.py" ]; then
  mkdir -p "$DST/command-center/p2-wave/_retired-mods"
  mv -f "$DST/command-center/lib/evidence_snapshot.py" "$DST/command-center/p2-wave/_retired-mods/evidence_snapshot.py.stub"
fi
echo DELTA-OK
