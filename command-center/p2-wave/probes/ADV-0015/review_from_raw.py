"""ADV-0015 independent mechanical re-derivation (review-from-raw, 2026-10-21)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
REPO = DIR.parents[3]


def main(artifact_path: str) -> int:
    problems: list[str] = []
    art = json.loads((REPO / artifact_path).read_text(encoding="utf-8"))
    p1 = json.loads((DIR / "probe1-vendor-diff.json").read_text(encoding="utf-8"))
    p2 = json.loads((DIR / "probe2-runtime.json").read_text(encoding="utf-8"))

    for k in ("CTRL-VENDOR-PAGE-LIVE", "CTRL-CURRENT-ID-RESOLVES"):
        if not p1["controls"].get(k):
            problems.append(f"probe1 control {k} not PASS")
    for k in ("CTRL-BOTH-STATES", "CTRL-NO-SILENT-SUBSTITUTION"):
        if not p2["controls"].get(k):
            problems.append(f"probe2 control {k} not PASS")
    statuses = {v["status"] for v in p1["pages"].values()}
    if statuses != {200}:
        problems.append(f"vendor page statuses not all 200: {statuses}")
    loud = [r for r in p2["rows"] if not r["case"].startswith("supported")]
    if not all(r["exit"] != 0 for r in loud):
        problems.append("a non-supported id exited 0 (silent substitution uncaught)")
    if p2["silent_substitution_detected"]:
        problems.append("silent substitution detected but artifact may claim healthy")

    if art.get("state") == "SUCCESS":
        if art.get("reviewer", {}).get("verdict") != "PASS":
            problems.append("SUCCESS artifact must carry reviewer PASS")
        for t in art.get("tests", []):
            if t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                problems.append(f"test {t.get('id')} result={t.get('result')}")
        for c in art.get("negative_controls", []):
            if c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True:
                problems.append(f"control {c.get('id')} not both-states")
        tgt = art.get("report", {}).get("targets", [{}])[0]
        if tgt.get("verdict") != "REFUTED":
            problems.append("target verdict must be REFUTED given the measured drift")
    for a in art.get("artifacts", []):
        if a["path"].endswith("review-from-raw.raw.txt"):
            continue
        p = REPO / a["path"]
        if not p.is_file():
            problems.append(f"declared artifact missing: {a['path']}")
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != a.get("sha256"):
            problems.append(f"hash drift: {a['path']}")

    if problems:
        msg = "FAILED:adv0015-review " + "; ".join(problems)
        print(msg)
        (DIR / "review-from-raw.raw.txt").write_text(msg + "\n", encoding="utf-8")
        return 1
    out = (f"SUCCESS:adv0015-review raw supports artifact: pages 200x3, price drift + "
           f"retirement split re-derived, runtime loud-fail re-derived, "
           f"{len(art.get('artifacts', []))} declared artifacts hash-match")
    print(out)
    (DIR / "review-from-raw.raw.txt").write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
