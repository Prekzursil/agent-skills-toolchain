#!/usr/bin/env bash
# VERIFY_PLAN.sh — POSIX mirror of VERIFY_PLAN.ps1 (git-bash / WSL / Linux / macOS).
# The .ps1 is the PRIMARY path on native Windows 11; use this when running under a POSIX shell.
#
# Proves the shared mcp_agent_mail http channel works symmetrically (claude<->codex message
# visibility) and that a file-lease acquire/release round-trips, BEFORE AgentBridge is retired.
# Self-contained: starts an ISOLATED serve-http on a temp STORAGE_ROOT, discovers the bearer
# token, runs agent_mail_probe.py as an MCP client, prints SUCCESS:/FAILED: lines, tears down.
#
# Usage:  AM_REPO=/path/to/mcp_agent_mail ./VERIFY_PLAN.sh [PORT]
# Requires: uv on PATH, a cloned+synced mcp_agent_mail repo, git.
# Exit 0 == all checks green.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBE="$SCRIPT_DIR/agent_mail_probe.py"
REPO="${AM_REPO:-$HOME/mcp_agent_mail}"
PORT="${1:-8799}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-90}"

fail() { echo "FAILED:$1 ${2:-}"; }

# ---- preconditions ----
[ -d "$REPO" ] || { fail precondition_repo "repo not found at $REPO (set AM_REPO)"; exit 1; }
command -v uv >/dev/null 2>&1 || { fail precondition_uv "uv not on PATH"; exit 1; }
[ -f "$PROBE" ] || { fail precondition_probe "agent_mail_probe.py missing next to this script"; exit 1; }
echo "SUCCESS:preconditions"

# ---- isolated workspace ----
STAMP="$(date +%Y%m%d-%H%M%S)"
MARK="probe${STAMP}$(head -c6 /dev/urandom | od -An -tx1 | tr -d ' \n' 2>/dev/null || echo rnd)"
BASE="${TMPDIR:-/tmp}/am_verify_$STAMP"
STORAGE="$BASE/storage"
PROJECT="$BASE/project"
LOG="$BASE/server.log"
mkdir -p "$STORAGE" "$PROJECT"
: > "$LOG"

SERVER_PID=""
cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" >/dev/null 2>&1 || true
  rm -rf "$BASE" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# ---- start isolated serve-http ----
export STORAGE_ROOT="$STORAGE"
( cd "$REPO" && exec uv run python -m mcp_agent_mail.cli serve-http --host 127.0.0.1 --port "$PORT" ) >"$LOG" 2>&1 &
SERVER_PID=$!

# ---- wait for the port ----
up=0
for _ in $(seq 1 "$STARTUP_TIMEOUT"); do
  kill -0 "$SERVER_PID" 2>/dev/null || break
  if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then exec 3>&- 3<&- ; up=1; break; fi
  # fallback probes if bash /dev/tcp is unavailable
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$PORT" 2>/dev/null; then up=1; break; fi
  sleep 1
done
if [ "$up" -ne 1 ]; then
  fail server_start "serve-http did not open port $PORT within ${STARTUP_TIMEOUT}s"
  echo "--- server.log tail ---"; tail -n 30 "$LOG" 2>/dev/null || true
  exit 1
fi
echo "SUCCESS:server_up port=$PORT"

# ---- discover bearer token (env file, then server log) ----
TOKEN=""
for src in "$STORAGE/.env" "$LOG"; do
  [ -n "$TOKEN" ] && break
  [ -f "$src" ] || continue
  TOKEN="$(grep -Eo 'BEARER[A-Z_]*[[:space:]]*[=:][[:space:]]*"?[A-Za-z0-9._-]+' "$src" 2>/dev/null \
            | head -n1 | grep -Eo '[A-Za-z0-9._-]+$' || true)"
done
if [ -n "$TOKEN" ]; then echo "SUCCESS:token_discovered (len=${#TOKEN})"
else echo "note: no bearer token discovered; attempting unauthenticated (probe reports if auth is required)"; fi

# ---- run the MCP-client probe (inside repo so mcp SDK resolves) ----
export AM_URL="http://127.0.0.1:$PORT/mcp"
export AM_TOKEN="$TOKEN"
export AM_PROJECT="$PROJECT"
export AM_MARK="$MARK"

( cd "$REPO" && uv run python "$PROBE" )
OVERALL=$?

if [ "$OVERALL" -eq 0 ]; then echo "SUCCESS:verify_plan_complete"; exit 0
else echo "FAILED:verify_plan $OVERALL check(s) failed"; exit 1; fi
