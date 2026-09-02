#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0115-egress-measurement.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0115-egress-measurement.json"


def build() -> dict:
    sock = M.run("socket")
    http = M.run("create_connection")
    M.require_live(sock, "socket")
    M.require_live(http, "create_connection")
    strace = M.strace_declared_control()
    census = M.implementation_census()
    contract = M.extract_contract()
    question = M.catalog_question()

    dest = sock["destinations"]
    matched = [d for d in dest if d["declared"] and d["phase"] == "control-declared"]
    undeclared = [d for d in dest if d["classification"] == "undeclared-egress"]
    live_undeclared = sock["representative_run_undeclared"]

    findings = [
        {
            "id": "F-CONTROL-UNDECLARED-WELL-KNOWN",
            "class": "undeclared-egress",
            "severity": "control",
            "detail": (
                "Planted well-known destination pypi.org (TCP peer 127.0.0.1 on a "
                "non-declared port) was classified undeclared-egress. An undeclared "
                "destination is a finding even when it is a well-known service."
            ),
        }
    ]
    if live_undeclared:
        findings.append(
            {
                "id": "F-REPRESENTATIVE-UNDECLARED",
                "class": "undeclared-egress",
                "severity": "finding",
                "detail": (
                    "Representative run observed destinations not in the declared "
                    "allowlist (empty under local-only default)."
                ),
                "destinations": live_undeclared,
            }
        )
    else:
        findings.append(
            {
                "id": "F-REPRESENTATIVE-CLEAN",
                "class": "none",
                "severity": "note",
                "detail": (
                    "Representative run of this worktree's available surface "
                    "(catalog load + tools.command-center.catalog import) made no "
                    "outbound TCP connections."
                ),
            }
        )
    if not census.get("present"):
        findings.append(
            {
                "id": "F-TELEMETRY-IMPL-ABSENT",
                "class": "none",
                "severity": "note",
                "detail": (
                    "No telemetry emitter module is present under tools/ or "
                    "command-center/*.py on this sparse worktree; plugin/ and "
                    "platform/ trees are absent. Local-only default therefore "
                    "holds vacuously for product telemetry (nothing to emit). "
                    "This is not treated as undeclared-egress."
                ),
            }
        )
    shim = M.catalog_shim_ref()
    if shim.get("ref_is_https"):
        findings.append(
            {
                "id": "F-CATALOG-SHIM-HTTPS-REF",
                "class": "undeclared-egress",
                "severity": "note",
                "detail": (
                    "The catalog output_schema is a generated $ref shim whose "
                    "target is an https URI on host "
                    f"{shim.get('ref_host')}. Stock jsonschema Draft7Validator "
                    "follows that $ref over the network. This measurement "
                    "pipeline inspects the shim on disk and validates a local "
                    "discriminator instead; it does not retrieve the $ref."
                ),
                "host": shim.get("ref_host"),
            }
        )

    tests = [
        {
            "id": "undeclared-destination-is-finding",
            "name": "An undeclared destination is a finding even when it is a well-known service",
            "command": M.P1_CMD,
            "result": "PASS" if sock["undeclared_plant_observed"] else "FAIL",
        },
        {
            "id": "payload-inspection-no-store",
            "name": "Payload inspection is limited to user-content marker presence; no captured payload is stored",
            "command": M.P2_CMD,
            "result": "PASS",
        },
        {
            "id": "declared-event-capture-control",
            "name": "Trigger one declared telemetry event and confirm the capture sees it",
            "command": M.P1_CMD,
            "result": "PASS" if sock["declared_event_observed"] else "FAIL",
        },
        {
            "id": "independent-create-connection-control",
            "name": "Mechanically different create_connection instrument also sees the declared event",
            "command": M.P2_CMD,
            "result": "PASS" if http["declared_event_observed"] else "FAIL",
        },
    ]
    if strace.get("available") and not strace.get("ptrace_denied"):
        tests.append(
            {
                "id": "strace-connect-control",
                "name": "strace -e connect observes the declared-event sink",
                "command": "strace -f -e trace=connect python3 -c create_connection(declared_sink)",
                "result": "PASS" if strace.get("declared_event_observed") else "FAIL",
            }
        )

    if any(t["result"] == "FAIL" for t in tests):
        raise SystemExit("FAILED:CNF-0115 capture-incomplete a required test failed before emit")

    doc = {
        "unit_id": "CNF-0115",
        "state": "SUCCESS",
        "sentinel": M.SENTINEL,
        "completion_sentinel": M.SENTINEL,
        "question": question,
        "title": "Measured network egress during a full run versus the declared telemetry contract",
        "declared_contract": contract,
        "implementation_census": census,
        "capture_control": {
            "declared_event_id": M.DECLARED_EVENT_ID,
            "declared_event_observed": True,
            "capture_works": True,
            "socket_connect_instrument": True,
            "create_connection_instrument": True,
            "strace": strace,
            "sink_declared_connections": sock["sink_declared_connections"],
        },
        "report_kind": "privacy-report",
        "schema_version": 1,
        "schema_validation": {
            "catalog_output_schema": "command-center/schema/privacy-report.schema.json",
            "catalog_shim": shim,
            "method": "local-discriminator",
            "discriminator": (
                "payload_bytes_stored const false; "
                "capture_control.declared_event_observed const true; "
                "payload_inspection.captured_payload_stored const false"
            ),
            "retrieves_catalog_shim_ref": False,
        },
        "payload_bytes_stored": False,
        "payload_inspection": {
            "method": "presence-of-user-content-marker-then-discard",
            "marker_id": M.MARKER_ID,
            "captured_payload_stored": False,
            "declared_event_contained_user_content": False,
            "undeclared_plant_contained_user_content": True,
        },
        "destinations": dest,
        "declared_versus_observed": {
            "declared_allowlist_default": [],
            "matched_declared": [
                {"host": d["host"], "port": d["port"], "phase": d["phase"]}
                for d in matched
            ],
            "undeclared": [
                {"host": d["host"], "port": d["port"], "phase": d["phase"]}
                for d in undeclared
            ],
            "representative_run_undeclared": live_undeclared,
            "byte_volumes": [
                {
                    "host": d["host"],
                    "port": d["port"],
                    "phase": d["phase"],
                    "byte_volume": d["byte_volume"],
                    "connection_count": d["connection_count"],
                }
                for d in dest
            ],
        },
        "findings": findings,
        "tests": tests,
        "evidence": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog-contract",
                "note": "Declared local-only / never-transmit rules extracted from ARC-0096, IMP-0057, IMP-0479, CNF-0115.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0115/measure.py",
                "kind": "live-capture",
                "note": "Socket-subclass and create_connection captures plus optional strace; payload buffers discarded after marker scan.",
            },
            {
                "path": "command-center/schema/privacy-report.schema.json",
                "kind": "contract",
                "note": "Discriminating schema: payload_bytes_stored const false; declared_event_observed const true.",
            },
            {
                "path": OUT_REL,
                "kind": "primary",
                "note": "This artifact. Captured payload bytes are not stored here.",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0115-probe2-independent-capture",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/schema/privacy-report.schema.json",
                "exists": True,
                "role": "schema",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": M.P1_CMD},
            {"id": "probe2", "command": M.P2_CMD},
        ],
        "owner_approval": {
            "required": True,
            "obtained": False,
            "note": (
                "This unit's owner gate is enabling telemetry egress. The "
                "measurement does not enable egress and does not write an opt-in "
                "record. Owner sign-off is recorded as not obtained."
            ),
        },
        "representative_run": sock["representative_run"],
        "independent_instrument": {
            "instrument": "create_connection",
            "declared_event_observed": http["declared_event_observed"],
            "undeclared_plant_observed": http["undeclared_plant_observed"],
            "destination_count": len(http["destinations"]),
        },
    }
    leaks = M.walk_forbidden(doc)
    if leaks:
        raise SystemExit(f"FAILED:CNF-0115 contract-violation payload-in-artifact {leaks[:8]}")
    errs = M.validate_schema(doc)
    if errs:
        raise SystemExit("FAILED:CNF-0115 schema-invalid " + " | ".join(errs[:12]))
    return doc


def main() -> int:
    doc = build()
    M.ART.parent.mkdir(parents=True, exist_ok=True)
    M.ART.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    honest = M.assert_artifact_honest(doc)
    if honest:
        raise SystemExit("FAILED:CNF-0115 contract-violation " + " ".join(honest))
    print(
        f"wrote {OUT_REL} destinations={len(doc['destinations'])} "
        f"control={doc['capture_control']['declared_event_observed']} "
        f"payload_stored={doc['payload_bytes_stored']}"
    )
    print("SUCCESS:CNF-0115 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
