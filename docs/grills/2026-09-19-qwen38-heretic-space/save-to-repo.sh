#!/usr/bin/env bash
# Sync the grill folder into the toolchain repo branch and push, so a Codespace interruption loses nothing.
# Usage: save-to-repo.sh [--once]   (default: loop every 5 minutes)
set -u
SRC=/home/codespace/grills/2026-09-19-qwen38-heretic-space
REPO=/workspaces/agent-skills-toolchain
DST=docs/grills/2026-09-19-qwen38-heretic-space
BRANCH=grill/qwen38-heretic-space-2026-09-19
MEM=/home/codespace/.claude/projects/-workspaces-agent-skills-toolchain/memory
save_once() {
  mkdir -p "$SRC/claude-memory-snapshot"
  cp -f "$MEM"/*.md "$SRC/claude-memory-snapshot/" 2>/dev/null || true
  rsync -a --delete --exclude 'workflow-journal-*.jsonl.tmp' "$SRC/" "$REPO/$DST/"
  cd "$REPO" || return 1
  [ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || { echo "not on $BRANCH; skipping"; return 1; }
  git add -A -- "$DST"
  if git diff --cached --quiet; then echo "$(date -u +%H:%M:%SZ) no changes"; return 0; fi
  git -c user.useConfigOnly=false commit --quiet -m "docs(grills): auto-sync qwen38-heretic grill artifacts $(date -u +%Y-%m-%dT%H:%MZ)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push --quiet origin "$BRANCH" && echo "$(date -u +%H:%M:%SZ) pushed $(git rev-parse --short HEAD)"
}
if [ "${1:-}" = "--once" ]; then save_once; exit $?; fi
while true; do save_once; sleep 300; done
