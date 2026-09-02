#!/usr/bin/env bash
set -eu
if [ "$#" -lt 1 ]; then echo "git-bash-standin: usage" >&2; exit 2; fi
target=$1
shift
if [ ! -f "$target" ]; then echo "git-bash-standin: not a file" >&2; exit 127; fi
tmp=$(mktemp)
tr -d '\r' < "$target" > "$tmp"
exec /bin/bash "$tmp" "$@"
