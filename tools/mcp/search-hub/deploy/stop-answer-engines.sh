#!/usr/bin/env bash
# Stop EVERY answer-engine profile (vane, ldr, ollama) and reclaim the RAM.
# Thin wrapper: `run-answer-engines.sh down` already expands to all profiles, which
# matters because `docker compose down` skips profiled services it was not told
# about and would leave them running.
#
# Usage:  ./stop-answer-engines.sh [--print]     (--print shows, does not stop)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/run-answer-engines.sh" down --vane --ldr --ollama "$@"
