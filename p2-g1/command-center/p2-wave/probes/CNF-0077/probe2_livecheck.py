#!/usr/bin/env python3
"""CNF-0077 probe2: live re-derivation - re-run the LOAD classification for every load-error row
and structurally re-verify every executed row's src + recorded failure text.
Emitted by shard8-w2 resume builder 2026-10-25. Self-contained; stdlib only."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/confirmation/CNF-0077-blueprint-executability.json")
    rows = d["blueprints"]
    load_rows = [r for r in rows if r["invocation"] == "LOAD"]
    exec_rows = [r for r in rows if r["invocation"] != "LOAD"]
    ck("twelve_load_rows_recorded", len(load_rows) == 12)
    live_load_error = 0
    for r in load_rows:
        p = REPO / r["path"]
        cls = "load-error"
        if p.is_file():
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                if doc.get("stages"):
                    cls = "loaded-with-stages"
            except Exception:
                cls = "load-error"
        if cls == "load-error":
            live_load_error += 1
    ck("load_rows_reproduce_load_error_live", live_load_error == 12)
    exec_missing = [r["path"] for r in exec_rows if not (REPO / r["path"]).is_file()]
    ck("executed_rows_src_present_today", not exec_missing)
    ck("executed_rows_carry_error_text", all(r.get("error") for r in exec_rows))
    ck("executed_rows_all_nonzero_exit", all(r.get("exit_code", 1) != 0 for r in exec_rows))
    ck("total_rows_114", len(rows) == 114)
    return finish("probe2_livecheck", "CNF-0077")

if __name__ == "__main__":
    sys.exit(main())
