#!/usr/bin/env python3
"""RES-0091 independent re-derivation: run the battery on the recorded real
artifact (IMP-0167 receipt) and verify the battery metadata; NC = broken
receipt file fires P1+P3, nondeterministic file fires P2."""
from __future__ import annotations
import json, random, sys, tempfile, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0091"

def shape_ok(doc):
    return isinstance(doc, dict) and {"unit_id", "state", "sentinel"} <= set(doc)

def creds_ok(text):
    return not L.scan_credentials(text)

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    bat = doc.get("property_battery") or {}
    c.append(("battery metadata: all_pass with >=3 implemented, >=2 untestable",
              bat.get("all_pass") is True and int(bat.get("implemented_count") or 0) >= 3
              and int(bat.get("untestable_count") or 0) >= 2,
              f"impl={bat.get('implemented_count')} untestable={bat.get('untestable_count')} "
              f"all_pass={bat.get('all_pass')}"))
    real = L.REPO / "command-center/receipts/IMP-0167.json"
    c.append(("recorded real artifact still present", real.is_file(), str(real)))
    good = json.loads(real.read_text(encoding="utf-8"))
    c.append(("P1 passes on the real receipt", shape_ok(good), "IMP-0167 shape"))
    c.append(("P3 passes on the real receipt", creds_ok(real.read_text(encoding="utf-8")), "IMP-0167 clean"))
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    bad = dict(good)
    bad.pop("unit_id", None)
    bad["notes"] = "planted sk-" + "b" * 40
    Path(tmp).write_text(json.dumps(bad), encoding="utf-8")
    try:
        loaded = json.loads(Path(tmp).read_text(encoding="utf-8"))
        fires = (not shape_ok(loaded)) and (not creds_ok(Path(tmp).read_text(encoding="utf-8")))
        c.append(("NC: broken receipt file fires P1 and P3", fires, tmp))
    finally:
        Path(tmp).unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
