#!/usr/bin/env bash
# Planted: unquoted $(...) in a numeric comparison.
if [ $(grep -c . "$1") -gt 0 ]; then
  echo yes
fi
