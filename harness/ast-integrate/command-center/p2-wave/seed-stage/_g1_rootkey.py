#!/usr/bin/env python3
"""Re-key the current fails by the FILE a repair has to touch (02.09, meta lens F3).

Signature clustering (`_g1_landscape.py`) masks away exactly the class/module/attribute that
identify the root cause, so 80 % of its clusters are singletons. This tool keys each failing
unit by, in order:
  1. `cannot import name 'X' from 'm' (path)`  -> path (real module missing a name X)
  2. `module 'm' has no attribute 'x'`          -> file of m (resolved on the measurement path)
  3. `No module named 'm'`                       -> m (module to create), key `MISSING:m`
  4. `G1-STRICT placeholder module 'm' at path`  -> path (placeholder to make real)
  5. any other exception                         -> innermost traceback frame under the repo that is
                                                    NOT inside probes/<ID>/ (the code that raised)
  6. else                                        -> `PROBE:<unit>` (assertion in the probe: per-unit)

Usage: python3 _g1_rootkey.py [out.json] [min_size]
Prints groups largest first: `n key : units` and the split shared (n>1) vs per-unit.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import ROOT, WIN, latest_rows  # noqa: E402

ROOTS = [WIN, WIN / "tools", WIN / "platform" / "lib", WIN / "tools" / "agentspec"]
RE_IMPORT_NAME = re.compile(r"cannot import name '([^']+)' from '([^']+)' \(([^)]+)\)")
RE_MOD_ATTR = re.compile(r"module '([^']+)' has no attribute '([^']+)'")
RE_NO_MODULE = re.compile(r"No module named '([^']+)'")
RE_STRICT = re.compile(r"G1-STRICT placeholder module '([^']+)' at (\S+)")
RE_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
RE_EXC = re.compile(r"^\s*([A-Za-z_][\w.]*(?:Error|Exception|Exit|Warning))\b:?\s*(.*)$")


def rel(path: str) -> str:
    for base in (str(ROOT), str(WIN), str(Path.home() / "p2-g1")):
        if path.startswith(base + "/"):
            return path[len(base) + 1 :]
    return path


def resolve_module(dotted: str) -> str:
    parts = dotted.split(".")
    if parts and parts[0] in {"marketplace", "plugin", "workflow_foundry", "council", "router", "bench"}:
        cands = [WIN / "tools" / Path(*parts), WIN / Path(*parts)]
    else:
        cands = [r / Path(*parts) for r in ROOTS]
    for c in cands:
        if (c / "__init__.py").is_file():
            return (c / "__init__.py").relative_to(WIN).as_posix()
        if Path(str(c) + ".py").is_file():
            return Path(str(c) + ".py").relative_to(WIN).as_posix()
    return f"MISSING:{dotted}"


def key_for(uid: str, rec: dict) -> tuple[str, str]:
    tail = str(rec.get("tail") or "")
    line = str(rec.get("line") or "")
    m = RE_STRICT.search(tail)
    if m:
        return rel(m.group(2)), "placeholder"
    m = RE_IMPORT_NAME.search(tail)
    if m:
        return rel(m.group(3)), f"import-name:{m.group(1)}"
    m = RE_MOD_ATTR.search(tail)
    if m:
        return resolve_module(m.group(1)), f"module-attr:{m.group(2)}"
    m = RE_NO_MODULE.search(tail)
    if m:
        return f"MISSING:{m.group(1)}", "no-module"
    lines = [ln for ln in tail.splitlines() if ln.strip()]
    exc = None
    for ln in reversed(lines):
        mm = RE_EXC.match(ln.strip())
        if mm and mm.group(1) not in ("SystemExit",):
            exc = mm.group(0).strip()[:120]
            break
    if exc:
        frames = RE_FRAME.findall(tail)
        for fpath, _lineno, _fn in reversed(frames):
            r = rel(fpath)
            if fpath.startswith("<") or r.startswith("command-center/p2-wave/probes/") or r.startswith("/") or "site-packages" in r or r.startswith("command-center/p2-wave/seed-stage/") or r.startswith("usr/"):
                continue
            return r, f"exc:{exc}"
        return f"PROBE:{uid}", f"exc-in-probe:{exc}"
    if "probe-exit:124" in line or "TIMEOUT" in tail:
        return "TIMEOUT", "timeout"
    return f"PROBE:{uid}", f"assert:{line[:100]}"


def main() -> int:
    rows = latest_rows()
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for uid, rec in sorted(rows.items()):
        if rec.get("ok"):
            continue
        k, why = key_for(uid, rec)
        groups[k].append((uid, why))
    min_size = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    shared = [(k, v) for k, v in ordered if len(v) > 1 and not k.startswith("PROBE:")]
    total = sum(len(v) for v in groups.values())
    print(f"fails={total} keys={len(groups)} shared-keys={len(shared)} units-in-shared={sum(len(v) for _, v in shared)} per-unit={sum(1 for k in groups if k.startswith('PROBE:'))}")
    for k, v in ordered:
        if len(v) < min_size:
            continue
        print(f"{len(v):4d}  {k}")
        print("      " + " ".join(f"{u}[{w.split(':',1)[0]}]" for u, w in v[:16]) + (" ..." if len(v) > 16 else ""))
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps({"fails": total, "groups": [{"key": k, "n": len(v), "units": [{"id": u, "why": w} for u, w in v]} for k, v in ordered]}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
