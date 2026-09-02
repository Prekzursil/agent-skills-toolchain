#!/usr/bin/env bash
# Planted: [ -n $x ] without quotes — empty x becomes `[ -n ]`, which is true.
x="$1"
if [ -n $x ]; then
  echo nonempty
fi
