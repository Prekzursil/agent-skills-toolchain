#!/usr/bin/env python3
"""Re-pin ADV-0127 manifest + SUBAGENT-RETURN sha rows to the refreshed artifact."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
PROBE = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0127"


def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    spec = importlib.util.spec_from_file_location("adv0127_clock_lib2", PROBE / "clock_lib.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adv0127_clock_lib2"] = mod
    spec.loader.exec_module(mod)
    out_rel = mod.OUT_REL
    live_sha, live_bytes = norm_sha(REPO / out_rel)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = False

    man_p = PROBE / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_p.read_text(encoding="utf-8"))
    for row in man.get("artifacts") or []:
        if (
            isinstance(row, dict)
            and row.get("unit_id") == "ADV-0127"
            and str(row.get("path", "")).replace("\\", "/") == out_rel
            and row.get("sha256") != live_sha
        ):
            row["sha256"] = live_sha
            row["bytes"] = live_bytes
            row["present"] = True
            changed = True
    if changed:
        man_p.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"manifest row updated={changed} sha={live_sha[:16]} bytes={live_bytes}")

    ret_p = PROBE / "SUBAGENT-RETURN.json"
    ret = json.loads(ret_p.read_text(encoding="utf-8"))
    ret_changed = False
    for a in ret.get("artifacts") or []:
        if (
            isinstance(a, dict)
            and str(a.get("path", "")).replace("\\", "/") == out_rel
            and a.get("sha256") != live_sha
        ):
            a["sha256"] = live_sha
            a["bytes"] = live_bytes
            a["exists"] = True
            ret_changed = True
    if ret_changed:
        ret["ts"] = now
        ret_p.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"subagent-return updated={ret_changed}")
    print(f"SUCCESS:ADV-0127 manifest re-pinned to {live_sha[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
