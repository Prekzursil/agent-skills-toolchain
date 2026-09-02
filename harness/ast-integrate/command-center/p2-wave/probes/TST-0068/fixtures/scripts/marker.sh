#!/usr/bin/env bash
# TST-0068 live marker. Shebang is honored on Linux execve; Windows cmd.exe
# does not read this line.
set -eu
tag="${1:-ok}"
printf 'TST-0068-MARKER:%s\n' "${tag}"
