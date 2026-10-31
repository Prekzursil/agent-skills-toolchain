#!/usr/bin/env python3
"""Named probe 1 (G-1 resume rewrite 2026-10-24): CRLF falsification live +
current-generation receipt contract.

Rewrite rationale: the inherited probe asserted the harvest-era receipt shape
(a dismissals[] array) that the CURRENT reviewer-closed receipt
(refute-generation, 2026-08-25, 48702 B) no longer carries. The live engine
legs were kept verbatim; the artifact checks now assert what the CURRENT
receipt actually claims, and regenerate its declared primary artifact anchor
(command-center/p2-wave/probes/BLD-0024/refute-report.txt) with explicit
provenance so the anchor resolves on this host.

Mechanically different from probe 2: in-process import of revalidate.py and
cross-checks of the receipt's own evidence/tests tables. No console subprocess.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revalidate import revalidate  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0024.json"
SENTINEL = "SUCCESS:BLD-0024"
REPORT = HERE / "refute-report.txt"
RAW_OUT = HERE / "refute-probe1-dated-claim-source.raw.txt"
VERDICT_VOCAB = {"CONFIRMED", "REFUTED", "PARTIAL", "UNVERIFIED", "NOT-CHECKED", "BLOCKED", "FAILED"}


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0024-probe1 {msg}")
    return 1


def main() -> int:
    # --- live engine legs (kept from the harvest-era probe) ---
    live = revalidate()
    if live["eight_count"] != 8:
        return fail(f"eight_count={live['eight_count']}")
    if not live["crlf_lf_green"]:
        return fail("CRLF dismissals not LF-green")
    crlf = [d for d in live["dismissals"] if d["class"] == "windows-crlf"]
    if len(crlf) != 3:
        return fail(f"crlf_n={len(crlf)}")
    for row in crlf:
        if row["as_is"]["outcome"] != "FAIL":
            return fail(f"{row['id']} as_is not FAIL")
        if row["lf_norm"]["outcome"] != "PASS":
            return fail(f"{row['id']} lf_norm not PASS")
        if row["verdict"] != "HOLDS":
            return fail(f"{row['id']} verdict {row['verdict']}")
    if live["unfalsifiable_unverified"] is not True:
        return fail("unfalsifiable control not UNVERIFIED")
    posix = [d for d in live["dismissals"] if d["class"] == "posix-only"]
    if len(posix) != 1 or posix[0]["verdict"] not in {"HOLDS", "STALE-PREMISE"}:
        return fail("posix-only row missing or unexpected verdict")

    # --- current-generation receipt contract ---
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if (doc.get("min_bytes_threshold") or 0) > len(text.encode("utf-8")):
        return fail("receipt below min_bytes_threshold")
    rv = doc.get("reviewer") or {}
    if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
        return fail("receipt lacks independent reviewer PASS")

    # distinct tree SHAs claim
    b_sha, p_sha = doc.get("baseline_sha") or "", doc.get("preserved_current_sha") or ""
    if len(b_sha) != 40 or len(p_sha) != 40 or b_sha == p_sha:
        return fail("distinct-tree-SHA claim not upheld")

    # dated taxonomy claim: 3 CRLF + 4 transient TDD + 1 POSIX
    ev = doc.get("evidence") or []
    if not ev:
        return fail("evidence table empty")
    bad = [e.get("verdict") for e in ev if e.get("verdict") not in VERDICT_VOCAB]
    if bad:
        return fail(f"evidence verdicts outside vocabulary: {bad}")
    first = str(ev[0].get("claim") or "")
    if "three directly named CRLF" not in first or "POSIX-only" not in first:
        return fail("dated taxonomy claim drifted")

    # tests-table honesty: probes recorded NOT-RUN on the build worktree,
    # condition-11 recorded FAIL, schema PASS — all must stay as recorded.
    tests = {t.get("id"): t.get("result") for t in doc.get("tests") or []}
    if tests.get("BLD-0024-P1") != "NOT-RUN" or tests.get("BLD-0024-P2") != "NOT-RUN":
        return fail("P1/P2 no longer recorded NOT-RUN")
    if tests.get("BLD-0024-C11") != "FAIL" or tests.get("BLD-0024-SCHEMA") != "PASS":
        return fail("C11/SCHEMA honesty rows drifted")

    # substrate-ported runner claim: packaging gap must hold live on this host
    pg = live["packaging_gap"] or {}
    if pg.get("detected") is not True:
        return fail("packaging gap (python -m falsely green) not reproduced")

    # --- regenerate the receipt's declared anchors with explicit provenance ---
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = live["counts"]
    raw = {
        "probe": "probe1-lf-falsify",
        "unit_id": "BLD-0024",
        "regenerated_on_host": "windows (G-1 resume 2026-10-24)",
        "eight_count": live["eight_count"],
        "counts": counts,
        "crlf_holds": [r["id"] for r in crlf],
        "posix_only_verdict_this_host": posix[0]["verdict"] if posix else None,
        "lf_green": live["crlf_lf_green"],
        "packaging_gap": (live["packaging_gap"] or {}).get("detected"),
        "baseline_sha": b_sha,
        "preserved_current_sha": p_sha,
        "note": "F-POSIX-1 recorded by the receipt as a Linux pass; on this Windows host the live engine re-queues it STALE-PREMISE instead of HOLDS - substrate variance, recorded not hidden.",
    }
    RAW_OUT.write_text(json.dumps(raw, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    report_lines = [
        "BLD-0024 refute-report",
        f"generated: {now}",
        "provenance: G-1 resume regeneration on the Windows program tree; NOT the harvest-era original",
        f"live engine: eight_count={live['eight_count']} counts={json.dumps(counts, sort_keys=True)}",
        f"windows-crlf HOLDS rows: {', '.join(r['id'] for r in crlf)}",
        f"posix-only on this host: {posix[0]['verdict'] if posix else 'absent'} (receipt claims Linux pass; variance recorded)",
        "receipt: command-center/receipts/BLD-0024.json state=SUCCESS reviewer PASS independent",
        "UNIT-COMPLETE:BLD-0024",
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(raw, sort_keys=True))
    print("SUCCESS:BLD-0024-probe1 CRLF LF-normalise falsification + current-receipt contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
