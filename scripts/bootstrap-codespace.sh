#!/usr/bin/env bash
# Materialise the agent harness into ~/.claude inside a Codespace / Linux container.
#
# Why an installer instead of committing ~/.claude directly: `.claude/` is gitignored
# (.gitignore:36) precisely so runtime secrets (.credentials.json, history.jsonl,
# session transcripts) can never be committed. So the repo carries SOURCES and this
# script assembles the live tree from them.
#
# Safe to re-run (idempotent). Never writes a credential.
#
#   bash scripts/bootstrap-codespace.sh            # install
#   bash scripts/bootstrap-codespace.sh --dry-run  # show what it would do
set -euo pipefail

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CLAUDE_HOME:-$HOME/.claude}"

run() { if [[ $DRY -eq 1 ]]; then echo "  would: $*"; else "$@"; fi; }
say() { printf '%s\n' "$*"; }

say "=== bootstrap agent harness -> $DEST ==="
say "repo: $REPO"
[[ $DRY -eq 1 ]] && say "(DRY RUN - nothing will be written)"

run mkdir -p "$DEST"

# ---- 1. content that is safe to mirror verbatim ----
# skills live in two repo roots; skills-claude-only is Claude-specific and wins.
for pair in "skills:skills" "skills-claude-only:skills" "commands:commands" \
            "agents:agents" "rules:rules" "hooks:hooks" \
            "agent-self/config/workflows:workflows"; do
  src="$REPO/${pair%%:*}"; dst="$DEST/${pair##*:}"
  if [[ -d "$src" ]]; then
    n=$(find "$src" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')
    say "[1] ${pair%%:*} -> ${pair##*:}  ($n entries)"
    run mkdir -p "$dst"
    if [[ $DRY -eq 0 ]]; then cp -R "$src/." "$dst/"; fi
  fi
done

# ---- 2. settings.json, with Windows-only hooks stripped ----
# 43 hook entries hardcode C:/ paths and 7 invoke powershell/pwsh; on Linux each
# would fail on EVERY tool call, so they are filtered out rather than shipped broken.
SRC_SETTINGS="$REPO/agent-self/config/settings.json"
if [[ -f "$SRC_SETTINGS" ]]; then
  say "[2] settings.json -> $DEST/settings.json (dropping Windows-bound hooks)"
  if [[ $DRY -eq 0 ]]; then
    python3 - "$SRC_SETTINGS" "$DEST/settings.json" <<'PY'
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    cfg = json.load(f)
WIN = re.compile(r'[A-Za-z]:[\\/]|powershell|pwsh|\.ps1', re.I)
removed = kept = 0
hooks = cfg.get("hooks") or {}
for event, entries in list(hooks.items()):
    new_entries = []
    for entry in entries or []:
        inner = [h for h in (entry.get("hooks") or [])
                 if not WIN.search(str(h.get("command", "")))]
        removed += len(entry.get("hooks") or []) - len(inner)
        kept += len(inner)
        if inner:
            new_entries.append({**entry, "hooks": inner})
    if new_entries:
        hooks[event] = new_entries
    else:
        del hooks[event]
cfg["hooks"] = hooks
# a Windows statusline cannot run here either
cfg.pop("statusLine", None)
# force the Linux-safe MCP set
cfg.pop("enabledPlugins", None)
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"    hooks kept={kept} dropped(Windows-bound)={removed}")
PY
  fi
fi

# ---- 3. MCP: portable servers only ----
# 31 of 69 servers point at Windows-local installs (IDA, Ghidra, CheatEngine,
# apktool, hexstrike, jadx...) and cannot exist here. Only the portable 38 are wired.
PORT="$REPO/agent-self/config/mcp/mcp.portable.json"
if [[ -f "$PORT" ]]; then
  say "[3] MCP portable set -> $DEST/../.mcp.json"
  run cp "$PORT" "$HOME/.mcp.json"
  say "    NOTE: values are \${PLACEHOLDERS}; supply real keys via Codespaces Secrets:"
  say "      gh secret set EXA_API_KEY --user   (etc.)"
fi

# ---- 4. top-level instruction files ----
for f in CLAUDE.md AGENTS.md; do
  [[ -f "$REPO/$f" ]] && { say "[4] $f -> $DEST/$f"; run cp "$REPO/$f" "$DEST/$f"; }
done

# ---- 5. never ship these ----
say "[5] deliberately NOT installed: .credentials.json, history.jsonl, projects/,"
say "    sessions/, plugins/ (22 GB - refetch via 'claude plugin install')"

say ""
say "done. verify with:  claude mcp list   &&   ls $DEST/skills | wc -l"
