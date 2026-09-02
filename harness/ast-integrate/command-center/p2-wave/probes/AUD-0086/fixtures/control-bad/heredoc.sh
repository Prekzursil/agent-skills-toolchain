#!/bin/sh
# Control-bad: heredoc body fed to python via the shell.
python3 - <<'PY'
print(1)
PY
