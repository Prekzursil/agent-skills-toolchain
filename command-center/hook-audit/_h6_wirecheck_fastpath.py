r"""H6 — BOTH-STATES proof that wire-check's ripgrep fast path is DEAD on this box.

hooks/wire-check/check.py::_rg_lines (:126-135) is:

    try:
        args = ["rg", ...]
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode in (0, 1):
            return [...]
    except Exception:
        pass
    # stdlib fallback (bounded) -- only used if ripgrep is unavailable.

`text=True` with no `encoding=` decodes the child with the Windows ANSI codepage
(cp1252). Ripgrep's output over this repo contains bytes outside cp1252, so the
decode raises INSIDE subprocess's reader thread, `run()` propagates, the bare
`except Exception: pass` swallows it, and control falls into the os.walk
fallback whose own comment says it is "only used if ripgrep is unavailable".

Ripgrep IS available. The comment is wrong about which state the code is in.

STATE A (as shipped)  : text=True, no encoding   -> expect UnicodeDecodeError
STATE B (one-word fix): encoding="utf-8", errors="replace" -> expect success

A detector that only ran STATE B would prove nothing; a detector that only ran
STATE A could be blamed on a broken rg. Both are run, plus an rg-exists control.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center" / "hook-audit"
PATTERN = "main"  # a symbol wire-check would plausibly probe


def rg_args(cwd: str, pattern: str) -> list[str]:
    return ["rg", "-w", "-n", "--no-heading", "-S", "-g", "!.git", pattern, cwd]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {"pattern": PATTERN, "cwd": str(REPO)}

    rg = shutil.which("rg")
    res["rg_on_path"] = rg
    if not rg:
        print("FAILED:h6 ripgrep not on PATH -- the fallback would be legitimate")
        return 1
    print(f"  control: ripgrep present at {rg}")

    # --- STATE A: exactly as shipped -------------------------------------
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            rg_args(str(REPO), PATTERN), capture_output=True, text=True, timeout=60
        )
        res["state_A"] = {
            "raised": False,
            "returncode": r.returncode,
            "lines": len((r.stdout or "").splitlines()),
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as e:
        res["state_A"] = {
            "raised": True,
            "exc": type(e).__name__,
            "msg": str(e)[:200],
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    # --- STATE B: the one-word fix ---------------------------------------
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            rg_args(str(REPO), PATTERN),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        res["state_B"] = {
            "raised": False,
            "returncode": r.returncode,
            "lines": len((r.stdout or "").splitlines()),
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as e:
        res["state_B"] = {
            "raised": True,
            "exc": type(e).__name__,
            "msg": str(e)[:200],
            "ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    # --- cost of the fallback that state A silently selects ---------------
    import sys

    sys.path.insert(0, str(REPO / "hooks" / "wire-check"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "wc", str(REPO / "hooks" / "wire-check" / "check.py")
    )
    wc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wc)
    t0 = time.perf_counter()
    got = wc._rg_lines(str(REPO), PATTERN)
    res["shipped_rg_lines"] = {
        "ms": round((time.perf_counter() - t0) * 1000, 1),
        "lines": len(got),
        "hit_4000_cap": len(got) > 4000,
    }

    a, b, s = res["state_A"], res["state_B"], res["shipped_rg_lines"]
    print(f"\n  STATE A (as shipped, text=True)      : {a}")
    print(f"  STATE B (encoding='utf-8')           : {b}")
    print(f"  shipped _rg_lines() one call         : {s}")

    verdict = a.get("raised") and not b.get("raised") and b.get("lines", 0) > 0
    res["fastpath_dead_confirmed"] = bool(verdict)
    if verdict:
        print(
            "\n  VERDICT: fast path DEAD. State A raises "
            f"{a['exc']}; state B returns {b['lines']} lines in {b['ms']} ms. "
            f"The shipped call takes {s['ms']} ms via the os.walk fallback "
            f"= {round(s['ms'] / max(b['ms'], 0.001), 1)}x slower."
        )
    else:
        print("\n  VERDICT: NOT reproduced -- state A did not raise. Claim withdrawn.")
    (OUT / "H6-WIRECHECK-FASTPATH.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )
    print("SUCCESS:h6-wirecheck-fastpath")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
