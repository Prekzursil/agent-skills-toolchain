#!/usr/bin/env bash
# Start / stop the OPT-IN, ON-DEMAND answer engines behind search-hub's `answer`
# lane: Vane (selfhosted_answer) and local-deep-research (its web UI + REST API;
# the hub's LDR MCP path, ENABLE_LDR=1, runs `ldr-mcp` over STDIO on the host).
# Nothing starts unless a profile flag is given -- 0 RAM idle is the default.
#
# Usage:
#   ./run-answer-engines.sh [up|down|logs|ps|smoke|print] [--vane] [--ldr] [--ollama] [--print]
#
#   up --vane            start Vane on 127.0.0.1:${VANE_PORT:-3000}, smoke GET /api/providers
#   up --ldr             start local-deep-research on 127.0.0.1:${LDR_PORT:-5000}
#   up --vane --ldr      both;  --ollama adds an evicting Ollama (OLLAMA_KEEP_ALIVE=0)
#                        ONLY for a box without a host Ollama
#   down                 stop EVERY profile (what stop-answer-engines.sh calls)
#   print / --print      show the resolved env + the exact compose command WITHOUT
#                        running Docker (the one mode that works on a Docker-less box)
#
# Prereqs (up/down/logs/ps): Docker + docker compose. Reuses the estate SearXNG at
# host.docker.internal:8890 and the host Ollama at host.docker.internal:11434 by
# default -- override with VANE_SEARXNG_API_URL / VANE_OLLAMA_BASE_URL /
# LDR_SEARXNG_URL / LDR_OLLAMA_URL. No API keys are needed or set.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
COMPOSE_FILE="docker-compose.answer-engines.yml"

# Pins verified 2026-09-02 (Docker Hub + upstream tags); bump deliberately, and
# re-read Vane's /api/providers + /api/search contract if you move off v1.12.2.
export VANE_IMAGE="${VANE_IMAGE:-itzcrazykns1337/vane:slim-v1.12.2}"
export VANE_PORT="${VANE_PORT:-3000}"
export VANE_SEARXNG_API_URL="${VANE_SEARXNG_API_URL:-http://host.docker.internal:8890}"
export VANE_OLLAMA_BASE_URL="${VANE_OLLAMA_BASE_URL:-http://host.docker.internal:11434}"
export VANE_MEM_LIMIT="${VANE_MEM_LIMIT:-768m}"
export LDR_IMAGE="${LDR_IMAGE:-localdeepresearch/local-deep-research:1.10.7}"
export LDR_PORT="${LDR_PORT:-5000}"
export LDR_OLLAMA_URL="${LDR_OLLAMA_URL:-http://host.docker.internal:11434}"
export LDR_SEARXNG_URL="${LDR_SEARXNG_URL:-http://host.docker.internal:8890}"
export LDR_MEM_LIMIT="${LDR_MEM_LIMIT:-2g}"
export OLLAMA_IMAGE="${OLLAMA_IMAGE:-ollama/ollama:0.33.2}"
export OLLAMA_PORT="${OLLAMA_PORT:-11434}"
export OLLAMA_MEM_LIMIT="${OLLAMA_MEM_LIMIT:-16g}"
export ANSWER_ENGINES_RESTART="${ANSWER_ENGINES_RESTART:-no}"
# The eviction policy the `ollama` profile hard-codes; set the same on a host Ollama.
OLLAMA_KEEP_ALIVE="0"

ACTION="up"
PRINT_ONLY=0
WANT_VANE=0
WANT_LDR=0
WANT_OLLAMA=0
for arg in "$@"; do
  case "$arg" in
    up|down|logs|ps|smoke) ACTION="$arg" ;;
    print) ACTION="print" ;;
    --vane) WANT_VANE=1 ;;
    --ldr) WANT_LDR=1 ;;
    --ollama) WANT_OLLAMA=1 ;;
    --all) WANT_VANE=1; WANT_LDR=1 ;;
    --print) PRINT_ONLY=1 ;;
    -h|--help) ACTION="help" ;;
    *)
      echo "unknown argument: $arg" >&2
      ACTION="help"
      ;;
  esac
done
# --print wins over any action: it must never reach Docker.
[ "$PRINT_ONLY" = 1 ] && ACTION="print"

# `down`/`logs`/`ps` with no flag mean every profile (compose ignores profiled
# services otherwise, which would leave containers running after a `down`).
if [ "$ACTION" = "down" ] || [ "$ACTION" = "logs" ] || [ "$ACTION" = "ps" ]; then
  if [ "$WANT_VANE$WANT_LDR$WANT_OLLAMA" = "000" ]; then
    WANT_VANE=1; WANT_LDR=1; WANT_OLLAMA=1
  fi
fi

PROFILE_ARGS=()
PROFILE_NAMES=()
[ "$WANT_VANE" = 1 ] && PROFILE_ARGS+=(--profile vane) && PROFILE_NAMES+=(vane)
[ "$WANT_LDR" = 1 ] && PROFILE_ARGS+=(--profile ldr) && PROFILE_NAMES+=(ldr)
[ "$WANT_OLLAMA" = 1 ] && PROFILE_ARGS+=(--profile ollama) && PROFILE_NAMES+=(ollama)

