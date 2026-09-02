#!/usr/bin/env bash
# Corrected forms the lint must stay silent on.
count=$(grep -c '^NO_SUCH_TOKEN$' "$1" || true)
if [ "$(grep -c . "$1" || true)" -gt 0 ]; then
  echo yes
fi
n=$(grep -c '^' "$1" || true)
x="$1"
if [ -n "$x" ]; then
  echo nonempty
fi
printf '%s\n' "$count" "$n"
