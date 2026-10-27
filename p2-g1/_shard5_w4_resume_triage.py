#!/usr/bin/env python3
"""Static triage for builder shard 5 wave 4 units (pre-probe check)."""
import json
import hashlib
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
MINE = ["BLD-0049", "BLD-0058", "BLD-0059", "CC-0009", "CC-0010", "CC-0012",
        "CC-0019", "CNF-0077", "CNF-0132", "CNF-0133", "CNF-0136", "CNF-0147"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat["work_units"] if u["id"] in MINE}
    for uid in MINE:
        u = units[uid]
        out = REPO / u["output_path"].replace("\\", "/")
        reasons = []
        doc = None
        if not out.is_file() or out.stat().st_size <= 0:
            reasons.append("artifact-absent")
        else:
            text = out.read_text(encoding="utf-8")
            try:
                doc = json.loads(text)
            except Exception:
                reasons.append("unparseable")
            if doc is not None:
                st = str(doc.get("state", "")).upper()
                if st in NOT_DELIVERING:
                    reasons.append("self-declared:" + st)
                sent = u.get("completion_sentinel", "")
                if sent and ("SUCCESS:" + uid) not in text and sent not in text:
                    reasons.append("sentinel-absent")
        ret_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
        man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if not ret_p.is_file():
            reasons.append("subagent-return-absent")
        else:
            try:
                ret = json.loads(ret_p.read_text(encoding="utf-8"))
                st_ret = str(ret.get("status") or ret.get("state", "")).upper()
                if st_ret in NOT_DELIVERING:
                    reasons.append("return:" + st_ret)
            except Exception:
                reasons.append("return-unparseable")
        if not man_p.is_file():
            reasons.append("manifest-absent")
        else:
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
                rows = [a for a in man.get("artifacts", [])
                        if isinstance(a, dict) and a.get("unit_id") == uid]
                if not rows:
                    reasons.append("manifest-row-absent")
                elif out.is_file():
                    live = digest(out)
                    ok = [a for a in rows
                          if str(a.get("path", "")).replace("\\", "/") == u["output_path"].replace("\\", "/")
                          and str(a.get("sha256", "")) == live
                          and a.get("present") is True]
                    if not ok:
                        reasons.append("manifest-sha-mismatch")
            except Exception:
                reasons.append("manifest-unparseable")
        # receipt reviewer state
        reviewer = ""
        if isinstance(doc, dict):
            rv = doc.get("reviewer") or {}
            if isinstance(rv, dict):
                reviewer = "reviewer:%s/indep=%s" % (rv.get("verdict"), rv.get("independent"))
        print("%s | %s | %s" % (uid, "STATIC-OK" if not reasons else ";".join(reasons), reviewer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
