#!/usr/bin/env bash
# Sync the grill folder into the toolchain repo branch and push, so a Codespace interruption loses nothing.
# Usage: save-to-repo.sh [--once]   (default: loop every 5 minutes)
# Work-to-do = staged changes OR commits ahead of upstream (a failed push is retried on every pass; never silently dropped).
set -u
SRC=/home/codespace/grills/2026-09-19-qwen38-heretic-space
REPO=/workspaces/agent-skills-toolchain
DST=docs/grills/2026-09-19-qwen38-heretic-space
BRANCH=grill/qwen38-heretic-space-2026-09-19
MEM=/home/codespace/.claude/projects/-workspaces-agent-skills-toolchain/memory
ts() { date -u +%H:%M:%SZ; }
save_once() {
  mkdir -p "$SRC/claude-memory-snapshot"
  cp -f "$MEM"/*.md "$SRC/claude-memory-snapshot/" 2>/dev/null || true
  rsync -a --delete "$SRC/" "$REPO/$DST/" || { echo "$(ts) RSYNC FAILED" >&2; return 1; }
  cd "$REPO" || return 1
  [ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || { echo "$(ts) not on $BRANCH; skipping" >&2; return 1; }
  git add -A -- "$DST"
  local ahead
  ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 1)   # no upstream -> treat as needing a push
  if git diff --cached --quiet && [ "$ahead" = "0" ]; then echo "$(ts) no changes"; return 0; fi
  if ! git diff --cached --quiet; then
    git commit --quiet -m "docs(grills): auto-sync qwen38-heretic grill artifacts $(date -u +%Y-%m-%dT%H:%MZ)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" || { echo "$(ts) COMMIT FAILED" >&2; return 1; }
  fi
  if git push --quiet origin "$BRANCH"; then echo "$(ts) pushed $(git rev-parse --short HEAD)"; return 0; fi
  echo "$(ts) push rejected; trying rebase onto origin/$BRANCH" >&2
  if git pull --quiet --rebase --autostash origin "$BRANCH" && git push --quiet origin "$BRANCH"; then
    echo "$(ts) pushed after rebase $(git rev-parse --short HEAD)"; return 0
  fi
  echo "$(ts) PUSH FAILED — $(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo '?') commit(s) still unpushed; will retry next pass" >&2
  return 1
}
if [ "${1:-}" = "--once" ]; then save_once; exit $?; fi
while true; do save_once; sleep 300; done
