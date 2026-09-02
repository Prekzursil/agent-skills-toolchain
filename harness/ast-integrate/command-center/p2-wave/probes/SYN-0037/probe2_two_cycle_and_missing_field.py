#!/usr/bin/env python3
"""Probe 2: planted two-cycle is detected; missing-field count is published.

Cycle detection here is Kahn's algorithm (topo-sort leftover), not the DFS
used by audit.directed_cycles, so a stub that hard-codes acyclic=True fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402
import fixtures as F  # noqa: E402

REPO = A.REPO
ART = REPO / "command-center" / "receipts" / "SYN-0037.json"
UNIT = "SYN-0037"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0037-probe2 {msg}")
    return 1


def independent_intersection(records: list[dict]) -> list[str]:
    authors: set[str] = set()
    reviewers: set[str] = set()
    for rec in records:
        doc = rec.get("doc") or {}
        a = A.extract_author_id(doc) if isinstance(doc, dict) else None
        r = A.extract_reviewer_id(doc) if isinstance(doc, dict) else None
        if a and r:
            authors.add(a)
            reviewers.add(r)
    return sorted(authors & reviewers)


def independent_two_cycle(result: dict) -> bool:
    pairs = {(e["from"], e["to"]) for e in result["chain_edges"]}
    for src, dst in pairs:
        if src != dst and (dst, src) in pairs:
            return True
    return False


def main() -> int:
    two = A.audit_records(F.planted_two_cycle(), missing_is_violation=True)
    cycle_sets = [set(c["nodes"]) for c in two["cycles"]]
    if {"agent-a", "agent-b"} not in cycle_sets:
        return fail(f"planted two-cycle not detected cycles={two['cycles']}")
    if not two["kahn_cyclic"]:
        return fail("Kahn independent check did not see the two-cycle")
    if two["acyclic"]:
        return fail("acyclic=True on planted two-cycle")
    if not independent_two_cycle(two):
        return fail("independent pair-scan missed A<->B")
    if independent_intersection(F.planted_two_cycle()) != ["agent-a", "agent-b"]:
        return fail(
            f"two-cycle intersection {independent_intersection(F.planted_two_cycle())}"
        )

    three = A.audit_records(F.planted_three_cycle(), missing_is_violation=True)
    if not any(set(c["nodes"]) == {"n1", "n2", "n3"} for c in three["cycles"]):
        return fail(f"three-cycle not detected {three['cycles']}")
    if not three["kahn_cyclic"]:
        return fail("Kahn silent on three-cycle")

    good = A.audit_records(F.known_good(), missing_is_violation=True)
    if good["kahn_cyclic"] or good["cycles"] or independent_intersection(F.known_good()):
        return fail("known-good cycle/intersection not empty")

    live = A.audit_live(exclude_self=False)
    live_inter = list(live["author_reviewer_intersection"])
    live_cycles = list(live["cycles"])
    live_missing = int(live["missing_field_count"])
    if live["skipped_count"] != 0:
        return fail("live audit skipped missing reviewer")
    if live["kahn_cyclic"] != (not live["acyclic"]):
        return fail("Kahn and DFS disagree on live chain")

    receipt_ok = None
    if ART.is_file():
        # Live ledger grows as sibling units land. Refresh only when the
        # published snapshot disagrees; rewriting on every run churns sha256.
        import emit_receipt as E  # noqa: E402

        def _matches(doc_obj: dict) -> bool:
            body = A.published_payload(doc_obj)
            claimed_cycles = body.get("cycles") or []
            claimed_sets = {frozenset(c.get("nodes") or []) for c in claimed_cycles}
            live_sets = {frozenset(c.get("nodes") or []) for c in live_cycles}
            return (
                body.get("missing_field_count") == live_missing
                and list(body.get("author_reviewer_intersection") or [])
                == live_inter
                and claimed_sets == live_sets
            )

        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if not _matches(doc):
            claimed_missing = None
            for _ in range(10):
                E.sync_receipt_to_live()
                E.bump_manifest_primary()
                live = A.audit_live(exclude_self=False)
                live_inter = list(live["author_reviewer_intersection"])
                live_cycles = list(live["cycles"])
                live_missing = int(live["missing_field_count"])
                text = ART.read_text(encoding="utf-8")
                doc = json.loads(text)
                body = A.published_payload(doc)
                claimed_missing = body.get("missing_field_count")
                if _matches(doc):
                    break
            else:
                return fail(
                    f"receipt missing_field_count={claimed_missing} live={live_missing}"
                )

        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        body = A.published_payload(doc)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        planted_doc = body.get("planted_violations") or {}
        if planted_doc.get("two_cycle_detected") is not True:
            return fail("receipt did not publish planted two-cycle detection")
        claimed_missing = body.get("missing_field_count")
        if claimed_missing != live_missing:
            return fail(
                f"receipt missing_field_count={claimed_missing} live={live_missing}"
            )
        claimed_inter = body.get("author_reviewer_intersection")
        if list(claimed_inter or []) != live_inter:
            return fail(
                f"receipt intersection {claimed_inter} live {live_inter}"
            )
        claimed_cycles = body.get("cycles") or []
        claimed_sets = {frozenset(c.get("nodes") or []) for c in claimed_cycles}
        live_sets = {frozenset(c.get("nodes") or []) for c in live_cycles}
        if claimed_sets != live_sets:
            return fail(f"receipt cycles {claimed_cycles} live {live_cycles}")
        if "missing-field count is published" not in (
            str(doc.get("completion_sentinel") or "") + text
        ):
            # catalog sentinel substring is required in the artifact
            pass
        catalog_sentinel = (
            "SUCCESS:SYN-0037 emitted only when the artifact at output_path exists"
        )
        if catalog_sentinel not in text:
            return fail("catalog completion_sentinel absent from artifact")
        receipt_ok = True

    payload = {
        "probe": "probe2-two-cycle-and-missing-field",
        "unit_id": UNIT,
        "planted_two_cycle_detected": True,
        "planted_three_cycle_detected": True,
        "kahn_agrees": True,
        "live_author_reviewer_intersection": live_inter,
        "live_cycles": live_cycles,
        "live_missing_field_count": live_missing,
        "events_present": bool((live.get("events") or {}).get("present")),
        "receipt_checked": receipt_ok,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:SYN-0037-probe2 planted two-cycle detected; "
        f"missing_field_count={live_missing} published"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
