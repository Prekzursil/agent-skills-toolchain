#!/usr/bin/env bash
# Planted: wc -l on a possibly-empty stream (undercounts a last line with no NL).
n=$(cat "$1" | wc -l)
echo "$n"
