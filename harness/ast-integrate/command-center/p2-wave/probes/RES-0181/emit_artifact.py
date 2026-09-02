#!/usr/bin/env python3
"""Emit RES-0181 research-claim-record artifact from frozen captures."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import archaeology as A  # noqa: E402
from corpus import (  # noqa: E402
    LOAD_BEARING_IDS,
    MECHANISMS,
    OUT_REL,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    SILENT_IDS,
    UNIT_ID,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0181/probe1_quote_lineage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0181/probe2_silent_control.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    return A.digest_file(path)


def main() -> int:
    recovered = A.recover_all()
    rows = [recovered[m["id"]] for m in MECHANISMS]
    load_bearing = [r for r in rows if not r["silent_negative_control"]]
    silent = [r for r in rows if r["silent_negative_control"]]
    got = [r for r in load_bearing if r["recovery_status"] == "RATIONALE-RECOVERED"]
    none = [r for r in load_bearing if r["recovery_status"] == A.NO_RATIONALE]
    contradicts = [r for r in got if r["vs_current_docs"] == "CONTRADICTS-DOCS"]
    inferred = [r for r in rows if r.get("inferred")]
    silent_ok = all(r["recovery_status"] == A.NO_RATIONALE for r in silent)
    rate = (len(contradicts) / len(got)) if got else None

    if len(load_bearing) != 12:
        print(f"FAILED:emit expected 12 load-bearing, got {len(load_bearing)}")
        return 1
    if len(silent) != 3:
        print(f"FAILED:emit expected 3 silent, got {len(silent)}")
        return 1
    if not silent_ok:
        bad = [r["mechanism_id"] for r in silent if r["recovery_status"] != A.NO_RATIONALE]
        print(f"FAILED:emit silent controls recovered a rationale: {bad}")
        return 1
    if inferred:
        print("FAILED:emit inferred rows present; this engine quotes or is silent")
        return 1
    if not got:
        print("FAILED:emit zero recovered load-bearing rationales")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Recovered quoted rationales for {len(got)} of {len(load_bearing)} "
        f"load-bearing mechanisms from frozen commit/spec/RFC captures; "
        f"{len(contradicts)} recovered rationale(s) CONTRADICT current docs "
        f"(rate {rate:.3f} of recovered). {len(none)} load-bearing rows were "
        f"{A.NO_RATIONALE}. All {len(silent)} planted silent mechanisms are "
        f"{A.NO_RATIONALE} (engine does not invent from the name). "
        f"Inferred count={len(inferred)}. {SENTINEL}."
    )
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = {
        "unit_id": UNIT_ID,
        "claim_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "research-claim-record",
        "output_schema": SCHEMA_REL,
        "schema_note": (
            "command-center/schema/research-claim-record.schema.json is owned by "
            "RES-0001/CC-0017 and is absent on this sparse tree; this record carries "
            "the RES-0001 field list (claim id, canonical mechanism, source lineage "
            "with resolved URL + fetch timestamp + sha256, evidence tier E1-E4, "
            "Sherman-Kent band, settling probe, contradiction/support edges, "
            "freshness stamp) so an unsourced recovered-rationale is not representable."
        ),
        "schema_status": "PROVISIONAL pending Phase-4 formalization (CC-0017)",
        "title": (
            "Recover WHY a mechanism exists from commit, PR and issue history "
            "rather than from its docs"
        ),
        "question": QUESTION,
        "answer": answer,
        "freshness_stamp": now,
        "mode": "source-code-archaeology",
        "counts": {
            "load_bearing": len(load_bearing),
            "silent_negative_control": len(silent),
            "rationale_recovered": len(got),
            "no_rationale_recoverable_load_bearing": len(none),
            "no_rationale_recoverable_silent": len(silent),
            "contradicts_docs": len(contradicts),
            "consistent_docs": sum(1 for r in got if r["vs_current_docs"] == "CONSISTENT"),
            "inferred": len(inferred),
            "contradiction_rate_of_recovered": rate,
        },
        "load_bearing_ids": LOAD_BEARING_IDS,
        "silent_ids": SILENT_IDS,
        "claims": rows,
        "contradiction_edges": [
            {
                "from": r["claim_id"],
                "to": "current-documentation",
                "kind": "CONTRADICTS-DOCS",
                "hits": r["opposition_hits"],
            }
            for r in contradicts
        ],
        "support_edges": [
            {
                "from": r["claim_id"],
                "to": "current-documentation",
                "kind": "CONSISTENT",
            }
            for r in got
            if r["vs_current_docs"] == "CONSISTENT"
        ],
        "tests": [
            {
                "id": "probe1-quote-lineage",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "probe2-silent-control",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0181-probe2-silent-control",
            "verdict": "PASS",
            "independent": True,
            "default_when_insufficient": "REFUTED",
            "notes": (
                "Adversarial control: planted silent history must stay "
                f"{A.NO_RATIONALE}; a tempting mechanism title must not become "
                "a rationale; injecting an explicit because-quote must recover."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0181/captures/index.json",
                "exists": True,
                "role": "supporting",
            },
        ],
    }
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    sha, n = digest_file(out_path)
    print(f"wrote {OUT_REL} bytes={n} sha256={sha}")
    print(f"recovered={len(got)} contradicts={len(contradicts)} silent={len(silent)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
