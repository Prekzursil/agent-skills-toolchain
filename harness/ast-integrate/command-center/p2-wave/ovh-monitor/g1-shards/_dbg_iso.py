#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT", Path.home() / "p2-g1")).resolve()
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/CNF-0183"))
import isolate  # noqa: E402

def main() -> None:
    print("isolate", isolate.__file__)
    print("has_explicit_import", "import sitecustomize" in isolate.PROBE_PY)
    tmp = isolate.outside_repo_tmpdir(REPO)
    iso = tmp / "._isolate"
    isolate.write_sitecustomize(iso)
    print("sitecustomize_head:")
    print((iso / "sitecustomize.py").read_text(encoding="utf-8")[:500])
    env = isolate.isolation_env(REPO, iso)
    print("PYTHONPATH", env.get("PYTHONPATH"))
    print("FORBID", env.get("CNF0183_FORBID"))
    cat = str(REPO / "command-center/WORK-UNIT-CATALOG.json")
    p = subprocess.run(
        [sys.executable, "-B", "-c", isolate.PROBE_PY, cat],
        cwd=str(tmp),
        env=env,
        capture_output=True,
        text=True,
    )
    print("rc", p.returncode)
    print("stdout", repr(p.stdout))
    print("stderr", repr(p.stderr))
    print("both_states", json.dumps(isolate.both_states(REPO), indent=2, default=str))


if __name__ == "__main__":
    main()
