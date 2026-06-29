#!/usr/bin/env bash
# longrun.sh — Bash equivalent of longrun.ps1
#
# Wraps a long-running command with heartbeat progress and a terminal
# SUCCESS:<id> / FAILED:<id> marker. Designed for run_in_background / Monitor
# so heartbeat lines stream as notifications.
#
# Raw command output goes to a log file only (stdout stays clean).
#
# Usage:
#   longrun.sh [OPTIONS] -- <command> [args...]
#
# Options:
#   -i, --id ID               Label for this operation (default: command basename)
#   -h, --heartbeat-sec N     Seconds between heartbeats (default: 15)
#   -t, --hang-timeout-sec N  Kill if silent for N seconds; 0=off (default: 0)
#   -d, --log-dir DIR         Directory for log files (default: $TMPDIR or /tmp)
#
# Examples:
#   # Heartbeat every 3s, stream 10s incremental output
#   longrun.sh -i loop-test -h 3 -- bash -c 'for i in 1 2 3 4 5; do echo "step $i"; sleep 2; done'
#
#   # With hang-timeout:
#   longrun.sh -i silent-test -h 5 -t 10 -- bash -c 'sleep 30'
#
#   # Failing command:
#   longrun.sh -i fail-test -- bash -c 'echo "error output" >&2; exit 1'
#
# Terminal markers:
#   SUCCESS:<id> (<elapsed>s)
#   FAILED:<id> exit=<code> :: <last error line>

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
OPT_ID=''
OPT_HEARTBEAT_SEC=15
OPT_HANG_TIMEOUT_SEC=0
OPT_LOG_DIR="${TMPDIR:-${TMP:-/tmp}}"

# ── Parse options ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--id)               OPT_ID="$2";              shift 2 ;;
        -h|--heartbeat-sec)    OPT_HEARTBEAT_SEC="$2";   shift 2 ;;
        -t|--hang-timeout-sec) OPT_HANG_TIMEOUT_SEC="$2"; shift 2 ;;
        -d|--log-dir)          OPT_LOG_DIR="$2";          shift 2 ;;
        --)                    shift; break ;;
        -*)                    echo "Unknown option: $1" >&2; exit 2 ;;
        *)                     break ;;
    esac
done

