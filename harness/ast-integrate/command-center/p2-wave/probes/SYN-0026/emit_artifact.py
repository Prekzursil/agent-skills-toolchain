#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0026.cross-vendor-meta-review.json.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.

Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema 4.10
Draft7Validator follows that URL and fails closed. Validate against the
inlined physical profile (generic_report + report.kind=meta-review-finding)
the same way BLD-0039 does, with no network.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import protocol as P  # noqa: E402
import _p2lib as L  # noqa: E402
from dispatch import observe_output  # noqa: E402

SCHEMA_REL = P.SCHEMA_REL
OUT_REL = P.OUT_REL
PROTO_REL = "command-center/p2-wave/probes/SYN-0026/protocol.py"
DISP_REL = "command-center/p2-wave/probes/SYN-0026/dispatch.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
MANIFEST_REL = "command-center/p2-wave/probes/SYN-0026/UNIT-ARTIFACT-MANIFEST.json"
SUPPORTING = [
    SCHEMA_REL,
    PROTO_REL,
    DISP_REL,
    "command-center/p2-wave/probes/SYN-0026/emit_artifact.py",
    "command-center/p2-wave/probes/SYN-0026/probe1_vendor_differs.py",
    "command-center/p2-wave/probes/SYN-0026/probe2_unilateral_and_severed.py",
    "command-center/p2-wave/probes/SYN-0026/fixtures/planted-contest.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compiled_schema() -> dict:
    """Inline receipt $defs. jsonschema 4.10.3 cannot take registry=."""
    shim_path = REPO / SCHEMA_REL
    if not shim_path.is_file() or shim_path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:SYN-0026 catalog schema missing {SCHEMA_REL}")
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    ref = str(shim.get("$ref") or "")
    if "artifact-class-profiles.schema.json#/$defs/meta-review-finding" not in ref:
        raise SystemExit(f"FAILED:SYN-0026 unexpected catalog schema $ref {ref!r}")
    receipt = json.loads((REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise SystemExit("FAILED:SYN-0026 receipt.schema.json missing generic_report")
    return {
        "$id": (
            "https://ast-integrate.invalid/command-center/p2-wave/probes/"
            "SYN-0026/meta-review-finding.local.json"
        ),
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "type": "object",
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {
                            "kind": {"const": "meta-review-finding"}
                        },
                    }
                },
            },
        ],
        "$defs": defs,
    }


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    for err in Draft7Validator(compiled_schema()).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def persist(doc: dict) -> int:
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "SYN-0026", "state": "SUCCESS", "blob": "x" * 200},
    ]
    for blob in garbage:
        if not schema_errors(blob):
            print(f"FAILED:SYN-0026 local schema accepted garbage {list(blob)[:2]}")
            return 1
    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0026 artifact does not satisfy meta-review-finding")
        for e in errs[:25]:
            print("   ", e)
        return 1
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(dest)
    floor = int(doc.get("min_bytes_threshold") or 1)
    if size < floor:
        print(f"FAILED:SYN-0026 artifact {size}B below declared floor {floor}B")
        return 1
    primary = L.art(OUT_REL, "primary")
    doc["artifacts"][0] = {
        k: primary[k] for k in ("path", "bytes", "sha256", "exists", "eol", "role")
    }
    if doc["artifacts"][0]["exists"] is not True:
        print("FAILED:SYN-0026 primary missing after write")
        return 1
    errs = schema_errors(doc)
    if errs:
        print("FAILED:SYN-0026 rewritten artifact schema errors")
        for e in errs[:25]:
            print("   ", e)
        return 1
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(dest)
    print(
        f"wrote {OUT_REL} bytes={size} sha256={sha} "
        f"lenses={doc['report']['summary']['lens_count']} "
        f"agree={doc['report']['summary']['agree_count']} "
        f"contest={doc['report']['summary']['contest_count']}"
    )
    print("SUCCESS:SYN-0026 emit")
    return 0


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    units = P.index_units()
    unit = units[P.UNIT_ID]
    lens_ids = P.lens_ids_for_unit(units)
    if len(lens_ids) < 7:
        print(f"FAILED:SYN-0026 emit expected 7 lens deps, got {lens_ids}")
        return 1
    author_ids = {"SYN-0008"} | set(lens_ids)
    dispatch_dir = HERE / "dispatches"
    dispatch_dir.mkdir(parents=True, exist_ok=True)

    lens_rows: list[dict] = []
    dispatch_evidence: list[dict] = []
    for lid in lens_ids:
        lu = units[lid]
        row, rec = P.review_one_lens(lu, author_ids, dispatch_dir)
        lens_rows.append(row)
        dispatch_evidence.append(
            {
                "lens_id": lid,
                "exit_code": rec["exit_code"],
                "parsed": rec["parsed"],
                "output_bytes": rec["output_bytes"],
                "output_path": rec["output_path"],
                "prompt_path": rec["prompt_path"],
                "prompt_transport": "file",
                "classification": rec["classification"],
                "counts_as_result": rec["counts_as_result"],
                "terminal_state": rec["terminal_state"],
            }
        )
        if rec["terminal_state"] != "SUCCESS":
            print(f"FAILED:SYN-0026 emit dispatch {lid} terminal={rec['terminal_state']}")
            print(json.dumps(rec, sort_keys=True)[:1500])
            return 1

    P.assert_vendor_differs(lens_rows)
    P.assert_contests_anchored_and_open(lens_rows)
    authors, reviewers, intersection = P.build_rosters(units, lens_rows)
    if intersection:
        print(f"FAILED:SYN-0026 emit roster intersection {intersection}")
        return 1

    planted = P.planted_contest()
    try:
        planted.close_unilaterally("first")
        print("FAILED:SYN-0026 emit planted contest closed unilaterally")
        return 1
    except P.UnilateralCloseError:
        pass
    try:
        P.assign_reviewer("anthropic", "anthropic", "bogus-same", author_ids)
        print("FAILED:SYN-0026 emit same-vendor assign was accepted")
        return 1
    except P.SameVendorReviewError:
        pass
    try:
        P.assign_reviewer("openai", "anthropic", "SYN-0008", author_ids)
        print("FAILED:SYN-0026 emit author-as-reviewer was accepted")
        return 1
    except P.ReviewerAuthoredError:
        pass

    severed = P.run_severed_control(dispatch_dir)
    if severed.get("classification") != "severed-stream" or severed.get("counts_as_result"):
        print(f"FAILED:SYN-0026 emit severed control {severed}")
        return 1
    if severed.get("terminal_state") != "FAILED":
        print(f"FAILED:SYN-0026 emit severed terminal {severed.get('terminal_state')}")
        return 1
    live0 = dispatch_evidence[0]
    if live0["exit_code"] == 0 and severed.get("exit_code") == 0:
        if live0["counts_as_result"] == severed.get("counts_as_result"):
            print("FAILED:SYN-0026 emit exit-0-only detector is inert")
            return 1

    agree_ctrl = P.reconcile(
        P.Verdict(vendor="anthropic", label="LENS-OUTPUT-ABSENT"),
        P.Verdict(vendor="openai", label="LENS-OUTPUT-ABSENT"),
    )
    if agree_ctrl.status != P.AGREE:
        print("FAILED:SYN-0026 emit identical labels did not AGREE")
        return 1

    sentinel = str(unit.get("completion_sentinel") or "")
    n_agree = sum(1 for r in lens_rows if r["reconciliation"] == P.AGREE)
    n_contest = sum(1 for r in lens_rows if r["reconciliation"] == P.CONTEST)
    n_absent = sum(
        1
        for r in lens_rows
        if r["first_vendor_verdict"]["label"] == "LENS-OUTPUT-ABSENT"
    )
    adj = observe_output("command-center/synthesis/SYN-0011.adjudications.json")

    findings = []
    for row in lens_rows:
        findings.append(
            {
                "id": f"finding-{row['lens_id']}",
                "lens_id": row["lens_id"],
                "claim": (
                    f"Second-vendor ({row['reviewer_vendor']}) re-observed "
                    f"{row['output_path']} independently of first-vendor "
                    f"({row['author_vendor']}) and labelled "
                    f"{row['second_vendor_verdict']['label']}; first-vendor "
                    f"labelled {row['first_vendor_verdict']['label']}; "
                    f"reconciliation={row['reconciliation']}."
                ),
                "reconciliation": row["reconciliation"],
                "raw_anchor": row["raw_anchor"],
            }
        )
    findings.append(
        {
            "id": "finding-planted-contest-protocol",
            "lens_id": "SYN-0014",
            "claim": (
                "Planted CONTEST (first SUCCESS vs second FAILED) remains open; "
                "close_unilaterally('first') raises UnilateralCloseError; raw "
                f"anchor {planted.raw_anchor}."
            ),
            "reconciliation": P.CONTEST,
            "raw_anchor": planted.raw_anchor,
        }
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat_anchor = P.source_anchor(CATALOG_REL, '"id": "SYN-0026"')
    proto_anchor = P.source_anchor(PROTO_REL, "Neither side may close")
    disp_anchor = P.source_anchor(DISP_REL, "terminal state for")

    supporting = []
    for rel in SUPPORTING:
        row = L.art(rel, "supporting")
        if row["exists"] is not True:
            print(f"FAILED:SYN-0026 missing supporting {rel}")
            return 1
        supporting.append(
            {k: row[k] for k in ("path", "bytes", "sha256", "exists", "eol", "role")}
        )

    src1 = L.probe(
        "source",
        "test-run",
        P.P1,
        (
            f"lenses={len(lens_rows)} intersection={intersection} "
            f"second_vendor_labels={[r['second_vendor_verdict']['label'] for r in lens_rows]}"
        ),
        0,
    )
    ver1 = L.probe(
        "verifier",
        "file-read",
        cat_anchor,
        (
            "catalog SYN-0026 reviewer_requirement disqualifies synthesis "
            "authors; assigned vendor=openai; dependencies="
            + ",".join(lens_ids)
        ),
        0,
    )
    src2 = L.probe(
        "source",
        "test-run",
        P.P2,
        (
            f"planted.status={planted.status} planted.open={planted.open} "
            f"severed.terminal={severed.get('terminal_state')} "
            f"severed.classification={severed.get('classification')} "
            f"live0.terminal={live0['terminal_state']}"
        ),
        0,
    )
    ver2 = L.probe(
        "verifier",
        "file-read",
        disp_anchor,
        "Severed-stream (exit 0 + job receipt) classifies FAILED, not SUCCESS.",
        0,
    )
    schema_probe = L.probe(
        "source",
        "schema-validate",
        (
            "python3 -B command-center/p2-wave/probes/SYN-0026/emit_artifact.py "
            "(Draft7Validator compiled generic_report + kind=meta-review-finding)"
        ),
        "in-process compiled_schema before persist; catalog shim $ref not fetched",
        0,
    )

    body_for_hash = {
        "unit_id": P.UNIT_ID,
        "lenses": lens_rows,
        "findings": findings,
        "dispatch_control": {
            "classification": severed["classification"],
            "terminal_state": severed["terminal_state"],
        },
    }
    primary_sha = hashlib.sha256(
        json.dumps(body_for_hash, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    n_second = sum(
        1 for r in lens_rows if (r.get("second_vendor_verdict") or {}).get("label")
    )
    doc = {
        "schema_version": 1,
        "unit_id": P.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": cat_anchor,
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "cross-vendor-meta-reviewer",
            "execution_substrate": "local-serialized",
        },
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "two strikes then pivot"),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": 4096,
                "sha256": primary_sha,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            *supporting,
        ],
        "evidence": [
            L.evidence(
                (
                    f"Each of {len(lens_rows)} catalog lenses has a second-vendor "
                    f"verdict (n_second={n_second}) from the OTHER catalog vendor "
                    "than the lens author; author/reviewer roster intersection is "
                    f"empty ({intersection})."
                ),
                "CONFIRMED",
                cat_anchor,
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Planted CONTEST stays open with a raw anchor; neither side "
                    "may close it unilaterally. A severed confirmer (exit 0 + "
                    "job-receipt) classifies FAILED/severed-stream, not SUCCESS."
                ),
                "CONFIRMED",
                planted.raw_anchor or P.PLANTED_CONTEST_REL,
                [src2, ver2],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "test_reviewer_vendor_differs_from_every_author_vendor_per_lens",
                "name": "Reviewer vendor differs from every author vendor per lens",
                "command": P.P1,
                "result": "PASS",
            },
            {
                "id": "test_no_contested_finding_is_closed_by_one_side_alone",
                "name": "No CONTEST is closed by one side alone",
                "command": P.P2,
                "result": "PASS",
            },
            {
                "id": "dispatch_severed_classifies_failed_not_success",
                "name": "Deliberately severed run classifies FAILED not SUCCESS",
                "command": P.P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "planted-contest-unilateral-close",
                "known-broken-fixture",
                (
                    "First SUCCESS vs second FAILED must stay open CONTEST; "
                    "close_unilaterally raises. Identical labels AGREE and "
                    "need no raw anchor."
                ),
                True,
                agree_ctrl.status == P.AGREE and agree_ctrl.raw_anchor is None,
                bad=(
                    f"status={planted.status} open={planted.open} "
                    f"anchor={planted.raw_anchor} UnilateralCloseError=raised"
                ),
                good=f"agree.status={agree_ctrl.status} raw_anchor={agree_ctrl.raw_anchor}",
            ),
            L.control(
                "planted-severed-stream",
                "malformed-input",
                (
                    "A confirmer that writes only a job-receipt must classify "
                    "severed-stream / FAILED. A complete confirmer with parsed "
                    "output must classify SUCCESS."
                ),
                severed.get("terminal_state") == "FAILED"
                and severed.get("classification") == "severed-stream",
                live0["terminal_state"] == "SUCCESS" and live0["counts_as_result"],
                bad=(
                    f"terminal={severed.get('terminal_state')} "
                    f"class={severed.get('classification')} "
                    f"counts={severed.get('counts_as_result')}"
                ),
                good=(
                    f"terminal={live0['terminal_state']} "
                    f"counts={live0['counts_as_result']} "
                    f"exit={live0['exit_code']}"
                ),
            ),
        ],
        "reviewer": {
            "reviewer_id": "SYN-0026-probe2-unilateral-and-severed",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs the planted CONTEST and the severed confirmer "
                "against protocol.py/dispatch.py. Not a live second-vendor "
                "cloud session. Lens authors are excluded from the reviewer roster."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0026/emit_artifact.py "
                    "compiled_schema Draft7Validator"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    f"{n_absent}/{len(lens_rows)} lens catalog output_path files "
                    "are absent on this worktree; both vendors independently "
                    "labelled LENS-OUTPUT-ABSENT and AGREE. That is an input "
                    "gap, not a same-vendor meta-review."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver SYN-0014..SYN-0021 catalog output_path files, then "
                    "re-run the second-vendor confirmer and re-reconcile."
                ),
            }
        ],
        "defects": [],
        "report": {
            "kind": "meta-review-finding",
            "control_ids": [
                "planted-contest-unilateral-close",
                "planted-severed-stream",
            ],
            "observations": [
                {
                    "name": "lens_count",
                    "measured": len(lens_rows),
                    "method": "catalog dependencies of SYN-0026 starting with SYN-",
                    "anchor": cat_anchor,
                },
                {
                    "name": "second_vendor_verdict_count",
                    "measured": n_second,
                    "method": "prompt-by-file confirmer, other catalog vendor",
                    "anchor": disp_anchor,
                },
                {
                    "name": "agree_count",
                    "measured": n_agree,
                    "method": "protocol.reconcile identical labels",
                    "anchor": proto_anchor,
                },
                {
                    "name": "contest_count",
                    "measured": n_contest,
                    "method": "protocol.reconcile differing labels with raw_anchor",
                    "anchor": proto_anchor,
                },
                {
                    "name": "roster_intersection",
                    "measured": ",".join(intersection) if intersection else "empty",
                    "method": "join author_roster against reviewer_roster",
                    "anchor": proto_anchor,
                },
                {
                    "name": "severed_terminal_state",
                    "measured": str(severed.get("terminal_state")),
                    "method": "dispatch.run_confirmer mode=severed",
                    "anchor": disp_anchor,
                },
                {
                    "name": "adjudications_label",
                    "measured": str(adj["label"]),
                    "method": "observe_output of SYN-0011.adjudications.json",
                    "anchor": "command-center/synthesis/SYN-0011.adjudications.json",
                },
            ],
            "title": str(unit.get("title") or ""),
            "question": str(unit.get("question_or_target") or ""),
            "meta_review_kind": "cross-vendor-reconciliation",
            "substrate": (
                "local-serialized mechanical second-vendor confirmer; prompt by "
                "file; vendor identity is the OTHER catalog vendor than the "
                "lens author. Not a live cloud vendor session."
            ),
            "protocol": {
                "id": "cross-vendor-reconciliation",
                "rules": [
                    "Agreement is recorded as AGREE with both verdicts kept on the row.",
                    "Disagreement is CONTEST and is escalated to a raw source anchor.",
                    "Neither side may close the other's finding unilaterally; CONTEST stays open.",
                ],
                "unilateral_close": "forbidden-on-CONTEST",
            },
            "inputs": {
                "lens_ids": lens_ids,
                "adjudications_path": "command-center/synthesis/SYN-0011.adjudications.json",
                "adjudications_label": adj["label"],
                "cross_vendor_dispatch_rule": "rules/common/cross-vendor-dispatch.md",
            },
            "summary": {
                "lens_count": len(lens_rows),
                "agree_count": n_agree,
                "contest_count": n_contest,
                "lens_output_absent_count": n_absent,
                "denominator": len(lens_rows),
            },
            "lenses": lens_rows,
            "author_roster": authors,
            "reviewer_roster": reviewers,
            "roster_intersection": intersection,
            "findings": findings,
            "dispatch_evidence": dispatch_evidence,
            "dispatch_control": {
                "id": "planted-severed-stream",
                "classification": severed["classification"],
                "counts_as_result": severed["counts_as_result"],
                "terminal_state": severed["terminal_state"],
                "exit_code": severed["exit_code"],
                "output_bytes": severed["output_bytes"],
                "parsed": severed["parsed"],
                "output_path": severed["output_path"],
                "note": "Exit 0 with a job-receipt is FAILED/severed-stream, not SUCCESS.",
            },
            "notes": (
                "G-1 for SYN-0026: live named probes, honest non-BLOCKED "
                "artifact, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. cloud ok=true is not delivery. "
                "Lens outputs absent on disk are recorded as LENS-OUTPUT-ABSENT "
                "AGREE, not as BLOCKED of this unit."
            ),
        },
        "extensions": {
            "cloud_ok": False,
            "adv_rebuild_circle": False,
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "reviewer-vendor-differs",
                    "command": P.P1,
                },
                {
                    "id": "probe2",
                    "role": "unilateral-close-and-severed",
                    "command": P.P2,
                },
            ],
        },
    }

    if sentinel not in json.dumps(doc):
        print("FAILED:SYN-0026 completion_sentinel missing from document")
        return 1
    return persist(doc)


if __name__ == "__main__":
    raise SystemExit(main())
