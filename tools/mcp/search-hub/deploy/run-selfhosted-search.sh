#!/usr/bin/env bash
# Bring up the minimal self-hosted, key-free search backend (TrailSearch) that
# powers search-hub's keyless selfhosted_* tools. Reuses the estate SearXNG at
# host.docker.internal:8890 by default; pass --bundled to also start a local one.
#
# Usage:
#   ./run-selfhosted-search.sh [up|down|smoke|logs] [--bundled]
#
# Prereqs: Docker + docker compose. TrailSearch (MIT) is cloned to ./trailsearch-src
# (pinned ref, override with TRAILSEARCH_REF). No API keys are needed or set.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

TRAILSEARCH_REPO="${TRAILSEARCH_REPO:-https://github.com/jianjungki/tavily-open.git}"
# Pinned to the ref measured for the 2026-09-02 decision record; bump deliberately.
TRAILSEARCH_REF="${TRAILSEARCH_REF:-e0e2dc1160fc60d0ea925e164194e34040e750f6}"
export TRAILSEARCH_SRC="${TRAILSEARCH_SRC:-$HERE/trailsearch-src}"
PORT="${SELFHOSTED_SEARCH_PORT:-8794}"
COMPOSE_FILE="docker-compose.selfhosted-search.yml"

ACTION="${1:-up}"
PROFILE_ARGS=()
for arg in "$@"; do
  [ "$arg" = "--bundled" ] && PROFILE_ARGS=(--profile bundled)
done

ensure_src() {
  if [ ! -d "$TRAILSEARCH_SRC/.git" ]; then
    echo "[run] cloning TrailSearch -> $TRAILSEARCH_SRC"
    git clone "$TRAILSEARCH_REPO" "$TRAILSEARCH_SRC"
  fi
  echo "[run] pinning TrailSearch @ $TRAILSEARCH_REF"
  git -C "$TRAILSEARCH_SRC" fetch --quiet origin "$TRAILSEARCH_REF" 2>/dev/null || true
  git -C "$TRAILSEARCH_SRC" checkout --quiet "$TRAILSEARCH_REF"
}

smoke() {
  echo "[smoke] GET /docs"
  curl -fsS "http://127.0.0.1:${PORT}/docs" >/dev/null && echo "  ok: healthy"
  echo "[smoke] POST /tavily/search"
  curl -fsS -X POST "http://127.0.0.1:${PORT}/tavily/search" \
    -H "Content-Type: application/json" \
    -d '{"query":"self hosted search smoke","max_results":3,"mode":"search"}' \
    | head -c 400
  echo
  echo "[smoke] point the hub at it:  export TRAILSEARCH_URL=http://127.0.0.1:${PORT}"
}

case "$ACTION" in
  up)
    ensure_src
    echo "[run] docker compose up (app on 127.0.0.1:${PORT})"
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" up -d --build
    echo "[run] waiting for /docs ..."
    for _ in $(seq 1 60); do
      curl -fsS "http://127.0.0.1:${PORT}/docs" >/dev/null 2>&1 && break || sleep 2
    done
    smoke
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" down
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" logs -f
    ;;
  smoke)
    smoke
    ;;
  *)
    echo "usage: $0 [up|down|smoke|logs] [--bundled]" >&2
    exit 2
    ;;
esac
