#!/usr/bin/env bash
printf 'ok-lf argv=%s\n' "$*"
command -v printf >/dev/null || exit 97
exit 0
