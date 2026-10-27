"""Shard17 w4 static contract pre-check (mirrors _measure_one_delivered.py checks, no probe runs)."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
mine = ["TST-0032", "TST-0057", "TST-0060", "TST-0066", "TST-0067", "TST-0068",
        "TST-0070", "TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091"]

cat = json.load(open(CATALOG, encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")}

for uid in mine:
    u = units[uid]
    out_rel = str(u.get("output_path", "")).replace("\\", "/")
    out = REPO / out_rel
    msgs = []
    rev_info = ""
    if not out.is_file() or out.stat().st_size <= 0:
        msgs.append("ARTIFACT-ABSENT")
    else:
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
            if isinstance(doc, dict) and str(doc.get("state", "")).upper() in NOT_DELIVERING:
                msgs.append("SELF-DECLARED:" + str(doc.get("state")))
            sentinel = str(u.get("completion_sentinel") or "")
            if sentinel and sentinel not in text:
                msgs.append("SENTINEL-ABSENT")
        except Exception as e:
            msgs.append("UNPARSEABLE:" + type(e).__name__)
    ret_p = PROBES / uid / "SUBAGENT-RETURN.json"
    man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_p.is_file():
        msgs.append("SUBAGENT-RETURN-ABSENT")
    else:
        try:
            ret = json.loads(ret_p.read_text(encoding="utf-8"))
            st = str(ret.get("status") or ret.get("state") or "").upper()
            if st in NOT_DELIVERING:
                msgs.append("RET-STATUS:" + st)
            rev = ret.get("reviewer") or {}
            cls = (ret.get("failure") or {}).get("classification")
            rev_info = "ret.status=%r reviewer.verdict=%r independent=%r fail.class=%r" % (
                ret.get("status") or ret.get("state"),
                rev.get("verdict") if isinstance(rev, dict) else None,
                rev.get("independent") if isinstance(rev, dict) else None,
                cls)
        except Exception as e:
            msgs.append("RET-UNPARSEABLE:" + type(e).__name__)
    if not man_p.is_file():
        msgs.append("MANIFEST-ABSENT")
    else:
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = [a for a in (man.get("artifacts") or [])
                    if isinstance(a, dict) and a.get("unit_id") == uid]
            if not rows:
                msgs.append("MANIFEST-ROW-ABSENT")
            elif out.is_file():
                raw = out.read_bytes().replace(b"\r\n", b"\n")
                live = hashlib.sha256(raw).hexdigest()
                match = [a for a in rows
                         if str(a.get("path", "")).replace("\\", "/") == out_rel
                         and str(a.get("sha256", "")) == live
                         and a.get("present") is True]
                if not match:
                    msgs.append("MANIFEST-SHA-MISMATCH live=%s rows=%s" % (
                        live[:12], [str(a.get("sha256", ""))[:12] for a in rows]))
        except Exception as e:
            msgs.append("MANIFEST-UNPARSEABLE:" + type(e).__name__)
    verdict = "STATIC-OK" if not msgs else " | ".join(msgs)
    print("%s: %s%s" % (uid, verdict, (" :: " + rev_info) if rev_info else ""))
