#!/usr/bin/env bash
# BUILD-R1: the decisive both-states test for the CI wiring.
#
# STATE BROKEN  (already measured): ubuntu python3 with NO tiktoken -> rule_audit --self-test
#               fails 2/19 controls, and r2_control_count_gate + r2_failclosed_mutation
#               cascade red off it.
# STATE FIXED   (this script): same interpreter, same repo, tiktoken installed.
#
# If the same invocations go green here, the CI plan needs exactly one dependency and the
# encoder control was doing its job.  If they stay red, tiktoken was not the cause and the
# plan must change.  Venv lives on the WSL-native filesystem (/tmp), never in the repo.
set -u

VENV=/tmp/rule-audit-venv
REPO=/mnt/c/Users/Prekzursil/source/ast-integrate

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" || exit 1
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check tiktoken || exit 1

cd "$REPO" || exit 1
echo "== interpreter =="
"$VENV/bin/python" docs/rule-audit/_b5_tiktoken.py
echo
echo "== sweep with tiktoken present =="
PYTHONIOENCODING=utf-8 "$VENV/bin/python" docs/rule-audit/_b3_portability.py --tag linux-tiktoken
