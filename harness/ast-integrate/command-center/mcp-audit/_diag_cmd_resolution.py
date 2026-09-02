"""Scratch diagnostic: does shutil.which() explain the FileNotFoundError rows?

Prints the COMMAND token only (never args-with-secrets, never env values).
"""

import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe_capability as pc  # noqa: E402

specs = pc.load_specs()
for name in ("codex", "chrome-devtools", "playwright", "playwright-cdp", "cloud-hub"):
    s = specs.get(name)
    if not s:
        print(f"{name:22} NO SPEC")
        continue
    cmd = s.get("command")
    print(f"{name:22} command={cmd!r} which={shutil.which(str(cmd))!r}")
