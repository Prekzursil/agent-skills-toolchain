"""ADV-0019 independent mechanical re-derivation (review-from-raw, 2026-10-21).

Re-reads the raw probe outputs and the artifact; re-computes the control table and
answer lists from primitives; never imports probe verdict logic."""

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
    p1 = json.loads((DIR / "probe1-extract.json").read_text(encoding="utf-8"))
    p2 = json.loads((DIR / "probe2-resolve.json").read_text(encoding="utf-8"))

    for k, v in p1["controls"].items():
        if not v:
            problems.append(f"probe1 control {k} not PASS in raw")
    for k, v in p2["controls"].items():
        if not v:
            problems.append(f"probe2 control {k} not PASS in raw")
    dead_raw = sorted(p2["dead_mcp_servers_instructed"])
    ext = art.get("extensions", {})
    if ext.get("answer_dead_mcp_servers") is not None:
        if sorted(ext["answer_dead_mcp_servers"]) != dead_raw:
            problems.append("artifact dead-mcp list != raw probe2 list")
    if art.get("state") == "SUCCESS":
        if art.get("reviewer", {}).get("verdict") != "PASS":
            problems.append("SUCCESS artifact must carry reviewer PASS")
        for t in art.get("tests", []):
            if t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN"):
                problems.append(f"SUCCESS artifact carries test {t.get('id')} result={t.get('result')}")
        for c in art.get("negative_controls", []):
            if c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True:
                problems.append(f"control {c.get('id')} not both-states")
    for a in art.get("artifacts", []):
        if a["path"].endswith("review-from-raw.raw.txt"):
            continue  # reviewer's own output, rewritten each run
        p = REPO / a["path"]
        if not p.is_file():
            problems.append(f"declared artifact missing: {a['path']}")
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != a.get("sha256"):
            problems.append(f"declared artifact hash drift: {a['path']}")

    if problems:
        msg = "FAILED:adv0019-review " + "; ".join(problems)
        print(msg)
        (DIR / "review-from-raw.raw.txt").write_text(msg + "\n", encoding="utf-8")
        return 1
    out = (f"SUCCESS:adv0019-review raw supports artifact: probe1+probe2 controls PASS, "
           f"{len(dead_raw)} dead mcp servers re-derived, "
           f"{len(art.get('artifacts', []))} declared artifacts hash-match")
    print(out)
    (DIR / "review-from-raw.raw.txt").write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
