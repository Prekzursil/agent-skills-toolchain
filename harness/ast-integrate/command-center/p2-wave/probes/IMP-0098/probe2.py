#!/usr/bin/env python3
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("probe2_independent_source.py")), run_name="__main__")
