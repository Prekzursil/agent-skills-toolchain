#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
python3 -c 'from pathlib import Path; t=Path("command-center/schema/audit-detector-control.schema.json").read_text(); i=t.find("$id"); print(t[i:i+140])'
python3 command-center/p2-wave/_measure_one_delivered.py CNL-0099
echo EXIT-CNL-0099=$?
python3 command-center/p2-wave/_measure_one_delivered.py ARC-0050
echo EXIT-ARC-0050=$?
