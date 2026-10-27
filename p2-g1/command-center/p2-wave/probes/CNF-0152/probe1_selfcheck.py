#!/usr/bin/env python3
"""CNF-0152 probe1: hostile-path matrix coherence - six shape rows, every HAZARD-CONFIRMED
verdict carries its instantiated path, and the honesty block records the substrate scope
(including the NUL-mount crash evidence string). Emitted by shard8-w2 resume builder."""
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
    d = load("command-center/receipts/CNF-0152.json")
    m = d["matrix"]
    ck("six_shape_rows", len(m) == 6)
    shapes = {r.get("id") for r in m}
    ck("five_required_shapes_plus_one",
       {"a-long-root", "b-reserved-device", "c-case-collision", "d-non-ascii", "e-spaces"}.issubset(shapes))
    ok = True
    for r in m:
        ok &= r.get("verdict") == "HAZARD-CONFIRMED"
        ok &= bool(r.get("path_used"))
    ck("all_rows_hazard_confirmed_with_paths", ok)
    h = d.get("honesty", {})
    ck("substrate_recorded", h.get("substrate") == "linux")
    ck("windows_scope_recorded", h.get("windows_os_not_executed") is True)
    blob = json.dumps(d)
    ck("nul_mount_crash_string_recorded", ("NUL" in blob) and ("mount" in blob.lower()))
    ck("sentinel_in_artifact", "SUCCESS:CNF-0152" in (REPO / "command-center/receipts/CNF-0152.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0152")

if __name__ == "__main__":
    sys.exit(main())