usage() {
  echo "usage: $0 [up|down|logs|ps|smoke|print] [--vane] [--ldr] [--ollama] [--print]" >&2
  echo "  nothing starts by default: pass --vane and/or --ldr to choose the engines" >&2
}

compose_cmd() {
  # The exact command, as text, so --print shows what `up` would run.
  local verb="$1"
  echo "docker compose -f $COMPOSE_FILE ${PROFILE_ARGS[*]:-} $verb"
}

print_env() {
  echo "# answer-engines: resolved env (nothing was started; Docker not invoked)"
  echo "# profiles: ${PROFILE_NAMES[*]:-<none -- pass --vane / --ldr / --ollama>}"
  echo "COMPOSE_FILE=$HERE/$COMPOSE_FILE"
  echo "ANSWER_ENGINES_RESTART=$ANSWER_ENGINES_RESTART"
  echo "VANE_IMAGE=$VANE_IMAGE"
  echo "VANE_PORT=$VANE_PORT"
  echo "VANE_SEARXNG_API_URL=$VANE_SEARXNG_API_URL"
  echo "VANE_OLLAMA_BASE_URL=$VANE_OLLAMA_BASE_URL"
  echo "VANE_MEM_LIMIT=$VANE_MEM_LIMIT"
  echo "LDR_IMAGE=$LDR_IMAGE"
  echo "LDR_PORT=$LDR_PORT"
  echo "LDR_OLLAMA_URL=$LDR_OLLAMA_URL"
  echo "LDR_SEARXNG_URL=$LDR_SEARXNG_URL"
  echo "LDR_MEM_LIMIT=$LDR_MEM_LIMIT"
  echo "OLLAMA_IMAGE=$OLLAMA_IMAGE"
  echo "OLLAMA_PORT=$OLLAMA_PORT"
  echo "OLLAMA_MEM_LIMIT=$OLLAMA_MEM_LIMIT"
  echo "OLLAMA_KEEP_ALIVE=$OLLAMA_KEEP_ALIVE   # hard-coded in the ollama profile; set it on a host Ollama too"
  echo "# would run:"
  echo "#   $(compose_cmd 'up -d')"
  echo "#   $(compose_cmd 'down')"
  echo "# then point the hub at the engines (endpoint-agnostic: an OVH URL works the same):"
  echo "#   export ENABLE_VANE=1 VANE_URL=http://127.0.0.1:${VANE_PORT}      # or VANE_URL=https://vane.your.ovh"
  echo "#   VANE_TIMEOUT_S=120 is the LLM budget per answer (raise for slow models)"
  echo "#   export ENABLE_LDR=1        # LDR MCP ProviderSpec (providers.py): runs ldr-mcp over STDIO via uvx on the host"
  echo "#   LDR web UI + REST API from --ldr: http://127.0.0.1:${LDR_PORT}   # NOT LDR_URL: providers.py uses LDR_URL only"
  echo "#                                                                # for a resident ldr-mcp behind a Streamable-HTTP gateway"
}

smoke() {
  if [ "$WANT_VANE" = 1 ]; then
    echo "[smoke] vane GET /api/providers"
    curl -fsS "http://127.0.0.1:${VANE_PORT}/api/providers" | head -c 600
    echo
    echo "[smoke] point the hub at it:  export ENABLE_VANE=1 VANE_URL=http://127.0.0.1:${VANE_PORT}"
  fi
  if [ "$WANT_LDR" = 1 ]; then
    echo "[smoke] ldr GET /api/v1/health"
    curl -fsS "http://127.0.0.1:${LDR_PORT}/api/v1/health" | head -c 300
    echo
    echo "[smoke] LDR web UI + REST API: http://127.0.0.1:${LDR_PORT}  (hub MCP path is separate:"
    echo "[smoke]   export ENABLE_LDR=1 runs ldr-mcp over STDIO on the host; LDR_URL is NOT this port)"
  fi
  if [ "$WANT_OLLAMA" = 1 ]; then
    echo "[smoke] ollama GET /api/tags"
    curl -fsS "http://127.0.0.1:${OLLAMA_PORT}/api/tags" | head -c 300
    echo
  fi
}

wait_for() {
  local url="$1"
  for _ in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0 || sleep 2
  done
  echo "[run] warning: $url did not answer within 120 s (first pull can take longer)" >&2
  return 0
}

case "$ACTION" in
  print)
    print_env
    ;;
  up)
    if [ "${#PROFILE_ARGS[@]}" -eq 0 ]; then
      echo "[run] refusing: nothing is started by default -- pass --vane and/or --ldr (and --ollama only without a host Ollama)" >&2
      usage
      exit 2
    fi
    echo "[run] $(compose_cmd 'up -d')"
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" up -d
    [ "$WANT_VANE" = 1 ] && wait_for "http://127.0.0.1:${VANE_PORT}/api/providers"
    [ "$WANT_LDR" = 1 ] && wait_for "http://127.0.0.1:${LDR_PORT}/api/v1/health"
    smoke
    ;;
  down)
    echo "[run] $(compose_cmd 'down')"
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" down
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" logs -f
    ;;
  ps)
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" ps
    ;;
  smoke)
    if [ "$WANT_VANE$WANT_LDR$WANT_OLLAMA" = "000" ]; then WANT_VANE=1; WANT_LDR=1; fi
    smoke
    ;;
  *)
    usage
    exit 2
    ;;
esac
