#!/bin/bash
# cs-deploy -- install the WSL-side cs-* commands to ~/.local/bin, bring the daemon up, back up.
#
# SRC IS DERIVED, NOT HARDCODED. This file used to open with
#   SRC=/mnt/c/Users/Prekzursil/source/agent-skills-toolchain/scripts/claude-science
# which names a specific checkout on one machine. Measured 2026-08-12: that checkout sits at a
# detached HEAD holding the PRE-FIX tree, so running this script COPIED STALE CODE OVER THE FIXED
# CODE -- cs-backup 4,054 B -> 2,523 B, cs-maintain 4,141 -> 3,615, cs-recover 3,139 -> 2,715 --
# and, because the old list did not know about them, deployed NO cs-lib.sh and NO cs.conf, leaving
# every deployed script sourcing a config file that was not there. It is the same defect that made
# /claude-science run a stale tree, in the one place still holding it.
#
# Deploying from the directory this script lives in is correct by construction: the copy you run is
# the copy you get. CS_SRC overrides for the unusual case of deploying some other tree deliberately.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
SRC="${CS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
DEST="$HOME/.local/bin"
echo "=== deploying from $SRC ==="
mkdir -p "$DEST"

fail=0

# 1. Commands: extension STRIPPED (cs-backup.sh -> the command `cs-backup`), CR-stripped, +x.
#    The list mirrors install.ps1 step 2 exactly; a shorter list here is how four of these scripts
#    came to be three Git-months older than the rest of the tree.
for f in cs-start cs-recover cs-restore cs-backup cs-maintain cs-supervisor cs-install cs-serve-prep cs-finish; do
  if [ ! -f "$SRC/$f.sh" ]; then
    echo "MISSING in source, not deployed: $f.sh"
    fail=1
    continue
  fi
  if tr -d '\r' < "$SRC/$f.sh" > "$DEST/$f" && chmod +x "$DEST/$f"; then
    echo "installed $f"
  else
    echo "FAILED to install $f"
    fail=1
  fi
done

# 2. Config seam: NAME PRESERVED and not executable. cs-lib.sh is sourced BY NAME by every script
#    above (`. "$(dirname "${BASH_SOURCE[0]}")/cs-lib.sh"`), so running it through the strip loop
#    would leave the scripts sourcing a file that does not exist. cs.conf is the SSOT they read.
for f in cs-lib.sh cs.conf; do
  if [ ! -f "$SRC/$f" ]; then
    echo "MISSING in source, not deployed: $f"
    fail=1
    continue
  fi
  if tr -d '\r' < "$SRC/$f" > "$DEST/$f"; then
    echo "installed $f"
  else
    echo "FAILED to install $f"
    fail=1
  fi
done

# 3. Verify the deploy instead of assuming it. A partial deploy is the dangerous state: the
#    commands exist, so PATH lookups succeed, and every one of them then dies on a missing
#    cs-lib.sh at the moment it is needed -- typically inside the weekly maintenance window.
for f in cs-backup cs-maintain cs-restore cs-recover cs-supervisor cs-lib.sh cs.conf; do
  [ -s "$DEST/$f" ] || { echo "VERIFY FAILED: $DEST/$f missing or empty"; fail=1; }
done
if ! bash -n "$DEST/cs-backup" 2>/dev/null; then echo "VERIFY FAILED: deployed cs-backup is not valid bash"; fail=1; fi

if [ "$fail" -ne 0 ]; then
  echo "FAILED:cs-deploy one or more files did not deploy -- fix before relying on cs-backup/cs-maintain"
  exit 1
fi
echo "SUCCESS:cs-deploy all commands + cs-lib.sh + cs.conf installed to $DEST"

echo "=== bring daemon up (pinned) ==="
cs-start 2>&1 | grep -vE 'nonce' | head -8
echo "=== FIRST BACKUP ==="
cs-backup
