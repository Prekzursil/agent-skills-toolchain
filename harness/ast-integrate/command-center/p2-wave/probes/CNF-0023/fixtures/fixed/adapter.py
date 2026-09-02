#!/usr/bin/env python3
'''FIXED adapter: invoke the payload script by path, never inline.'''
import subprocess
import sys

proc = subprocess.run([sys.executable, sys.argv[1]])
raise SystemExit(proc.returncode)
