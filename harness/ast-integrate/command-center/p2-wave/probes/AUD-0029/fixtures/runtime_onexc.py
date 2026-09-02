"""Runtime-only 3.12 shutil.rmtree(onexc=...) API.

A static scan that never inspects signatures will miss this if the call is
assembled at runtime. Probe 2 executes it under 3.10, 3.11, and 3.12.
"""
import shutil
from pathlib import Path

target = Path("/tmp/aud0029-onexc-absent-dir")
shutil.rmtree(target, onexc=lambda *_args: None)
print("onexc-ok")
