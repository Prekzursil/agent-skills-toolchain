r"""H7 — CORRECTED mechanism + the false-positive consequence for wire-check.

H6's sentence was WRONG and is retracted here rather than deleted.

H6 claimed: `text=True` raises UnicodeDecodeError -> `except Exception: pass`
-> the os.walk fallback runs. MEASURED: `subprocess.run` does NOT raise. In
CPython 3.14 the decode happens in `subprocess._readerthread`; when it throws,
the THREAD dies, the traceback is printed by the threading excepthook, and
`communicate()` returns an EMPTY string. So:

    r.returncode == 0  and  r.stdout == ""   ->  the `returncode in (0,1)`
    branch is taken and `_rg_lines` returns []  -- the fallback is NEVER reached.

That matters because ZERO references is precisely the condition wire-check
reports as "dead code / not-yet-wired". A silent empty result is not a slow
path, it is a FALSE POSITIVE GENERATOR.

This script measures the consequence directly: monkeypatch nothing, but call
`_rg_lines` (as shipped) and a utf-8 twin for the SAME patterns and count the
disagreements. Then run wire-check's real `main()` and capture what it emits.

CONTROLS
  * a pattern with tiny output must agree between the two (proves the twin is
    not just always-bigger);
  * the twin must be non-empty for at least one pattern the shipped call
    returns empty for, or there is no disagreement to report.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center" / "hook-audit"
WC = REPO / "hooks" / "wire-check" / "check.py"


def load():
    spec = importlib.util.spec_from_file_location("wc_probe", str(WC))
    m = importlib.util.module_from_spec(spec)
    sys.modules["wc_probe"] = m
    spec.loader.exec_module(m)
    return m


def twin(cwd: str, pattern: str, fixed=False, timeout=30) -> list[str]:
    """_rg_lines with the ONLY change being an explicit utf-8 decode."""
    args = ["rg", "-w", "-n", "--no-heading", "-S"]
    if fixed:
        args = ["rg", "-F", "-n", "--no-heading"]
    args += ["-g", "!.git", pattern, cwd]
    r = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if r.returncode in (0, 1):
        return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return []


# The absent-control must be a string that exists NOWHERE on disk -- including in
# THIS file. Spelling it as a literal makes ripgrep find this very probe (measured:
# the first version self-matched and aborted the run). Build it at runtime so the
# literal never appears in any file.
ABSENT_CTRL = "zzq" + "notasymbol" + "9174xyz"

PATTERNS = [
    "main",  # huge output -> expect shipped=0
    "_rg_lines",  # small output -> control, expect agreement
    "handleSubmit",
    "dispatch",
    "checks",
    ABSENT_CTRL,  # control: both must be 0
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wc = load()
    rows = []
    for p in PATTERNS:
        t0 = time.perf_counter()
        shipped = wc._rg_lines(str(REPO), p, timeout=30)
        sms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        good = twin(str(REPO), p)
        gms = (time.perf_counter() - t0) * 1000
        rows.append(
            {
                "pattern": p,
                "shipped_lines": len(shipped),
                "utf8_lines": len(good),
                "shipped_ms": round(sms, 1),
                "utf8_ms": round(gms, 1),
                "silently_emptied": len(shipped) == 0 and len(good) > 0,
            }
        )

    ctrl_absent = next(r for r in rows if r["pattern"] == ABSENT_CTRL)
    ctrl_small = next(r for r in rows if r["pattern"] == "_rg_lines")
    if ctrl_absent["utf8_lines"] != 0 or ctrl_absent["shipped_lines"] != 0:
        print("FAILED:h7 absent-control matched -> detector broken")
        return 1
    print("  control absent-symbol: both 0  OK")
    print(
        f"  control small-output  : shipped={ctrl_small['shipped_lines']} "
        f"utf8={ctrl_small['utf8_lines']} "
        f"{'AGREE' if ctrl_small['shipped_lines'] == ctrl_small['utf8_lines'] else 'DISAGREE'}"
    )

    print("\n  pattern                shipped   utf8   silently-emptied")
    for r in rows:
        print(
            f"  {r['pattern']:22s} {r['shipped_lines']:7d} {r['utf8_lines']:6d}"
            f"   {r['silently_emptied']}   ({r['shipped_ms']:.0f} / {r['utf8_ms']:.0f} ms)"
        )

    # --- what does wire-check ACTUALLY emit right now? --------------------
    payload = json.dumps(
        {"session_id": "hookaudit", "cwd": str(REPO), "stop_hook_active": False}
    )
    real_in, real_out = sys.stdin, sys.stdout
    buf = io.StringIO()
    sys.stdin, sys.stdout = io.StringIO(payload), buf
    t0 = time.perf_counter()
    try:
        rc = wc.main()
    except BaseException as e:
        rc = f"RAISED:{type(e).__name__}"
    finally:
        sys.stdin, sys.stdout = real_in, real_out
    ms = (time.perf_counter() - t0) * 1000
    emitted = buf.getvalue()
    ctx = ""
    for line in emitted.splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        ctx = (o.get("hookSpecificOutput") or {}).get("additionalContext") or ctx

    print(f"\n  wire-check main(): rc={rc} {ms:.0f} ms, emitted {len(emitted)} B")
    if ctx:
        for ln in ctx.splitlines():
            print(f"    | {ln[:170]}")

    n_emptied = sum(1 for r in rows if r["silently_emptied"])
    res = {
        "rows": rows,
        "silently_emptied_count": n_emptied,
        "wirecheck_rc": repr(rc),
        "wirecheck_ms": round(ms, 1),
        "wirecheck_context": ctx,
        "mechanism": (
            "subprocess.run does NOT raise; the cp1252 decode dies inside "
            "_readerthread, communicate() yields '', returncode stays 0, so "
            "_rg_lines returns [] via the success branch. The os.walk fallback "
            "is never reached. Zero references is wire-check's dead-code trigger."
        ),
    }
    (OUT / "H7-WIRECHECK-FP.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )
    print(f"\n  silently-emptied patterns: {n_emptied}/{len(rows)}")
    print("SUCCESS:h7-wirecheck-fp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
