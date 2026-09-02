#!/usr/bin/env bash
# Planted known-broken form: grep -c exits 1 on zero matches AND prints 0,
# so || echo 0 fires too and the captured count is 0\n0.
count=$(grep -c '^NO_SUCH_TOKEN$' "$1" || echo 0)
echo "$count"
