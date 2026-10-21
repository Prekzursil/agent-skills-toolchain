"""ADV-0014 independent mechanical re-derivation (review-from-raw, 2026-10-21)."""

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
    p1 = json.loads((DIR / "probe1-surface.json").read_text(encoding="utf-8"))
    p2 = json.loads((DIR / "probe2-mcp.json").read_text(encoding="utf-8"))

    if not p1["controls"]["CTRL-DETECTOR-VALID-AND-INVALID"]:
        problems.append("probe1 detector control not PASS")
    for k, v in p2["controls"].items():
        if not v:
            problems.append(f"probe2 control {k} not PASS")
    present = sum(1 for r in p1["rows"] if r["on_path"])
    if present != 9:
        problems.append(f"expected 9 binaries on PATH per raw, found {present}")
    dead = sum(1 for r in p2["rows"] if r["verdict"] == "REFUTED")
    conf = sum(1 for r in p2["rows"] if r["verdict"] == "CONFIRMED")
    if art.get("state") == "SUCCESS":
        if art.get("reviewer", {}).get("verdict") != "PASS":
            problems.append("SUCCESS artifact must carry reviewer PASS")
        for t in art.get("tests", []):
            if t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                problems.append(f"test {t.get('id')} result={t.get('result')}")
        for c in art.get("negative_controls", []):
            if c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True:
                problems.append(f"control {c.get('id')} not both-states")
        ext = art.get("extensions", {})
        if "answer" not in ext:
            problems.append("SUCCESS artifact missing extensions.answer")
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
        msg = "FAILED:adv0014-review " + "; ".join(problems)
        print(msg)
        (DIR / "review-from-raw.raw.txt").write_text(msg + "\n", encoding="utf-8")
        return 1
    out = (f"SUCCESS:adv0014-review raw supports artifact: {present}/9 binaries live with "
           f"control PASS, {conf} CONFIRMED + {dead} REFUTED MCP ids re-derived, "
           f"{len(art.get('artifacts', []))} declared artifacts hash-match")
    print(out)
    (DIR / "review-from-raw.raw.txt").write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
