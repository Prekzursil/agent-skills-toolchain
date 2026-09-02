"""Both-states control for the load-bearing design decision:

  Does a repo-root directory named `platform/` shadow the stdlib `platform` module?

State A (known-good, what we ship): platform/ has NO __init__.py  -> namespace portion only,
   stdlib platform.py must still win.
State B (known-broken): platform/__init__.py exists -> regular package, MUST shadow stdlib.

If the probe reports the same answer in both states it measures nothing.
Runs entirely in a throwaway temp dir; touches nothing in the repo.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

CHILD = (
    "import platform, sys;"
    "f=getattr(platform,'__file__',None);"
    "print('FILE=' + str(f));"
    "print('HAS_SYSTEM=' + str(hasattr(platform,'system')))"
)


def run(cwd: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", CHILD],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return (proc.stdout + proc.stderr).strip()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "platform" / "lib").mkdir(parents=True)

        state_a = run(root)  # no __init__.py

        (root / "platform" / "__init__.py").write_text(
            "SHADOWED = True\n", encoding="utf-8"
        )
        state_b = run(root)

    a_stdlib = "Lib\\platform.py" in state_a or "lib/platform.py" in state_a.lower()
    b_shadow = "HAS_SYSTEM=False" in state_b or "platform\\__init__.py" in state_b

    result = {
        "state_a_no_init_py": state_a,
        "state_b_with_init_py": state_b,
        "A_resolves_to_stdlib": a_stdlib,
        "B_shadows_stdlib": b_shadow,
        "detector_discriminates": bool(a_stdlib and b_shadow),
        "conclusion": (
            "CONFIRMED: omitting platform/__init__.py is required; adding it shadows stdlib platform."
            if (a_stdlib and b_shadow)
            else "DETECTOR-FAILURE: probe did not discriminate the two states."
        ),
    }
    print(json.dumps(result, indent=2))
    return 0 if result["detector_discriminates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
