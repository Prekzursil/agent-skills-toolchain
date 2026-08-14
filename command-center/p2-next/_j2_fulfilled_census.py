"""How many of the rail-blocked units have ALREADY consumed cross-vendor review?

`vendor_satisfiability.py:403` classifies purely on the reviewer vendor a receipt
DEMANDS and never reads `reviewer.verdict`. So a unit that already holds an executed
cross-vendor Codex PASS is still counted as unmet review capacity. That is an
owner-facing number, so it gets its own measurement and its own control.

DISCRIMINATING CONTROL (the point of this file):
Two counters run over the SAME rows.
  * `has_any_reviewer`  -- a receipt carries a reviewer block with a verdict.
  * `cross_vendor_pass` -- verdict PASS AND independent is true AND the reviewer_id
                           FIELD names an openai/codex reviewer.
If the two counters agree on both populations, the second is measuring reviewer
PRESENCE rather than cross-vendor FULFILMENT and must not be reported. The
SATISFIABLE_NOW population is the discriminator: all ten were reviewed by a
fresh-context Anthropic reviewer, so `has_any_reviewer` must be high there while
`cross_vendor_pass` must be zero.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
ART_REL = "command-center/p2-next/VENDOR-SATISFIABILITY.json"

# Matched against the reviewer_id FIELD only -- never against free prose. A document
# that merely NAMES codex is not a codex review (use-vs-mention).
OPENAI_RE = re.compile(r"\b(openai|codex[-\s]?(cli|exec)?)\b", re.I)
ANTHROPIC_RE = re.compile(r"\b(anthropic|claude)\b", re.I)


def show(rev: str, rel: str) -> str | None:
    """Stored blob. `git show <rev>:<path>` returns the blob with 0 CRLF (measured)."""
    proc = subprocess.run(
        ["git", "show", f"{rev}:{rel}"],
        capture_output=True,
        text=True,
        cwd=REPO,
        shell=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def reviewer_of(rec: dict) -> dict:
    rv = rec.get("reviewer")
    return rv if isinstance(rv, dict) else {}


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    art = show(rev, ART_REL)
    if art is None:
        print(f"FAILED:j2-census artifact absent at {rev}")
        return 1
    rows = json.loads(art)
    rows = rows["units"] if isinstance(rows, dict) and "units" in rows else rows

    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["verdict"], []).append(r)

    report: dict[str, object] = {"rev": rev, "populations": {}}
    ids_cross: dict[str, list[str]] = {}

    for verdict, group in sorted(buckets.items()):
        has_any = 0
        cross_pass = 0
        anth_pass = 0
        no_reviewer = 0
        hits = []
        seen_ids = []
        for r in group:
            rec_txt = show(rev, r["output_path"])
            if rec_txt is None:
                no_reviewer += 1
                continue
            try:
                rec = json.loads(rec_txt)
            except Exception:
                no_reviewer += 1
                continue
            rvw = reviewer_of(rec)
            vid = str(rvw.get("reviewer_id") or "")
            verd = str(rvw.get("verdict") or "").upper()
            indep = rvw.get("independent") is True
            if verd:
                has_any += 1
                seen_ids.append(f"{r['id']}|{verd}|{vid[:60]}")
            else:
                no_reviewer += 1
                continue
            if verd == "PASS" and indep and OPENAI_RE.search(vid):
                cross_pass += 1
                hits.append({"id": r["id"], "reviewer_id": vid})
            elif verd == "PASS" and indep and ANTHROPIC_RE.search(vid):
                anth_pass += 1
        report["populations"][verdict] = {
            "n": len(group),
            "has_any_reviewer": has_any,
            "cross_vendor_pass": cross_pass,
            "anthropic_pass": anth_pass,
            "no_reviewer_verdict": no_reviewer,
        }
        ids_cross[verdict] = hits
        print(f"\n==== {verdict}: {len(group)} units ====")
        print(f"  has_any_reviewer   : {has_any}")
        print(f"  cross_vendor_pass  : {cross_pass}   {[h['id'] for h in hits]}")
        print(f"  anthropic_pass     : {anth_pass}")
        print(f"  no reviewer verdict: {no_reviewer}")
        for s in seen_ids[:3]:
            print(f"    sample: {s}")

    report["cross_vendor_pass_ids"] = ids_cross

    # ---- the control ------------------------------------------------------
    sat = report["populations"].get("SATISFIABLE_NOW", {})
    rail = report["populations"].get("RAIL_BLOCKED", {})
    discriminates = (
        sat.get("has_any_reviewer", 0) > 0
        and sat.get("cross_vendor_pass", -1) == 0
        and rail.get("has_any_reviewer", 0) != rail.get("n", 0)
    )
    report["control_discriminates"] = discriminates
    print("\n---- CONTROL ----")
    print(
        f"  SATISFIABLE_NOW has_any_reviewer={sat.get('has_any_reviewer')} "
        f"cross_vendor_pass={sat.get('cross_vendor_pass')}  "
        f"(must be >0 and 0 -- else the counter reads presence, not vendor)"
    )
    print(f"  control discriminates: {discriminates}")

    out = pathlib.Path(__file__).with_name("J2-FULFILLED-CENSUS.json")
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\nwrote {out}")

    if not discriminates:
        print("FAILED:j2-census the two counters do not separate; reading is inert")
        return 1
    print("SUCCESS:j2-census counters separate; cross-vendor fulfilment is measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
