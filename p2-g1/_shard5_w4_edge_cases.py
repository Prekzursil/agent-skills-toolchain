#!/usr/bin/env python3
"""Edge-case detail: stale manifests + non-SUCCESS artifact states + disposition fields."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def digest(path: Path) -> str:
    return hashlib_sha(path)


def hashlib_sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    cat = load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    stale = []
    nostate = []
    disp_counter = {}
    for u in cat["work_units"]:
        uid = u["id"]
        d = u.get("disposition") or u.get("terminal_disposition") or u.get("status")
        if d:
            disp_counter[str(d)] = disp_counter.get(str(d), 0) + 1
        pd = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if not pd.is_file():
            continue
        out = REPO / str(u.get("output_path", "")).replace("\\", "/")
        doc = load(out) if out.is_file() else None
        if not (out.is_file() and out.stat().st_size > 0 and isinstance(doc, dict)
                and str(doc.get("state", "")).upper() not in NOT_DELIVERING):
            continue
        text = out.read_text(encoding="utf-8")
        sent = str(u.get("completion_sentinel", "") or "")
        if sent and sent not in text and ("SUCCESS:" + uid) not in text:
            continue
        man = load(pd)
        rows = [r for r in man.get("artifacts", []) if isinstance(r, dict) and r.get("unit_id") == uid]
        live = hashlib_sha(out)
        ok = any(str(r.get("path", "")).replace("\\", "/") == str(u.get("output_path", "")).replace("\\", "/")
                 and str(r.get("sha256", "")) == live and r.get("present") is True for r in rows)
        if not ok:
            stale.append((uid, "rows=%d" % len(rows)))
        st = str(doc.get("state", ""))
        if st != "SUCCESS":
            nostate.append((uid, st))
    print("stale-manifest units:", stale)
    print("non-SUCCESS artifact states:", nostate)
    print("per-unit disposition fields found:", disp_counter or "NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
