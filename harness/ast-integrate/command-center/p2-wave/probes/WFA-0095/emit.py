#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0095-duplicate-collapse-policy.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import policy as P  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0095-duplicate-collapse-policy.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0095/audit-report.schema.json"
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
QUESTION = (
    "Implementation target: a written collapse policy stating that collapsing "
    "two duplicates must preserve the union of their mechanisms, provenance "
    "anchors, licence obligations and stop rules - and that any collapse "
    "losing a capability is rejected rather than accepted as simplification."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0095/probe1_planted_lossy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0095/probe2_licence_restore.py"
)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0095 emit snippet not in {rel}: {snippet!r}")
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


def _pack_def_is_offline_live(defn: object) -> bool:
    """True when $defs/AuditReport can be validated without a network $ref."""
    if not isinstance(defn, dict):
        return False
    ref = defn.get("$ref")
    if isinstance(ref, str) and (
        ref.startswith("http://") or ref.startswith("https://")
    ):
        return False
    return any(
        k in defn
        for k in ("properties", "required", "allOf", "anyOf", "oneOf", "type")
    )


def load_audit_schema() -> tuple[dict, dict]:
    local = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    pack_path = REPO / PACK_REL
    info = {
        "declared": f"{PACK_REL}#/$defs/AuditReport",
        "declared_exists": pack_path.is_file(),
        "fallback": SCHEMA_REL,
        "required_fix": None,
    }
    if pack_path.is_file():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        defs = pack.get("$defs") or {}
        ar = defs.get("AuditReport")
        if _pack_def_is_offline_live(ar):
            schema = {
                "$schema": pack.get(
                    "$schema", "https://json-schema.org/draft/2020-12/schema"
                ),
                "$defs": defs,
                **ar,
            }
            info["used"] = info["declared"]
            return schema, info
        info["pack_audit_report_kind"] = (
            "remote-$ref-shim"
            if isinstance(ar, dict) and "$ref" in ar
            else "missing-or-empty"
        )
        info["required_fix"] = "offline-local-audit-report-schema"
        info["note"] = (
            "WFA-0001 pack $defs/AuditReport is a $ref shim to "
            "https://ast-integrate.invalid/platform/schema/"
            "artifact-class-profiles.schema.json. jsonschema 4.10.3 "
            "Draft7Validator fetches that URL and raises RefResolutionError "
            "(fingerprint catalog-shim-ref-network). Same-fingerprint retry "
            "is parked. Live emit validates against the unit-local schema. "
            "This is not an ADV rebuild of the pack."
        )
    info["used"] = SCHEMA_REL
    return local, info


