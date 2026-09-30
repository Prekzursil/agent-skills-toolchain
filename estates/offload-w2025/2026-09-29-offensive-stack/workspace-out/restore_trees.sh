#!/bin/bash
# restore_trees.sh - materialize the locally-empty trees from origin/main.
# Safety: only paths with ZERO local files are checked out; nothing local is overwritten.
cd /c/Users/prekzursil/source/agent-skills-toolchain
DIRS="command-center .github .quality docs hooks ci agent-self .agents .claude-plugin browser-profiles agents commands guides harness harness-audits harness-sota-2026-07-18-corpus browser-bridge out .claude"
for d in $DIRS; do
  n=$(find "$d" -type f 2>/dev/null | wc -l)
  echo "$d local-files=$n"
  if [ "$n" = "0" ]; then
    if git cat-file -e "origin/main:$d" 2>/dev/null; then
      git checkout origin/main -- "$d" && echo "  -> restored from origin/main"
    else
      echo "  -> not present on origin/main (skipped)"
    fi
  fi
done
echo ===AFTER===
for d in $DIRS; do
  echo "$d files=$(find "$d" -type f 2>/dev/null | wc -l)"
done