if [[ $# -eq 0 ]]; then
    echo "Usage: longrun.sh [OPTIONS] -- <command> [args...]" >&2
    exit 2
fi

CMD="$1"
shift
ARGS=("$@")

# ── Resolve ID ────────────────────────────────────────────────────────────────
if [[ -z "$OPT_ID" ]]; then
    OPT_ID="$(basename "$CMD")"
fi
ID="$OPT_ID"

# ── Resolve log directory ─────────────────────────────────────────────────────
mkdir -p "$OPT_LOG_DIR" 2>/dev/null || true

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_OUT="${OPT_LOG_DIR}/longrun-${ID}-${STAMP}-stdout.log"
LOG_ERR="${OPT_LOG_DIR}/longrun-${ID}-${STAMP}-stderr.log"

printf 'longrun[%s] starting: %s %s\n' "$ID" "$CMD" "${ARGS[*]:-}"
printf 'stdout log : %s\n' "$LOG_OUT"
printf 'stderr log : %s\n' "$LOG_ERR"

# ── Helpers ───────────────────────────────────────────────────────────────────
# Returns the last non-empty line from one or more files
last_nonempty_line() {
    local f line
    local result=''
    for f in "$@"; do
        if [[ -f "$f" ]]; then
            # tac reverses lines; print first non-empty
            while IFS= read -r line; do
                local trimmed="${line#"${line%%[![:space:]]*}"}"
                trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
                if [[ -n "$trimmed" ]]; then
                    result="$trimmed"
                    break
                fi
            done < <(command -p tac "$f" 2>/dev/null || tail -r "$f" 2>/dev/null || tail -n 50 "$f" 2>/dev/null)
        fi
        [[ -n "$result" ]] && break
    done
    printf '%s' "$result"
}

best_last_line() {
    # Prefer stderr for error context; fall back to stdout
    local errline
    errline="$(last_nonempty_line "$LOG_ERR" 2>/dev/null || true)"
    if [[ -n "$errline" ]]; then printf '%s' "$errline"; return; fi
    last_nonempty_line "$LOG_OUT" 2>/dev/null || true
}

# ── stdbuf availability (fail-safe — writing to a file is already unbuffered) ─
STDBUF_CMD=''
if command -v stdbuf >/dev/null 2>&1; then
    STDBUF_CMD='stdbuf -oL -eL'
fi

# ── Launch the command in background ─────────────────────────────────────────
# Writing straight to files avoids the pipeline-exit-code / PIPESTATUS complexity.
# setsid is preferred (new process group → clean tree kill), but is absent in
# Git Bash and some minimal environments — always fall back to plain background.
# Writing to a file (not a pipe) is already unbuffered-enough without setsid.

START_EPOCH=$SECONDS
CHILD_PID=''
CHILD_PGID=''

if [[ -n "$STDBUF_CMD" ]] && command -v setsid >/dev/null 2>&1; then
    # Linux: new session + line-buffered output
    setsid $STDBUF_CMD "$CMD" "${ARGS[@]}" >"$LOG_OUT" 2>"$LOG_ERR" &
elif command -v setsid >/dev/null 2>&1; then
    # Linux without stdbuf: new session, writing to file (unbuffered enough)
    setsid "$CMD" "${ARGS[@]}" >"$LOG_OUT" 2>"$LOG_ERR" &
elif [[ -n "$STDBUF_CMD" ]]; then
    # stdbuf available but no setsid (unusual)
    $STDBUF_CMD "$CMD" "${ARGS[@]}" >"$LOG_OUT" 2>"$LOG_ERR" &
else
    # Git Bash / minimal environments: plain background, file redirect
    "$CMD" "${ARGS[@]}" >"$LOG_OUT" 2>"$LOG_ERR" &
fi
CHILD_PID=$!
# Get the process group; falls back to PID itself if ps -o pgid unavailable
CHILD_PGID="$(ps -o pgid= -p "$CHILD_PID" 2>/dev/null | tr -d ' ' || true)"
if [[ -z "$CHILD_PGID" ]]; then CHILD_PGID="$CHILD_PID"; fi

# ── Kill helper: terminate entire process tree ────────────────────────────────
kill_tree() {
    local pid="$1"
    local pgid="$2"
    # Try process group first (negative pid = group leader)
    if [[ -n "$pgid" ]] && [[ "$pgid" != "0" ]]; then
        kill -- "-${pgid}" 2>/dev/null || true
    fi
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    kill -9 "$pid" 2>/dev/null || true
    [[ -n "$pgid" ]] && kill -9 -- "-${pgid}" 2>/dev/null || true
}

# ── Heartbeat + hang-detection loop ──────────────────────────────────────────
LAST_SIZE=0
LAST_OUTPUT_TIME=$SECONDS
NEXT_HEARTBEAT=$(( SECONDS + OPT_HEARTBEAT_SEC ))

while kill -0 "$CHILD_PID" 2>/dev/null; do
    sleep 0.5

    NOW=$SECONDS
    ELAPSED=$(( NOW - START_EPOCH ))

    # Hang detection
    if [[ "$OPT_HANG_TIMEOUT_SEC" -gt 0 ]]; then
        # Sum stdout + stderr sizes
        SIZE_OUT=0; SIZE_ERR=0
        if [[ -f "$LOG_OUT" ]]; then SIZE_OUT=$(wc -c < "$LOG_OUT" 2>/dev/null || echo 0); fi
        if [[ -f "$LOG_ERR" ]]; then SIZE_ERR=$(wc -c < "$LOG_ERR" 2>/dev/null || echo 0); fi
        CURRENT_SIZE=$(( SIZE_OUT + SIZE_ERR ))

        if [[ "$CURRENT_SIZE" -gt "$LAST_SIZE" ]]; then
            LAST_SIZE=$CURRENT_SIZE
            LAST_OUTPUT_TIME=$NOW
        elif [[ $(( NOW - LAST_OUTPUT_TIME )) -ge "$OPT_HANG_TIMEOUT_SEC" ]]; then
            LAST_LINE="$(best_last_line 2>/dev/null || true)"
            [[ -z "$LAST_LINE" ]] && LAST_LINE='(no output captured)'
            kill_tree "$CHILD_PID" "$CHILD_PGID"
            printf 'FAILED:%s exit=HANG :: hung for %ds with no output | last: %s\n' \
                "$ID" "$OPT_HANG_TIMEOUT_SEC" "$LAST_LINE"
            exit 124
        fi
    fi

    # Heartbeat
    if [[ "$NOW" -ge "$NEXT_HEARTBEAT" ]]; then
        LAST_LINE="$(best_last_line 2>/dev/null || true)"
        [[ -z "$LAST_LINE" ]] && LAST_LINE='(no output yet)'
        printf '⏳ %s: %ds | %s\n' "$ID" "$ELAPSED" "$LAST_LINE"
        NEXT_HEARTBEAT=$(( NOW + OPT_HEARTBEAT_SEC ))
    fi
done

# ── Collect exit code ─────────────────────────────────────────────────────────
EXIT_CODE=0
wait "$CHILD_PID" 2>/dev/null || EXIT_CODE=$?

ELAPSED=$(( SECONDS - START_EPOCH ))

# ── Terminal marker ───────────────────────────────────────────────────────────
if [[ "$EXIT_CODE" -eq 0 ]]; then
    printf 'SUCCESS:%s (%ds)\n' "$ID" "$ELAPSED"
else
    LAST_LINE="$(best_last_line 2>/dev/null || true)"
    [[ -z "$LAST_LINE" ]] && LAST_LINE='(no output captured)'
    printf 'FAILED:%s exit=%d :: %s\n' "$ID" "$EXIT_CODE" "$LAST_LINE"
fi

exit "$EXIT_CODE"