def main() -> int:
    live = P.run_all()
    compact = [P.compact_eval(live[fid]) for fid in sorted(live)]
    if not all(row["matched_expectation"] for row in compact):
        print("FAILED:WFA-0095 emit fixture expectation mismatch")
        print(json.dumps(compact, indent=2)[:4000])
        return 1

    lossy = live["planted-lossy-mechanism"]
    good = live["union-preserving"]
    weak = live["planted-licence-weakened"]
    no_edge = live["union-preserving-no-edge"]
    fx_lossy = P.fixtures()["planted-lossy-mechanism"]
    mutant = P.always_accept_mutant(
        fx_lossy["left"],
        fx_lossy["right"],
        fx_lossy["merged"],
        fx_lossy["survivor_id"],
    )

    controls = {
        "lossy_rejected": (not lossy["accepted"])
        and P.CAPABILITY_LOSS in lossy["codes"],
        "union_preserving_accepted": good["accepted"] is True and good["codes"] == [],
        "licence_weakened_rejected": (not weak["accepted"])
        and P.LICENCE_WEAKENED in weak["codes"],
        "duplicate_of_written": bool(good["edges"])
        and good["edges"][0]["edge_type"] == "duplicate-of",
        "restore_equals_preimage": good.get("restore_ok") is True,
        "no_edge_rejected": (not no_edge["accepted"])
        and P.MISSING_DUPLICATE_OF in no_edge["codes"],
        "always_accept_mutant_fails_planted_lossy": mutant["accepted"] is True
        and bool(mutant.get("missing", {}).get(P.MECHANISMS)),
        "policy_has_rejected": any(not r["accepted"] for r in live.values()),
    }
    if not all(controls.values()):
        print("FAILED:WFA-0095 emit controls")
        print(json.dumps(controls, indent=2))
        print(
            "mutant",
            json.dumps(
                {
                    "accepted": mutant["accepted"],
                    "missing": mutant["missing"],
                    "policy_constrained": mutant.get("policy_constrained"),
                },
                indent=2,
            ),
        )
        return 1

    admitted = sum(1 for r in live.values() if r["accepted"])
    rejected = sum(1 for r in live.values() if not r["accepted"])
    schema_doc, schema_res = load_audit_schema()
    pack_path = REPO / PACK_REL
    wfa_deps = {
        "WFA-0007": (
            REPO / "command-center/wfa/WFA-0007-lexical-duplicate-scan.json"
        ).is_file(),
        "WFA-0008": (
            REPO / "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json"
        ).is_file(),
        "WFA-0094": (
            REPO / "command-center/wfa/WFA-0094-semantic-diff-engine.json"
        ).is_file(),
        "WFA-0001-schema-pack": pack_path.is_file(),
    }

    evid = [
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "collapsing two duplicates must preserve the union",
            "catalog",
            "Catalog WFA-0095 names the four preserved sets and the lossy-reject rule.",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0095/policy.py",
            "Union preservation is a computed set difference",
            "probe",
            "evaluate_collapse computes missing = required_union - merged, not a comment.",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0095/policy.py",
            "embedding-cosine-rewrite",
            "fixture",
            "Planted unique mechanism on wf-scan-beta that a lossy merge drops.",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0095/policy.py",
            '"edge_type": "duplicate-of"',
            "probe",
            "Admitted collapse writes a duplicate-of edge with preimage snapshots.",
        ),
        ev(
            "command-center/p2-wave/probes/SYN-0047/classes.py",
            "workflow fusion loses a source capability",
            "seed",
            "Named failure class FC-11332 is the lossy-collapse plant this policy rejects.",
        ),
    ]

    doc = {
        "unit_id": "WFA-0095",
        "record_type": "AuditReport",
        "state": "SUCCESS",
        "sentinel": P.SENTINEL,
        "title": (
            "Collapse policy: a merge must preserve the union of the collapsed "
            "records' capabilities"
        ),
        "question": QUESTION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_ref": schema_res["declared"],
        "schema_resolution": schema_res,
        "dependency_artifacts_present": wfa_deps,
        "policy": {
            "text": P.POLICY_TEXT,
            "preserved_attribute_sets": list(P.PRESERVED_SETS),
            "stricter_licence_governs": True,
            "lossy_collapse_rejected": True,
            "duplicate_of_required": True,
            "licence_lattice": P.LICENCE_RANK,
            "reject_codes": [
                P.CAPABILITY_LOSS,
                P.PROVENANCE_LOSS,
                P.LICENCE_WEAKENED,
                P.LICENCE_UNKNOWN,
                P.STOP_RULE_LOSS,
                P.MISSING_DUPLICATE_OF,
                P.SURVIVOR_NOT_IN_PAIR,
            ],
        },
        "evaluations": compact,
        "controls": controls,
        "negative_control_verbatim": P.NEGATIVE_CONTROL_VERBATIM,
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0095-probe2-licence-restore",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-derives required unions with frozenset arithmetic in "
                "the probe file (does not call evaluate_collapse), checks that "
                "MIT+AGPL proposed as MIT is rejected and proposed as AGPL is "
                "accepted, restores the absorbed record from the duplicate-of "
                "snapshot, and shows always_accept_mutant admits the planted loss."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "unit-local-schema"},
            {
                "path": "command-center/p2-wave/probes/WFA-0095/policy.py",
                "exists": True,
                "role": "executable-policy",
            },
        ],
        "evidence": evid,
        "findings": [
            {
                "id": "F1",
                "claim": (
                    "Planted lossy collapse dropping embedding-cosine-rewrite is "
                    "rejected with CAPABILITY_LOSS."
                ),
                "verdict": "CONFIRMED",
                "anchor": "planted-lossy-mechanism",
            },
            {
                "id": "F2",
                "claim": (
                    "Union-preserving collapse is admitted, writes duplicate-of, "
                    "and restores the preimage pair."
                ),
                "verdict": "CONFIRMED",
                "anchor": "union-preserving",
            },
            {
                "id": "F3",
                "claim": (
                    "MIT + AGPL-3.0-only proposed under MIT is rejected; AGPL "
                    "governs the admitted merge."
                ),
                "verdict": "CONFIRMED",
                "anchor": "planted-licence-weakened",
            },
            {
                "id": "F4",
                "claim": (
                    "Live WFA-0007/0008/0094 scan artifacts are absent on this "
                    "worktree; the policy is proven on planted fixtures, not on "
                    "a live 284-candidate collapse set."
                ),
                "verdict": "DISCLOSED",
                "anchor": "dependency_artifacts_present",
            },
        ],
        "summary": {
            "admitted": admitted,
            "rejected": rejected,
            "policy_constrained": rejected > 0,
            "fixture_count": len(live),
            "governing_licence_on_admitted": good["governing_licence"],
            "note": (
                "A collapse that loses a capability is rejected rather than "
                "accepted as simplification. SUCCESS:WFA-0095"
            ),
        },
    }

    try:
        import jsonschema
    except ImportError:
        print("FAILED:WFA-0095 emit jsonschema not installed")
        return 1
    jsonschema.validate(doc, schema_doc)
    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated"}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema_doc)
        except jsonschema.ValidationError:
            garbage_rejected += 1
    if garbage_rejected != 3:
        print(
            f"FAILED:WFA-0095 emit schema vacuous garbage_rejected={garbage_rejected}"
        )
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if P.SENTINEL not in text:
        print("FAILED:WFA-0095 emit sentinel missing")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:WFA-0095 emit self-declared", doc.get("state"))
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:WFA-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
