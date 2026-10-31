r"""H5 — locate the hook whose OWN subprocess reader thread dies on cp1252.

The Stop dispatch emits a UnicodeDecodeError traceback from
`subprocess.py:_readerthread` at ~680 KB into a child's output. That is NOT the
audit harness (which decodes bytes explicitly); it is a hook calling
subprocess with text/universal_newlines and no encoding=, so Python decodes the
child with the Windows ANSI codepage (cp1252) and throws on the first byte
outside it. The reader thread dies -> the hook fails open -> the check produces
NOTHING, silently.

Two independent probes:
  1. STATIC: scan every live hook script for a subprocess call that decodes
     text without an explicit encoding=.
  2. DYNAMIC: run each Stop check alone in a subprocess and see which one
     reproduces the traceback. A static hit that does not reproduce is a
     candidate, not the culprit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path("C:/Users/Prekzursil/.claude/hooks")
OUT = REPO / "command-center" / "hook-audit"

SUBPROC = re.compile(r"subprocess\.(run|check_output|Popen|call)\s*\(", re.S)
TEXTY = re.compile(r"\b(text\s*=\s*True|universal_newlines\s*=\s*True|encoding\s*=)")

RUNNER = r"""
import io,sys,json,importlib.util,threading,re
p=sys.argv[1]; payload=sys.argv[2]
spec=importlib.util.spec_from_file_location("solo",p)
m=importlib.util.module_from_spec(spec); sys.modules["solo"]=m
spec.loader.exec_module(m)
sys.stdin=io.StringIO(payload)
buf=io.StringIO(); real=sys.stdout; sys.stdout=buf
try:
    fn=getattr(m,"main",None)
    import inspect
    n=len(inspect.signature(fn).parameters) if fn else 0
    rc = (fn([]) if n>=1 else fn()) if fn else "NO-MAIN"
finally:
    sys.stdout=real
real.write(json.dumps({"rc":repr(rc),"out_bytes":len(buf.getvalue())}))
"""


def static_scan() -> list[dict]:
    hits = []
    for p in sorted(LIVE.rglob("*.py")):
        if "__pycache__" in str(p) or p.name.startswith("test_"):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in SUBPROC.finditer(src):
            seg = src[m.start() : m.start() + 700]
            depth, end = 0, len(seg)
            for i, ch in enumerate(seg[seg.index("(") :], start=seg.index("(")):
                depth += ch == "("
                depth -= ch == ")"
                if depth == 0:
                    end = i + 1
                    break
            call = seg[:end]
            texty = "text=True" in call or "universal_newlines=True" in call
            has_enc = "encoding=" in call
            if texty and not has_enc:
                hits.append(
                    {
                        "file": str(p.relative_to(LIVE)).replace("\\", "/"),
                        "line": src[: m.start()].count("\n") + 1,
                        "call": " ".join(call.split())[:220],
                    }
                )
    return hits


def dynamic_probe() -> list[dict]:
    man = json.loads((LIVE / "_dispatch/manifest.json").read_text(encoding="utf-8"))
    payload = json.dumps(
        {"session_id": "hookaudit", "cwd": str(REPO), "stop_hook_active": False}
    )
    rows = []
    for chk in (man["events"]["Stop"] or {}).get("checks") or []:
        sp = (LIVE / chk["script"]).resolve()
        if not sp.is_file():
            continue
        t0 = time.perf_counter()
        p = subprocess.run(
            [sys.executable, "-c", RUNNER, str(sp), payload],
            capture_output=True,
            timeout=200,
        )
        ms = (time.perf_counter() - t0) * 1000
        se = p.stderr.decode("utf-8", "replace")
        rows.append(
            {
                "name": chk.get("name"),
                "budget_s": chk.get("timeout"),
                "wall_ms": round(ms, 1),
                "pct_of_budget": round(100.0 * (ms / 1000) / chk["timeout"], 1)
                if chk.get("timeout")
                else None,
                "exit": p.returncode,
                "cp1252_traceback": "charmap" in se or "UnicodeDecodeError" in se,
                "stderr_bytes": len(p.stderr),
                "stderr_tail": se[-300:],
            }
        )
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    st = static_scan()
    print(f"== STATIC: subprocess text-decode without encoding= ({len(st)} hits)")
    for h in st:
        print(f"   {h['file']}:{h['line']}  {h['call'][:150]}")

    dy = dynamic_probe()
    print("\n== DYNAMIC: each Stop check run ALONE")
    for r in sorted(dy, key=lambda x: -x["wall_ms"]):
        flag = "CP1252!!" if r["cp1252_traceback"] else "        "
        print(
            f"{flag} {str(r['name'])[:28]:28s} {r['wall_ms']:9.1f} ms /{str(r['budget_s']):>3}s"
            f" = {str(r['pct_of_budget']):>6}%  exit={r['exit']} err={r['stderr_bytes']}B"
        )
        if r["cp1252_traceback"]:
            print(f"          tail| {r['stderr_tail'].strip().splitlines()[-1][:160]}")
    culprits = [r["name"] for r in dy if r["cp1252_traceback"]]
    (OUT / "H5-CP1252.json").write_text(
        json.dumps({"static": st, "dynamic": dy, "culprits": culprits}, indent=2),
        encoding="utf-8",
    )
    print(f"\nCULPRITS (reproduced): {culprits}")
    print("SUCCESS:h5-cp1252")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
