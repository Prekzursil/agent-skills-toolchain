#!/usr/bin/env bash
# Linux launch adapter for IMP-0015. CRLF copies are refused.
# Invoked as `sh launch.sh`; dash rejects `pipefail`.
set -eu
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cmd="${1:-}"
shift || true

die() { echo "ERROR:$1 path=${2:-}" >&2; exit 1; }

has_cr() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys; d=open(sys.argv[1],"rb").read(); sys.exit(0 if b"\r" in d else 1)' "$1"
    return $?
  fi
  grep -a $'\r' "$1" >/dev/null 2>&1
}

check_file() {
  local f="$1"
  if has_cr "$f"; then
    die "CRLF_REJECTED" "$f"
  fi
  bash -n "$f"
}

resolve() {
  # POSIX: `sh` may be dash, which has no [[ ]]; a failed [[ made absolute
  # paths resolve under $ROOT and the CRLF check miss its target.
  case "$1" in
    /*) echo "$1" ;;
    *) echo "$ROOT/$1" ;;
  esac
}

case "$cmd" in
  host)
    echo "kernel=$(uname -s)"
    echo "cwd=$(pwd)"
    echo "bash=$(bash --version | head -n 1)"
    ;;
  check)
    f="$(resolve "${1:-}")"
    check_file "$f"
    echo "OK"
    ;;
  run)
    rel="${1:-}"
    arg="${2:-}"
    f="$(resolve "$rel")"
    check_file "$f"
    exec bash "$f" "$arg"
    ;;
  *)
    die "USAGE"
    ;;
esac
