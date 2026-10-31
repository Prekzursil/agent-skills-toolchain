#!/usr/bin/env python3
"""Fleet-wide STATIC delivered snapshot for the 2007-unit catalog.

Static proxy only (no live probe re-runs). Counts:
  A: artifact exists+non-empty+parses+not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  B: A + manifest sha row matches live bytes (CRLF-normalized)
  C: B + reviewer.verdict=PASS and reviewer.independent=true (artifact or receipt)
Also breaks down receipt states for units whose artifact is delivered.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    cat = load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    units = cat["work_units"]
    total = len(units)
    a = b = c = 0
    art_state = Counter()
    missing = []
    for u in units:
        uid = u.get("id")
        out = REPO / str(u.get("output_path", "")).replace("\\", "/")
        doc = None
        ok_a = False
        if out.is_file() and out.stat().st_size > 0:
            doc = load(out)
            if isinstance(doc, dict):
                if str(doc.get("state", "")).upper() not in NOT_DELIVERING:
                    text = out.read_text(encoding="utf-8")
                    sent = str(u.get("completion_sentinel", "") or "")
                    if not sent or sent in text or ("SUCCESS:" + uid) in text:
                        ok_a = True
        if ok_a:
            a += 1
            art_state[str(doc.get("state", "?"))] += 1
            man = load(REPO / "command-center" / "p2-wave" / "probes" / str(uid) / "UNIT-ARTIFACT-MANIFEST.json")
            ok_b = False
            if isinstance(man, dict):
                rows = [r for r in man.get("artifacts", [])
                        if isinstance(r, dict) and r.get("unit_id") == uid]
                live = digest(out)
                ok_b = any(str(r.get("path", "")).replace("\\", "/") == str(u.get("output_path", "")).replace("\\", "/")
                           and str(r.get("sha256", "")) == live
                           and r.get("present") is True for r in rows)
            if ok_b:
                b += 1
                closure = None
                rv = doc.get("reviewer")
                if isinstance(rv, dict):
                    closure = rv
                if not closure:
                    rj = load(REPO / "command-center" / "receipts" / (str(uid) + ".json"))
                    if isinstance(rj, dict):
                        rv2 = rj.get("reviewer")
                        if isinstance(rv2, dict):
                            closure = rv2
                if isinstance(closure, dict) and closure.get("verdict") == "PASS" and closure.get("independent") is True:
                    c += 1
        else:
            if len(missing) < 40:
                missing.append(uid)
    print("catalog total:", total)
    print("A artifact-static-ok:", a, "(%.1f%%)" % (100.0 * a / total))
    print("B +manifest-sha-match:", b, "(%.1f%%)" % (100.0 * b / total))
    print("C +reviewer-PASS/independent:", c, "(%.1f%%)" % (100.0 * c / total))
    print("remaining to full green (B):", total - b)
    print("remaining to full green (C):", total - c)
    print("artifact states among A:", dict(art_state))
    print("sample not-delivered ids:", missing[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
