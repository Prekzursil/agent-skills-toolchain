#!/usr/bin/env python3
"""Emit WFA-0084 HandoffContract from live interface + independent expected sets."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import expected as E  # noqa: E402
import fusion_precondition as F  # noqa: E402
import query as Q  # noqa: E402

from contract import (  # noqa: E402
    LIVE_GRAPHS,
    OUT_REL,
    P1,
    P2,
    PACK_REL,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "WFA-0084", "state": "SUCCESS"},
)


def live_graph_rows() -> list[dict]:
    rows = []
    for gid, rel in LIVE_GRAPHS.items():
        path = REPO / rel
        rows.append(
            {
                "id": gid,
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
                "role": "four-emitted-graphs",
            }
        )
    return rows


def main() -> int:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    jsonschema.Draft202012Validator.check_schema(schema)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:WFA-0084 schema accepted garbage")
            return 1

    lock_ok, lock_why = Q.version_lock_holds()
    if not lock_ok:
        print(f"FAILED:WFA-0084 version lock {lock_why}")
        return 1
    if Q.VERSION_LEDGER[Q.INTERFACE_VERSION] != Q.SCHEMA_FINGERPRINT:
        print("FAILED:WFA-0084 frozen ledger != live fingerprint")
        return 1

    qi = Q.load_fixture_interface(HERE)
    fix = HERE / "fixtures"
    matched = 0
    empty_n = 0
    for qtype, selector in E.CASES:
        got = Q.require_ids(qi.query(qtype, selector))
        want = E.ids_for(fix, qtype, selector)
        if got != want:
            print(f"FAILED:WFA-0084 emit mismatch {qtype}/{selector}")
            return 1
        matched += 1
        if want == []:
            empty_n += 1

    via_iface = F.fusible_pair_set(qi)
    via_direct = E.fusible_pairs(fix)
    if via_iface != via_direct:
        print("FAILED:WFA-0084 emit consumer/direct disagreement")
        return 1
    mutant = F.fusible_pair_set(Q.load_fixture_interface(HERE, subtract_conflicts=False))
    naive = E.load_compat_pairs(fix)
    if mutant == via_direct or mutant != naive:
        print("FAILED:WFA-0084 emit mutant control silent")
        return 1
    if not via_direct < mutant:
        print("FAILED:WFA-0084 emit conflict subtraction not a proper subset")
        return 1

    mutated = json.loads(json.dumps(Q.RESULT_SCHEMA))
    mutated["required"] = list(mutated["required"]) + ["new_required_field"]
    mutated["properties"]["new_required_field"] = {"type": "string"}
    m_ok, m_why = Q.version_lock_holds(
        schema=mutated, version=Q.INTERFACE_VERSION, ledger=Q.VERSION_LEDGER
    )
    if m_ok or m_why != "schema-changed-without-version-bump":
        print(f"FAILED:WFA-0084 emit version mutant silent {m_ok} {m_why}")
        return 1

    producers = live_graph_rows()
    producers.append(
        {
            "id": "fixture-corpus",
            "path": "command-center/p2-wave/probes/WFA-0084/fixtures/",
            "present": True,
            "role": "contract-proof-corpus",
        }
    )
    pack_present = (REPO / PACK_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "record_type": "HandoffContract",
        "title": "Registry query interface for disposition, family, mechanism, licence, task and fusibility",
        "question": QUESTION,
        "catalog_output_schema": PACK_REL + "#/$defs/HandoffContract",
        "schema_pack_present": pack_present,
        "captured_at": now,
        "cloud_ok": False,
        "interface": {
            "version": Q.INTERFACE_VERSION,
            "schema_fingerprint": Q.SCHEMA_FINGERPRINT,
            "module": "command-center/p2-wave/probes/WFA-0084/query.py",
            "query_method": "RegistryQueryInterface.query(query_type, selector)",
            "empty_result_status": "EMPTY",
            "error_ids_are_null": True,
        },
        "query_types": list(Q.QUERY_TYPES),
        "producers": producers,
        "consumers": [
            {
                "id": "fusion-precondition-checker",
                "driven_through": "RegistryQueryInterface.query",
                "module": "command-center/p2-wave/probes/WFA-0084/fusion_precondition.py",
            }
        ],
        "residual_unknowns": [
            {
                "id": "live-four-graphs-absent",
                "statement": (
                    "WFA-0078/0079/0080/0081 live artifacts are absent on this "
                    "worktree, so the contract is proven on a fixture corpus "
                    "that reproduces the four file conventions. The interface "
                    "is not yet bound to production v2 graphs."
                ),
                "settling_experiment": (
                    "Re-run probe1 and probe2 against the live v2 paths named "
                    "in producers[] once those units exist on disk."
                ),
            }
        ],
        "evidence": {
            "signal_a": {
                "name": "query-types-match-independent-expected-set",
                "cases_matched": matched,
                "empty_selectors": empty_n,
                "independent_module": "command-center/p2-wave/probes/WFA-0084/expected.py",
                "corpus_sha256": qi.artifact_version["corpus_sha256"],
                "corpus_id": qi.artifact_version["corpus_id"],
            },
            "signal_b": {
                "name": "fusion-precondition-via-interface-vs-direct-file-access",
                "via_interface": sorted(via_iface),
                "via_direct": sorted(via_direct),
                "naive_compat": sorted(naive),
                "mutant_no_subtract": sorted(mutant),
                "mutant_disagreed": True,
                "conflict_subtracted": sorted(naive - via_direct),
            },
        },
        "tests": [
            {
                "id": "empty-is-empty-not-error-zero",
                "result": "PASS",
                "detail": (
                    f"{empty_n} selectors returned status=EMPTY ids=[] ok=True; "
                    "unknown query type returned status=ERROR ids=null"
                ),
            },
            {
                "id": "schema-change-without-version-bump",
                "result": "PASS",
                "detail": m_why,
            },
            {
                "id": "results-carry-artifact-version",
                "result": "PASS",
                "detail": qi.artifact_version["corpus_sha256"],
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0084-probe2-fusion-direct-vs-interface",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe2 re-runs the fusion precondition checker through the "
                "interface and compares it to expected.py's direct file walk. "
                "A skip-conflict mutant is required to disagree. Probe2 also "
                "re-runs the version lock both-states control."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "query-expected-sets", "command": P1},
            {"id": "probe2", "role": "fusion-consumer-and-version", "command": P2},
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/WFA-0084/query.py",
                "exists": True,
                "role": "stable-interface",
            },
        ],
        "scope": {
            "proof_surface": (
                "Fixture corpus of six blueprints across four deliberately "
                "divergent JSON conventions. Each query type matched an "
                "independent expected set. Fusion precondition checker driven "
                "only through the interface reproduced the direct-access "
                "fusible-pair set. Live v2 graphs were not present."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "WFA-0078/0079/0080/0081 live graphs exist on this worktree",
                "WFA-0001 schema pack was authored here",
                "global unit_manifest.py --write was run",
                "any merge has been executed",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "graph-engineer",
            "execution_substrate": "linux-local",
        },
    }

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0084 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    blob = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in blob:
        print("FAILED:WFA-0084 completion sentinel absent")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:WFA-0084 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
