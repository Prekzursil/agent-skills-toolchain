#!/usr/bin/env python3
"""Emit command-center/phase3/A4/SECURITY.json for ARC-0027.

Does not write A4 DESIGN.json. Cloud ok is not consulted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import anchors as A
import overclaim as O
import paths as P
import reviewer as R
import schema_gate as SG
import sequence as S

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/phase3/A4/SECURITY.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
A4_FIXTURE = "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A4/DESIGN.json"
A1_PRECEDENCE = (
    "command-center/p2-wave/probes/ARC-0004/fixtures/estate/t0-baseline/precedence.json"
)
GATEWAY = "command-center/p2-wave/probes/ARC-0027/gateway.py"
DESIGN_A4 = "command-center/phase3/A4/DESIGN.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0027/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0027/probe2_path_enumeration.py"
)
QUESTION = (
    "Does lazy activation create a permission time-of-check/time-of-use gap? "
    "Determine whether the permission decision is made at INDEX time, "
    "SELECTION time or ACTIVATION time, whether a capability's declared "
    "permissions can change between those points, and specify where the "
    "authoritative check must live - then prove no activation path bypasses "
    "it by enumerating every path."
)
CLAIM = (
    "Lazy activation does not create a permission TOCTOU window because an "
    "index-time ALLOW remains valid through activate, declared grants cannot "
    "change between those epochs, and A4 DESIGN.json already places the check."
)
SNIP_Q = "Does lazy activation create a permission time-of-check/time-of-use gap?"
SNIP_BOTH = "with the check at activation time the edited permission must be caught"
SNIP_PATHS = "every activation entry point is listed with a file:line"
SNIP_EV = "The TOCTOU window is demonstrated or excluded"
SNIP_A4FIX = '"architecture_name": "gateway / lazy-activation"'
SNIP_A1 = '"no_resident_runtime": true'
SNIP_GW = "def authorize_activation"


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / rel, snippet)
    ok, why = A.resolve_anchor(REPO, rel, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0027 emit anchor {why}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    if (REPO / DESIGN_A4).is_file():
        print("FAILED:ARC-0027 emit A4 DESIGN.json present; do not rebuild-circle")
        return 1

    both = S.both_states()
    if not both["pass"]:
        print("FAILED:ARC-0027 both-states")
        print(
            json.dumps(
                {
                    k: both[k]
                    for k in ("index_slipped", "activation_caught", "selection_also_slips")
                },
                indent=2,
            )
        )
        return 1

    path_run = P.run()
    if not path_run["pass"]:
        print("FAILED:ARC-0027 path enumeration")
        print(json.dumps(path_run["completeness"], indent=2))
        return 1

    rev = R.review()
    if not rev["pass"]:
        print("FAILED:ARC-0027 reviewer bypasses")
        return 1

    e1 = ev(CATALOG, SNIP_Q, "live-tree", "Catalog asks whether lazy activation creates a permission TOCTOU gap.")
    e2 = ev(CATALOG, SNIP_BOTH, "live-tree", "Catalog requires both-states: activation-time catch, index-time slip.")
    e3 = ev(CATALOG, SNIP_PATHS, "live-tree", "Catalog requires every activation entry point listed with file:line.")
    e4 = ev(CATALOG, SNIP_EV, "live-tree", "Catalog requires a scratch index/edit/activate sequence with grants printed.")
    e5 = ev(
        A4_FIXTURE,
        SNIP_A4FIX,
        "dossier",
        "Reconstructed A4 pipeline fixture (not live phase3/A4/DESIGN.json) is gateway / lazy-activation.",
    )
    e6 = ev(
        A1_PRECEDENCE,
        SNIP_A1,
        "dossier",
        "A1-class fixture records no_resident_runtime; config-first cannot host an activation-time re-read.",
    )
    e7 = ev(GATEWAY, SNIP_GW, "live-tree", "Scratch A4 gateway places the authoritative choke in authorize_activation.")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    activation_paths = []
    for row in path_run["paths"]:
        activation_paths.append(
            {
                "id": row["id"],
                "function": row["function"],
                "path": row["path"],
                "line": row["line"],
                "check_function": row["check_function"],
                "check_path": row["check_path"],
                "check_line": row["check_line"],
                "crosses_check": row["crosses_check"],
            }
        )

    doc = {
        "unit_id": "ARC-0027",
        "state": "SUCCESS",
        "schema_version": 1,
        "sentinel": "SUCCESS:ARC-0027",
        "completion_sentinel": "SUCCESS:ARC-0027",
        "architecture_id": "A4",
        "architecture_class": "gateway-lazy-activation",
        "title": "A4 (gateway / lazy-activation): Permission TOCTOU across index, selection, and activation",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "answer": (
            "Yes: lazy activation creates a permission TOCTOU window if the "
            "decision is cached at INDEX or SELECTION and reused at ACTIVATE. "
            "Declared permissions can change between those points (scratch "
            "sequence: tool:Read -> tool:Read+tool:Bash). The authoritative "
            "check must live at ACTIVATION time, re-reading declared grants; "
            "every activation entry point must cross authorize_activation. "
            "A4 DESIGN.json is absent and was not rebuilt. SUCCESS:ARC-0027"
        ),
        "authoritative_check_epoch": "activation",
        "design_present": False,
        "design_path": DESIGN_A4,
        "design_note": (
            "A4 DESIGN.json is absent (ARC-0024 not delivered). This unit does "
            "not rebuild DESIGN.json. Placement is proven on the scratch "
            "gateway and pinned to catalog sentences plus reconstructed A4/"
            "A1-class fixture dossiers that exist on this worktree."
        ),
        "cloud_ok": False,
        "headline_verdict": "TOCTOU-AT-INDEX-CONFIRMED-CHECK-MUST-BE-ACTIVATION",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "security-reviewer",
            "execution_substrate": "headless-linux",
        },
        "both_states": {
            "index_slipped": both["index_slipped"],
            "activation_caught": both["activation_caught"],
            "selection_also_slips": both["selection_also_slips"],
            "index_activate_outcome": both["index"]["activate_outcome"],
            "index_effective_grant": both["index"]["activate_effective_grant"],
            "activation_activate_outcome": both["activation"]["activate_outcome"],
            "activation_effective_grant": both["activation"]["activate_effective_grant"],
            "printed_index": both["index"]["printed"],
            "printed_activation": both["activation"]["printed"],
            "printed_selection": both["selection"]["printed"],
            "scratch": both["scratch"],
        },
        "activation_paths": activation_paths,
        "planted_bypass": path_run["planted_bypass"],
        "path_completeness": path_run["completeness"],
        "runtime_path_crosses": path_run["runtime"],
        "claims": [
            {
                "id": "C1",
                "claim": "An index-time permission snapshot remains valid through activate.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e2["anchor"],
                "why_locus": (
                    "No A4 DESIGN.json encodes this rule. The claim is the unit "
                    "question's foil. Live scratch: index ALLOW on tool:Read, "
                    "edit adds tool:Bash, activate reuses cached ALLOW."
                ),
            },
            {
                "id": "C2",
                "claim": "The permission decision is made at SELECTION time.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e1["anchor"],
                "why_locus": (
                    "Selection only records an id unless check_epoch is selection. "
                    "When it does cache, the same TOCTOU slips. Selection is not "
                    "the authoritative epoch."
                ),
            },
            {
                "id": "C3",
                "claim": "Declared permissions cannot change between index and activate.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e4["anchor"],
                "why_locus": (
                    "Scratch copy edits skill.council from [tool:Read] to "
                    "[tool:Read, tool:Bash] after index and before activate."
                ),
            },
            {
                "id": "C4",
                "claim": (
                    "The authoritative check must live at ACTIVATION time, "
                    "re-read declared permissions, and every activation entry "
                    "point must cross it."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "SENTENCE",
                "anchor": e7["anchor"],
                "why_locus": (
                    "Both-states plus AST/runtime path enumeration on the scratch "
                    "gateway. A4 DESIGN.json is absent so this is not a DESIGN locus."
                ),
            },
            {
                "id": "C5",
                "claim": "A4 DESIGN.json already specifies the activation-time check.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e1["anchor"],
                "why_locus": (
                    "command-center/phase3/A4/DESIGN.json is absent. A missing "
                    "dossier cannot be a DESIGN locus and was not rebuilt."
                ),
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7],
        "scenario": {
            "id": "S1-toctou-index-edit-activate",
            "title": "Scratch index, edit declared permissions, activate",
            "silent_loss_file": (
                "command-center/p2-wave/probes/ARC-0027/fixtures/estate/"
                "capabilities/skill.council.json"
            ),
            "catching_architecture": (
                "A4 gateway with authorize_activation at activation epoch: "
                "re-read declared grants and DENY escalation. Index-time "
                "cached ALLOW is the failing control that lets tool:Bash slip."
            ),
            "procedure": [
                "1. Copy fixtures/estate to a tempfile scratch tree.",
                "2. Index capabilities; print effective grant at index (tool:Read).",
                "3. Select skill.council; print grant (not-checked at activation epoch).",
                "4. Edit declared permissions to add tool:Bash; print on-disk grant.",
                "5. Activate: index-epoch reuses cached ALLOW and slips; activation-epoch DENYs.",
                "6. Enumerate every activate_* / listed entry point with file:line and AST call to authorize_activation.",
            ],
            "on_this_estate": (
                f"index slipped={both['index_slipped']} "
                f"activation caught={both['activation_caught']} "
                f"selection also slips={both['selection_also_slips']} "
                f"A4 DESIGN present=False"
            ),
        },
        "strongest_surviving_counterargument": (
            "A write-lock on the capability record between index and activate, "
            "or a content-hash of declared permissions bound into the index "
            "ticket, would close TOCTOU without moving the check to activate. "
            "This unit does not implement that lock. The live proof is that an "
            "unlocked index-time decision slips; the required placement is "
            "therefore activate-time re-read (or an equivalent bind of the "
            "grant hash). Residual: A4 DESIGN.json is absent, so a future "
            "DESIGN could pick hash-bind instead of re-read; either must still "
            "sit on every activation path. Selection-time caching is the same "
            "gap and is not an acceptable choke."
        ),
        "tests": [
            {
                "id": "T1-both-states-toctou",
                "command": P1,
                "result": "PASS",
                "name": "Activation-time catch vs index-time slip, grants printed",
            },
            {
                "id": "T2-path-enumeration",
                "command": P2,
                "result": "PASS",
                "name": "Every activation entry point file:line crosses authorize_activation",
            },
        ],
        "reviewer": rev["reviewer"],
        "second_reviewer": rev["second_reviewer"],
        "reviewers": rev["reviewers"],
        "report": {
            "kind": "architecture-review",
            "observations": [
                {
                    "name": "index-time-slip",
                    "measured": True,
                    "method": "scratch index/edit/activate with check_epoch=index",
                    "anchor": "command-center/p2-wave/probes/ARC-0027/sequence.py",
                },
                {
                    "name": "activation-time-catch",
                    "measured": True,
                    "method": "scratch index/edit/activate with check_epoch=activation",
                    "anchor": "command-center/p2-wave/probes/ARC-0027/sequence.py",
                },
                {
                    "name": "activation-path-count",
                    "measured": len(activation_paths),
                    "method": "AST walk of gateway.py ACTIVATION_ENTRY_POINTS",
                    "anchor": GATEWAY,
                },
            ],
            "control_ids": ["T1-both-states-toctou", "T2-path-enumeration"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": GATEWAY, "exists": True, "role": "scratch-gateway"},
            {"path": CATALOG, "exists": True, "role": "live-catalog"},
            {"path": A4_FIXTURE, "exists": True, "role": "dossier"},
            {"path": A1_PRECEDENCE, "exists": True, "role": "dossier"},
            {
                "path": "command-center/p2-wave/probes/ARC-0027/probe1_both_states.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0027/probe2_path_enumeration.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "both-states-toctou"},
            {"id": "probe2", "command": P2, "role": "path-enumeration-and-overclaim"},
        ],
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/ARC-0027/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "emitted_at": now,
    }

    SG.validate_doc(doc)
    ok, why = O.check_overclaim(doc, REPO)
    if not ok:
        print(f"FAILED:ARC-0027 overclaim {why}")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:ARC-0027 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
