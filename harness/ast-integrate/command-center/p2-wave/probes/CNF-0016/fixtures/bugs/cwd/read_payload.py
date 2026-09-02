#!/usr/bin/env python3
# REQUIRES: working directory command-center/p2-wave/probes/CNF-0016/fixtures/bugs/cwd so relative path data/payload.txt resolves
"""Planted P0: payload only visible when cwd is this directory."""
from pathlib import Path

print(Path("data/payload.txt").read_text(encoding="utf-8"), end="")
