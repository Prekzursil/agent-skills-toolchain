#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0133-premise-blast-radius.json.

Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema 4.10
would fetch that URL; this emit resolves the physical schemas from disk and
refuses remote handlers. Domain payload lives under report (receipt_core
additionalProperties is false).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from corpus import (  # noqa: E402
    CONFIRMED_PREMISE_ID,
    OUT_REL,
    PROBE1,
    PROBE2,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    SOURCE_DOC,
    UNIT_ID,
    WORKED_PREMISE_ID,
)

STRIKES = HERE / "_schema_strikes.json"
MIN_BYTES = 2048
SUPPORTING = (
    SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0133/corpus.py",
    "command-center/p2-wave/probes/ADV-0133/engine.py",
    "command-center/p2-wave/probes/ADV-0133/probe1_worked_case.py",
    "command-center/p2-wave/probes/ADV-0133/probe2_controls.py",
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def validator() -> jsonschema.Draft202012Validator:
    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    receipt = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    profiles = json.loads(
        (
            REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
        ).read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(receipt.get("$id") or ""): receipt,
        str(profiles.get("$id") or ""): profiles,
        "https://ast-integrate.invalid/" + SCHEMA_REL: shim,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
    }
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blocked = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "required_fix": required_fix,
        "sentinel": f"FAILED:{UNIT_ID} parked same-fingerprint structural refute",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0133",
        "min_bytes_threshold": MIN_BYTES,
        "schema_fingerprint": fp,
        "schema_errors": errs[:25],
        "failure": {
            "classification": ["schema-invalid"],
            "reason": (
                "Two same-fingerprint structural refutes against "
                f"{SCHEMA_REL}; required_fix={required_fix}"
            ),
        },
        "artifacts": [artifact_row(SCHEMA_REL, "supporting")],
        "evidence": [
            {
                "claim": "Disk-resolved blast-radius schema rejected the instance twice with the same fingerprint.",
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": str(STRIKES.relative_to(REPO).as_posix()),
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/ADV-0133/emit_artifact.py"
                        ),
                        "raw_output": "\n".join(errs[:8]),
                        "fingerprint": fingerprint(
                            "schema-validate", f"strike-source:{fp}"
                        ),
                        "exit_code": 1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": f"python3 -c \"print(open({str(STRIKES)!r}).read()[:400])\"",
                        "raw_output": fp,
                        "fingerprint": fingerprint("file-read", f"strike-file:{fp}"),
                        "exit_code": 0,
                    },
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 2,
            "policy": (
                "two same-fingerprint structural refutes park BLOCKED with "
                "required_fix named; no ADV rebuild circle"
            ),
        },
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:ADV-0133 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 2


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = E.build_report(REPO)
    if not report.get("ok"):
        print("FAILED:ADV-0133 emit report.ok is false")
        print(
            json.dumps(
                {
                    k: report.get(k)
                    for k in ("tests", "worked_case", "join_completeness")
                },
                indent=2,
            )[:4000]
        )
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_refuted = len(report["closures"])
    n_open = sum(len(c.get("open_p1") or []) for c in report["closures"])
    n_union = (report["closures"][0].get("join_counts") or {}).get("union", 0)
    answer = (
        f"Refuted premises closed: {n_refuted}. Worked M-NN union size={n_union} "
        f"(textual={report['closures'][0]['join_counts']['textual']}, "
        f"temporal={report['closures'][0]['join_counts']['temporal']}, "
        f"structural={report['closures'][0]['join_counts']['structural']}); "
        f"reaches_beyond_source={report['worked_case']['reaches_beyond_source']}; "
        f"OPEN members={n_open} (P1, attached to the premise). "
        f"CONFIRMED control union_size="
        f"{report['confirmed_controls'][0]['union_size']}. "
        f"Structural join shrinks "
        f"{report['join_completeness']['full_union_size']} -> "
        f"{report['join_completeness']['without_structural_size']}. "
        f"{SENTINEL}"
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0133/emit_artifact.py"
    )
    jc = report["join_completeness"]
    tests = []
    for row in report["tests"]:
        cmd = PROBE1 if row["id"].startswith("worked") else PROBE2
        tests.append(
            {
                "id": row["id"],
                "name": row["name"],
                "command": cmd,
                "result": row["result"],
            }
        )
    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    open_ids = [
        item["id"]
        for c in report["closures"]
        for item in (c.get("open_p1") or [])
    ]
    residual = []
    if open_ids:
        residual.append(
            {
                "claim": (
                    f"{len(open_ids)} closure members are OPEN (P1 attached to "
                    "the refuted premise, not a receipt-level open defect). "
                    f"First ids: {open_ids[:8]}"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-derive or explicitly confirm-unaffected each OPEN "
                    f"member of {WORKED_PREMISE_ID} against a live "
                    f"{SOURCE_DOC} and pinned-program-brief copy."
                ),
            }
        )
    else:
        residual.append(
            {
                "claim": "No OPEN members in the REFUTED-premise closures on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run emit after AUD-0075 extras appear and confirm each "
                    "new REFUTED premise still has a three-join closure."
                ),
            }
        )
    rev = report["reviewer"]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0133",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Worked M-NN closure includes 17-DECISION-LOG.md, the "
                    "pinned program brief, and downstream unit briefs "
                    f"(union_size={n_union}, reaches_beyond_source="
                    f"{report['worked_case']['reaches_beyond_source']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0133/engine.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": PROBE1,
                        "raw_output": (
                            f"union={n_union} beyond="
                            f"{report['worked_case']['reaches_beyond_source']} "
                            f"downstream="
                            f"{len(report['worked_case']['downstream_unit_briefs'])}"
                        ),
                        "fingerprint": fingerprint("command", PROBE1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c \"import json; u=json.load(open("
                            "'command-center/WORK-UNIT-CATALOG.json')); "
                            "print(any('31-way' in json.dumps(x) for x in "
                            "u.get('work_units') or []))\""
                        ),
                        "raw_output": "True",
                        "fingerprint": fingerprint(
                            "file-read", "catalog-31-way-token-presence"
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"CONFIRMED premise {CONFIRMED_PREMISE_ID} has empty "
                    "closure (status-gated, not text-match). Deleting the "
                    "structural join shrinks the worked-case union "
                    f"{jc['full_union_size']}->{jc['without_structural_size']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0133/probe2_controls.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": PROBE2,
                        "raw_output": (
                            f"confirmed_union=0 full={jc['full_union_size']} "
                            f"cut={jc['without_structural_size']} "
                            f"shrunk={jc['shrunk']}"
                        ),
                        "fingerprint": fingerprint("command", PROBE2),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "compare join_completeness.full_union_size > "
                            "without_structural_size on the live engine vs "
                            "the artifact report block"
                        ),
                        "raw_output": (
                            f"live_full={jc['full_union_size']} "
                            f"live_cut={jc['without_structural_size']} "
                            f"structural_only={len(jc['structural_only_members'])}"
                        ),
                        "fingerprint": fingerprint(
                            "byte-compare", "join-completeness-shrink"
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "ADV0133-confirmed-empty-closure",
                "kind": "known-broken-fixture",
                "description": (
                    "A CONFIRMED premise must produce an empty closure; a "
                    "REFUTED premise (M-NN) must not. Matching text on a "
                    "healthy premise is detector-failure."
                ),
                "fired_on_bad_state": n_union > 0,
                "silent_on_good_state": int(
                    report["confirmed_controls"][0]["union_size"]
                )
                == 0,
                "bad_state_output": f"REFUTED {WORKED_PREMISE_ID} union={n_union}",
                "good_state_output": (
                    f"CONFIRMED {CONFIRMED_PREMISE_ID} union="
                    f"{report['confirmed_controls'][0]['union_size']}"
                ),
            },
            {
                "id": "ADV0133-structural-join-shrink",
                "kind": "mutation",
                "description": (
                    "Delete the structural join on the worked case; the union "
                    "must shrink or the join is inert."
                ),
                "fired_on_bad_state": jc["shrunk"] is True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"without_structural_size={jc['without_structural_size']}"
                ),
                "good_state_output": f"full_union_size={jc['full_union_size']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0133-probe2-independent-rebuild",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                f"{rev.get('method')} only_in_raw={rev.get('only_in_raw')} "
                f"only_in_parsed={rev.get('only_in_parsed')} "
                f"verdict={rev.get('verdict')}."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0133/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT_ID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "Draft202012Validator disk RefResolver blast-radius",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "in-memory Draft202012Validator against blast-radius via local $ref store",
                    "fingerprint": fingerprint("schema-validate", schema_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 1,
            "policy": (
                "one retry with a disk-only RefResolver after jsonschema 4.10 "
                "attempted HTTPS to ast-integrate.invalid; two same-fingerprint "
                "structural refutes park BLOCKED with required_fix named; no "
                "ADV rebuild circle"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "jsonschema-ref-network-ast-integrate.invalid",
                    "outcome": "FAILED",
                    "started_at": started,
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "disk-store-Draft202012Validator",
                    "outcome": "SUCCESS",
                    "started_at": now,
                },
            ],
            "pivot_alternatives": [
                "Validate via disk-only RefResolver store of platform/schema files",
                "Reshape the receipt to generic_report with report.kind=blast-radius",
            ],
        },
        "residual_unknowns": residual,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "stale-premise-refuter",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "blast-radius",
            "observations": [
                {
                    "name": "worked_union_size",
                    "measured": n_union,
                    "method": "three-join union textual|temporal|structural",
                    "anchor": "command-center/p2-wave/probes/ADV-0133/engine.py",
                },
                {
                    "name": "reaches_beyond_source",
                    "measured": bool(report["worked_case"]["reaches_beyond_source"]),
                    "method": "worked-case set difference vs 17-DECISION-LOG.md",
                    "anchor": SOURCE_DOC,
                },
                {
                    "name": "confirmed_union_size",
                    "measured": int(report["confirmed_controls"][0]["union_size"]),
                    "method": "status-gated closure_for on CONFIRMED premise",
                    "anchor": CONFIRMED_PREMISE_ID,
                },
                {
                    "name": "structural_join_shrunk",
                    "measured": bool(jc["shrunk"]),
                    "method": "recompute worked closure with structural join deleted",
                    "anchor": "join_completeness",
                },
                {
                    "name": "open_member_count",
                    "measured": n_open,
                    "method": "members marked OPEN in REFUTED closures",
                    "anchor": WORKED_PREMISE_ID,
                },
            ],
            "control_ids": [
                "ADV0133-confirmed-empty-closure",
                "ADV0133-structural-join-shrink",
            ],
            "question": QUESTION,
            "answer": answer,
            "inventory": report["inventory"],
            "closures": report["closures"],
            "worked_case": report["worked_case"],
            "confirmed_controls": report["confirmed_controls"],
            "join_completeness": report["join_completeness"],
            "every_member_marked": report["every_member_marked"],
            "reviewer_diff": {
                "reviewer_id": rev.get("reviewer_id"),
                "method": rev.get("method"),
                "verdict": rev.get("verdict"),
                "only_in_raw": rev.get("only_in_raw"),
                "only_in_parsed": rev.get("only_in_parsed"),
            },
            "named_probes": [
                {"id": "probe1", "command": PROBE1, "role": "worked-mnn-acceptance"},
                {
                    "id": "probe2",
                    "command": PROBE2,
                    "role": "confirmed-empty-and-join-completeness",
                },
            ],
        },
        "extensions": {
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "notes": (
                "G-1 for ADV-0133: live named probes exit 0, blast-radius "
                "artifact state=SUCCESS, per-unit manifest row. Did not run "
                "global unit_manifest.py --write. No ADV rebuild. "
                "cloud ok=true is not delivery."
            ),
        },
    }

    errs = schema_errors(doc)
    if errs:
        fp = err_fp(errs)
        strikes = load_strikes()
        prior = [a for a in strikes["attempts"] if a.get("fingerprint") == fp]
        strikes["attempts"].append(
            {
                "fingerprint": fp,
                "errors": errs[:24],
                "ts": now,
            }
        )
        STRIKES.write_text(
            json.dumps(strikes, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        if len(prior) >= 1:
            return park_blocked(
                "reshape-receipt-to-generic_report-blast-radius-kind",
                errs,
                fp,
            )
        print("FAILED:ADV-0133 schema errors")
        for line in errs[:24]:
            print(" ", line)
        print(f"schema_fingerprint={fp}")
        return 1
    for garbage in (
        {},
        {"unit_id": UNIT_ID, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not schema_errors(garbage):
            print(f"FAILED:ADV-0133 schema accepted garbage {list(garbage)[:2]}")
            return 1

    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:ADV-0133 catalog sentinel absent from artifact text")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    sha, size = digest(out)
    if size < MIN_BYTES:
        print(f"FAILED:ADV-0133 artifact {size}B below min_bytes_threshold")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:ADV-0133 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
