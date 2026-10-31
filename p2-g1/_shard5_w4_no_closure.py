#!/usr/bin/env python3
"""Which manifest-ok units lack reviewer closure; static-fail detail."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    import hashlib
    cat = load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    no_closure = []
    static_fail = []
    for u in cat["work_units"]:
        uid = u["id"]
        out = REPO / str(u.get("output_path", "")).replace("\\", "/")
        doc = load(out) if out.is_file() else None
        ok_a = (out.is_file() and out.stat().st_size > 0 and isinstance(doc, dict)
                and str(doc.get("state", "")).upper() not in NOT_DELIVERING)
        if ok_a:
            text = out.read_text(encoding="utf-8")
            sent = str(u.get("completion_sentinel", "") or "")
            if sent and sent not in text and ("SUCCESS:" + uid) not in text:
                ok_a = False
        if not ok_a:
            if out.is_file():
                why = "parse" if doc is None else ("self-declared:%s" % str(doc.get("state", "")))
            else:
                why = "absent"
            static_fail.append((uid, why))
            continue
        man = load(REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
        if not isinstance(man, dict):
            continue
        rows = [r for r in man.get("artifacts", []) if isinstance(r, dict) and r.get("unit_id") == uid]
        live = hashlib.sha256(out.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        ok_b = any(str(r.get("path", "")).replace("\\", "/") == str(u.get("output_path", "")).replace("\\", "/")
                   and str(r.get("sha256", "")) == live and r.get("present") is True for r in rows)
        if not ok_b:
            continue
        closure = None
        rv = doc.get("reviewer") if isinstance(doc, dict) else None
        if isinstance(rv, dict):
            closure = rv
        if not (isinstance(closure, dict) and closure.get("verdict") == "PASS" and closure.get("independent") is True):
            rj = load(REPO / "command-center" / "receipts" / (uid + ".json"))
            rv2 = rj.get("reviewer") if isinstance(rj, dict) else None
            if isinstance(rv2, dict) and rv2.get("verdict") == "PASS" and rv2.get("independent") is True:
                closure = rv2
        if not (isinstance(closure, dict) and closure.get("verdict") == "PASS" and closure.get("independent") is True):
            no_closure.append(uid)
    print("static-fail units (artifact layer):", static_fail)
    print("manifest-ok but NO reviewer closure:", no_closure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
