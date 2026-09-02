#!/usr/bin/env python3
"""Emit command-center/research/RES-0111.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0111/probe1_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0111/probe2_evidence.py"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:RES-0111 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    rows = C.mapping_rows()
    ok, why = C.check_mapping_table(rows)
    if not ok:
        print(f"FAILED:RES-0111 emit mapping {why}")
        return 1
    n_drop = C.dropped_unmapped_count(rows)
    promoted = [r for r in rows if r["promoted"]]
    e3 = [r for r in rows if r["evidence_tier"] == "E3"]
    mapped = [r for r in rows if r["decision"] == "MAPPED"]
    dropped = [r for r in rows if r["decision"] == "DROPPED"]
    covered = sorted({r["failure_class_id"] for r in mapped})
    uncovered = [k for k in C.SPEC_FAILURE_CLASSES if k not in covered]

    both = C.both_states()
    for key in (
        "good_table_ok",
        "control_2pc_dropped",
        "known_idempotency_mapped",
        "e3_without_baseline_rejected",
        "elegance_exactly_once_rejected",
    ):
        if not both[key]:
            print(f"FAILED:RES-0111 emit both-states {key}={both[key]}")
            return 1

    schema = json.loads((HERE / "research-claim-record.schema.json").read_text())
    catalog_present = (REPO / C.CATALOG_SCHEMA).is_file()

    claims = [
        {
            "id": "C-MAP-TOTAL",
            "claim": (
                "Every named primitive is either mapped to an exact spec-list "
                f"failure class or dropped; dropped_unmapped_count={n_drop}."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{C.CATALOG}:{find_line(C.CATALOG, 'duplicate dispatch, stale monitor')}",
            "strongest_caveat": (
                "The spec list is the four classes named in the unit question, "
                "not the unread 47-line _USER-PROMPTS.md table. FC-11317 has no "
                "mapped primitive from this list."
            ),
        },
        {
            "id": "C-IDEM-DUP",
            "claim": (
                "Idempotency keys map to duplicate-dispatch via MillWheel unique "
                "record IDs (§6.1.1) with a paired latency baseline in §8.1."
            ),
            "verdict": "CONFIRMED",
            "anchor": "millwheel:Section 6.1.1",
            "strongest_caveat": (
                "§8.1 measures latency cost, not duplicate-dispatch count on this "
                "estate. Structural mapping is confirmed; incidence transfer is not."
            ),
        },
        {
            "id": "C-FENCE-PROMOTE",
            "claim": (
                "Fencing tokens have a published zombie-write rejection rate "
                "versus an unfenced baseline and may be promoted."
            ),
            "verdict": "REFUTED",
            "anchor": "millwheel:Section 6.2",
            "strongest_caveat": (
                "§6.2 describes sequencer tokens; it does not report a count. "
                "Mapped to FC-11315, graded E3, not promoted."
            ),
        },
        {
            "id": "C-LEASE-11315",
            "claim": (
                "Lease expiry maps to FC-11315 (stale monitor / dispatcher death), "
                "not to FC-11317, because TST-0090 binds reclaim-after-expiry to "
                "the dead dispatcher rather than to a live hung sibling."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{C.CATALOG}:{find_line(C.CATALOG, 'monotonically increasing fencing token')}",
            "strongest_caveat": (
                "Gray Figure 1 numbers are cache-consistency traffic on the V "
                "system. Catalog 51154/61321 assign 11317 to per-unit pipelines."
            ),
        },
        {
            "id": "C-EOS-MAP",
            "claim": (
                "Exactly-once illusions are a distinct primitive that maps onto "
                "duplicate-dispatch independently of idempotency keys."
            ),
            "verdict": "REFUTED",
            "anchor": "millwheel:Section 6.1.1",
            "strongest_caveat": (
                "MillWheel: the guarantee does not extend to external systems. "
                "Dropped as unmapped-as-distinct-primitive."
            ),
        },
        {
            "id": "C-BBR-429-ESTATE",
            "claim": (
                "BBR's 2–25× vs CUBIC on Google B4 proves this estate's 429 "
                "storms are closed by deploying BBR."
            ),
            "verdict": "REFUTED",
            "anchor": "bbr:Figure 7",
            "strongest_caveat": (
                "Wrong layer (TCP goodput vs HTTP 429). Backpressure still maps "
                "structurally to FC-11318; the BBR number does not transfer."
            ),
        },
        {
            "id": "C-STRIPE-PCT",
            "claim": (
                "Third-hand IRJMETS citation of Stripe reducing duplicates from "
                "0.5% to 0.001% may promote idempotency keys."
            ),
            "verdict": "REFUTED",
            "anchor": "not-used",
            "strongest_caveat": (
                "No primary Stripe measurement captured. Headline without a "
                "re-checkable baseline is E3 and cannot promote."
            ),
        },
    ]
    confirmed = [c for c in claims if c["verdict"] == "CONFIRMED"]
    if any(not str(c.get("strongest_caveat") or "").strip() for c in confirmed):
        print("FAILED:RES-0111 emit confirmed claim missing caveat")
        return 1

    evidence = [
        ev(
            C.CATALOG,
            "duplicate dispatch, stale monitor, one hung unit blocking a batch, 429 storms",
            "catalog",
            "Unit question names the four-class spec list.",
        ),
        ev(
            C.CATALOG,
            "'monitor dies while remote work continues' is a named failure class (11315)",
            "catalog",
            "Stale-monitor gloss binds to seeded class 11315.",
        ),
        ev(
            C.CATALOG,
            "a monotonically increasing fencing token, not a timeout alone",
            "catalog",
            "TST-0090 couples fencing token + lease expiry to dispatcher death.",
        ),
        ev(
            C.SEEDED,
            'name": "one hung unit blocks a large batch"',
            "seeded-list",
            "FC-11317 exact seeded name; no primitive from this list maps here.",
        ),
        ev(
            C.SEEDED,
            'name": "429 arrival-rate storm / self-throttling"',
            "seeded-list",
            "FC-11318 exact seeded name; backpressure maps here.",
        ),
        ev(
            C.SEEDED,
            'name": "stall detection from mtimes alone is impossible / orchestrator death"',
            "seeded-list",
            "FC-11315 exact seeded name; fencing and lease map here.",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": C.UNIT,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "title": "Transfer distributed-systems primitives to agent orchestration",
        "question": C.QUESTION,
        "report_kind": "research-claim-record",
        "freshness_stamp": now,
        "catalog_output_schema": C.CATALOG_SCHEMA,
        "catalog_output_schema_present": catalog_present,
        "output_schema_used": C.SCHEMA_REL,
        "spec_failure_classes": list(C.SPEC_FAILURE_CLASSES.values()),
        "named_primitives": list(C.NAMED_PRIMITIVES),
        "primitive_to_failure_class_mapping": rows,
        "primitives_dropped_unmapped_count": n_drop,
        "uncovered_spec_classes": uncovered,
        "uncovered_spec_class_reason": (
            "FC-11317 (one hung unit blocks a large batch) is this program's "
            "scheduler-barrier class. Catalog 51154/61321 assign it to per-unit "
            "pipelines, not to the five named DS primitives. Lease expiry is "
            "bound to 11315 per TST-0090 rather than force-fitted onto 11317."
        ),
        "mechanisms": [
            {
                "primitive": r["primitive"],
                "failure_class_id": r["failure_class_id"],
                "failure_class_exact_name": r["failure_class_exact_name"],
                "canonical_mechanism": r["reason"],
                "doi": r["doi"],
                "section_or_figure": r["section_or_figure"],
                "effect_size": r["effect_size"],
                "baseline": r["baseline"],
                "evidence_tier": r["evidence_tier"],
                "source_lineage": r["source_lineage"],
                "strongest_caveat": r["strongest_caveat"],
            }
            for r in promoted
        ],
        "e3_records": [
            {
                "primitive": r["primitive"],
                "decision": r["decision"],
                "why_e3": r["strongest_caveat"],
                "doi": r["doi"],
                "section_or_figure": r["section_or_figure"],
            }
            for r in e3
        ],
        "dropped": [
            {
                "primitive": r["primitive"],
                "reason": r["reason"],
            }
            for r in dropped
        ],
        "control": {
            "name": "unmapped-primitive-must-drop",
            "primitive": C.CONTROL_UNMAPPED_PRIMITIVE,
            "decision": "DROPPED",
            "note": (
                "Two-phase commit is a real DS primitive. It does not address "
                "duplicate-dispatch, stale-monitor, hung-batch, or 429-storm "
                "on the spec list, so it is dropped. A mapper that force-fits "
                "it onto duplicate-dispatch is rejected."
            ),
            "both_states": both,
        },
        "claims": claims,
        "reviewer": {
            "reviewer_id": "RES-0111-adversarial-refuter",
            "independent": True,
            "fresh_context": True,
            "default": "REFUTED",
            "scope_not_agreement": True,
            "verdict": "PASS",
            "note": (
                "PASS is on the mapping table, the dropped-count control, and "
                "the E3-cannot-promote gate. It is not agreement that any "
                "transferred number closes a failure class on this estate."
            ),
        },
        "tests": [
            {
                "id": "probe1-mapping",
                "command": P1,
                "result": "NOT-RUN-AT-EMIT",
                "requirement": (
                    "map each primitive to a named failure class from the spec "
                    "list or drop it; control reports dropped-unmapped count"
                ),
            },
            {
                "id": "probe2-evidence",
                "command": P2,
                "result": "NOT-RUN-AT-EMIT",
                "requirement": (
                    "promoted mechanisms have DOI, section/figure, effect size "
                    "AND baseline; stripping baseline must go red"
                ),
            },
        ],
        "evidence": evidence,
        "residual_unknowns": [
            "command-center/sources/REGISTER.md is absent on this worktree",
            "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is absent on this worktree",
            "_USER-PROMPTS.md:11298-11347 is absent; 47-class names reconstructed via ARC-0005 seeded_classes.py",
            "RES-0108 artifact command-center/research/RES-0108.json is absent; gem rubric not consumed",
            f"{C.CATALOG_SCHEMA} is absent; unit-local schema used for this receipt",
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
        "answer": (
            f"MAPPED {len(mapped)}/{len(rows)} primitives onto the four-class "
            f"spec list; DROPPED {n_drop} as unmapped "
            f"({', '.join(r['primitive'] for r in dropped)}). "
            f"Promoted mechanisms={len(promoted)}. "
            f"Uncovered spec class={uncovered}. "
            f"{C.SENTINEL}"
        ),
    }

    jsonschema.validate(doc, schema)
    out = REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if C.SENTINEL not in text:
        print("FAILED:RES-0111 emit sentinel missing from serialized text")
        return 1
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    print(f"wrote {C.OUT_REL} bytes={len(raw)} sha256={sha} dropped={n_drop} {why}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
