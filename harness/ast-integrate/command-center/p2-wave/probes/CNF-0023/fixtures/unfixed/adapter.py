#!/usr/bin/env python3
'''UNFIXED adapter: interpolates payload into a single-quoted bash -c body.'''
import subprocess
import sys
from pathlib import Path

body = Path(sys.argv[1]).read_text(encoding='utf-8').strip()
# windows-shell section 10 defect: apostrophe in body terminates the quotes.
cmd = "python3 -c '" + body + "'"
proc = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
sys.stdout.write(proc.stdout or '')
sys.stderr.write(proc.stderr or '')
raise SystemExit(proc.returncode if proc.returncode != 0 else 1)
