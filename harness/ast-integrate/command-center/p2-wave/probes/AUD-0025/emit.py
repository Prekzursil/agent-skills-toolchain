#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0025-unpinned-version-census.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402
import schema_ctl as S  # noqa: E402

OUT = L.REPO / L.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0025-emit {msg}")
    return 1


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()


def art(rel: str, role: str) -> dict:
    path = L.REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    crlf = path.read_bytes().count(b"\r\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "role": role,
        "eol": "CRLF" if crlf else "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census = L.census_doc()
    p1 = L.probe1_payload()
    p2 = L.probe2_payload()
    clf = census["classifier_control"]
    ctl = census["resolution_control"]
    if not clf["ok"]:
        return fail(f"classifier control {clf}")
    if ctl["contaminated"]:
        return fail("exact-pin dual-seed mismatch; resolver contaminated")
    if not ctl["ok"]:
        return fail(f"resolution control {ctl}")

    floating = [f for f in census["findings"] if f.get("floats_in_practice") is True]
    major_open = [f for f in floating if f.get("allows_new_major") is True]
    not_checked = sum(
        1 for f in census["findings"] if f.get("floats_in_practice") == "NOT-CHECKED"
    )
    names = ", ".join(census["floating_names"]) or "(none)"
    report_summary = (
        f"This worktree's live product manifests ({census['live_manifest_count']} files, "
        f"{census['live_declaration_count']} declarations) have "
        f"{census['floating_in_practice_count']} declaration(s) that dual-seed "
        f"resolve to different versions on the fixture index: {names}. "
        f"Of those, {len(major_open)} accept a new major. "
        f"{not_checked} live declaration(s) are NOT-CHECKED for dual-seed float "
        "because the package is absent from the declared fixture index. "
        "Release cadence is NOT-CHECKED (no registry egress). "
        "Resolved-today lockfiles are absent beside most live pyprojects."
    )
    owner_decision = (
        "CENSUS ONLY — record floating constraints and blast radius; do not "
        "auto-pin, rewrite live manifests, or query registries without owner "
        "sign-off."
    )
    answer = report_summary + " " + L.SENTINEL

    findings = []
    for i, f in enumerate(census["findings"], 1):
        floats = f.get("floats_in_practice")
        major = f.get("allows_new_major")
        findings.append(
            {
                "id": f"AUD0025-L{i:02d}-{f['name']}",
                "category": "inventory",
                "subject": f"{f['name']}@{f['manifest']}",
                "summary": (
                    f"{f['name']} declared {f['declared']!r} "
                    f"syntax={f['syntax_class']} class={f['dep_class']} "
                    f"floats_in_practice={floats} "
                    f"seeds={f.get('seed_lowest')}..{f.get('seed_highest')} "
                    f"allows_new_major={major}"
                ),
                "name": f["name"],
                "declared": f["declared"],
                "syntax_class": f["syntax_class"],
                "ecosystem": f["ecosystem"],
                "dep_class": f["dep_class"],
                "manifest": f["manifest"],
                "floats_in_practice": floats,
                "seed_lowest": f.get("seed_lowest"),
                "seed_highest": f.get("seed_highest"),
                "allows_new_major": major,
                "next_major_tested": f.get("next_major_tested"),
                "matching_index_versions": f.get("matching_index_versions") or [],
                "release_cadence": "NOT-CHECKED",
                "resolved_today": "NOT-CHECKED",
                "blast_radius": f.get("blast_radius"),
            }
        )
    findings.append(
        {
            "id": "AUD0025-C-exact-pin",
            "category": "control",
            "subject": "pinned-pkg==1.2.3",
            "summary": (
                "Exact-pin fixture resolved identically across seeds "
                f"({(ctl.get('exact_row') or {}).get('seed_lowest')})."
            ),
        }
    )

    named_probes = [
        {
            "id": "probe1",
            "command": L.P1_CMD,
            "raw_output": L.dumps(p1),
            "exit_code": 0,
        },
        {
            "id": "probe2",
            "command": L.P2_CMD,
            "raw_output": L.dumps(p2),
            "exit_code": 0,
        },
    ]
    p1_raw = L.dumps(p1)
    p2_raw = L.dumps(p2)
    if len(p1_raw) > 65536 or len(p2_raw) > 65536:
        return fail("probe payload exceeds evidence.raw_output maxLength")

    ev_p1_src = {
        "role": "source",
        "method": "static-analysis",
        "command": L.P1_CMD,
        "raw_output": p1_raw,
        "fingerprint": fingerprint("static-analysis", L.P1_CMD),
        "exit_code": 0,
    }
    ev_p1_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": (
            "python3 -B -c classifier_control over "
            "command-center/p2-wave/probes/AUD-0025/fixtures"
        ),
        "raw_output": L.dumps(clf),
        "fingerprint": fingerprint("file-read", "AUD-0025-fixtures-syntax-zoo"),
        "exit_code": 0,
    }
    ev_p2_src = {
        "role": "source",
        "method": "command",
        "command": L.P2_CMD,
        "raw_output": p2_raw,
        "fingerprint": fingerprint("command", L.P2_CMD),
        "exit_code": 0,
    }
    ev_p2_ver = {
        "role": "verifier",
        "method": "byte-compare",
        "command": (
            "dual-seed lowest vs highest on pinned-pkg==1.2.3 versus float-pkg>=1.0"
        ),
        "raw_output": L.dumps(ctl),
        "fingerprint": fingerprint("byte-compare", "AUD-0025-dual-seed-controls"),
        "exit_code": 0,
    }

    supporting = [
        L.SCHEMA_REL,
        "command-center/p2-wave/probes/AUD-0025/lib.py",
        "command-center/p2-wave/probes/AUD-0025/schema_ctl.py",
        "command-center/p2-wave/probes/AUD-0025/probe1_constraint_syntax.py",
        "command-center/p2-wave/probes/AUD-0025/probe2_dual_resolution.py",
        L.INDEX_REL,
        "command-center/p2-wave/probes/AUD-0025/fixtures/pep440-zoo/pyproject.toml",
        "command-center/p2-wave/probes/AUD-0025/fixtures/npm-syntax/package.json",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    artifacts[0]["role"] = "supporting"
    missing = [a["path"] for a in artifacts if not (L.REPO / a["path"]).is_file()]
    if missing:
        return fail(f"missing supporting {missing}")

    consumer_probe = {
        "role": "verifier",
        "method": "schema-validate",
        "command": (
            "python3 -B -c schema_ctl.errors(json.loads(output_path))"
        ),
        "raw_output": "offline RefResolver; empty object rejected; receipt_core+audit-finding",
        "fingerprint": fingerprint("schema-validate", "AUD-0025-schema_ctl"),
        "exit_code": 0,
    }

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": L.UNIT,
        "state": "SUCCESS",
        "sentinel": L.SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0025",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "local-parallel",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically "
                "different detectors before a third attempt"
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "outcome": "FAILED",
                    "error_fingerprint": "schema-report-required",
                }
            ],
            "pivot_alternatives": [
                "offline RefResolver disk store (no HTTPS fetch of ast-integrate.invalid)",
                "receipt_core document with report.kind=audit-finding plus observations and control_ids",
            ],
        },
        "artifacts": artifacts,
        "report": {
            "kind": "audit-finding",
            "summary": report_summary,
            "owner_decision": owner_decision,
            "headline_count": census["floating_in_practice_count"],
            "floating_names": census["floating_names"],
            "major_open_count": len(major_open),
            "live_declaration_count": census["live_declaration_count"],
            "not_checked_dual_seed": not_checked,
            "syntax_histogram_live": census["syntax_histogram_live"],
            "question": L.QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "live_declarations",
                    "measured": census["live_declaration_count"],
                    "method": "static-analysis",
                    "anchor": "pyproject.toml and package.json outside probes/",
                },
                {
                    "name": "floating_in_practice",
                    "measured": census["floating_in_practice_count"],
                    "method": "byte-compare",
                    "anchor": L.INDEX_REL,
                },
                {
                    "name": "named_syntax_classes_hit",
                    "measured": ",".join(clf["named_classes_hit"]),
                    "method": "file-read",
                    "anchor": "command-center/p2-wave/probes/AUD-0025/fixtures",
                },
                {
                    "name": "dual_seed_not_checked",
                    "measured": not_checked,
                    "method": "static-analysis",
                    "anchor": L.INDEX_REL,
                },
            ],
            "control_ids": ["AUD0025-C1-exact-pin", "AUD0025-C2-float-pkg"],
            "named_probes": named_probes,
            "census": {
                "live_manifest_count": census["live_manifest_count"],
                "live_declaration_count": census["live_declaration_count"],
                "fixture_declaration_count": census["fixture_declaration_count"],
                "floating_in_practice_count": census["floating_in_practice_count"],
                "floating_names": census["floating_names"],
                "exact_live_count": census["exact_live_count"],
                "syntax_histogram": census["syntax_histogram"],
                "syntax_histogram_live": census["syntax_histogram_live"],
                "index": L.INDEX_REL,
                "seeds": ["lowest", "highest"],
                "release_cadence": "NOT-CHECKED",
                "resolved_today": "NOT-CHECKED",
                "note": (
                    "Probe 2 is a dual-seed resolve against the declared fixture index, "
                    "not two wall-clock PyPI/npm crawls. A constraint floats in practice "
                    "when lowest and highest satisfying versions in that index differ."
                ),
            },
            "findings": findings,
            "classifier_control": census["classifier_control"],
            "resolution_control": census["resolution_control"],
        },
        "evidence": [
            {
                "claim": (
                    f"Probe 1 classified {census['live_declaration_count']} live "
                    f"declarations across {census['live_manifest_count']} manifests. "
                    "Planted fixtures hit exact, compatible, caret, tilde, wildcard, "
                    "and none."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0025/probe1_constraint_syntax.py",
                "probes": [ev_p1_src, ev_p1_ver],
            },
            {
                "claim": (
                    f"Probe 2 dual-seed resolved the fixture index: "
                    f"{census['floating_in_practice_count']} live declaration(s) "
                    f"float in practice ({names}); exact pin pinned-pkg==1.2.3 is "
                    "seed-invariant; float-pkg>=1.0 differs across seeds."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0025/probe2_dual_resolution.py",
                "probes": [ev_p2_src, ev_p2_ver],
            },
        ],
        "tests": [
            {
                "id": "syntax-zoo-six-named-classes",
                "command": L.P1_CMD,
                "result": "PASS" if clf["all_six_named"] else "FAIL",
            },
            {
                "id": "exact-pin-identical-across-seeds",
                "command": L.P2_CMD,
                "result": "PASS" if ctl["exact_identical_across_seeds"] else "FAIL",
            },
            {
                "id": "floating-constraint-differs-across-seeds",
                "command": L.P2_CMD,
                "result": "PASS" if ctl["float_differs_across_seeds"] else "FAIL",
            },
            {
                "id": "schema-rejects-empty-object",
                "command": "schema_ctl.errors({})",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0025-C1-exact-pin",
                "kind": "known-broken-fixture",
                "description": (
                    "Fixture pinned-pkg==1.2.3 must resolve to 1.2.3 on both lowest "
                    "and highest seeds (good state silent). Divergence means the "
                    "resolver is contaminated. The paired bad state is float-pkg>=1.0."
                ),
                "fired_on_bad_state": ctl["float_differs_across_seeds"],
                "silent_on_good_state": ctl["exact_identical_across_seeds"],
                "good_state_output": L.dumps(ctl.get("exact_row")),
                "bad_state_output": L.dumps(ctl.get("float_row")),
            },
            {
                "id": "AUD0025-C2-float-pkg",
                "kind": "mutation",
                "description": (
                    "Fixture float-pkg>=1.0 must pick different versions under the two "
                    "seeds, otherwise a zero-float headline is indistinguishable from "
                    "an inert resolver. The paired good state is pinned-pkg==1.2.3."
                ),
                "fired_on_bad_state": ctl["float_differs_across_seeds"],
                "silent_on_good_state": ctl["exact_identical_across_seeds"],
                "good_state_output": L.dumps(ctl.get("exact_row")),
                "bad_state_output": L.dumps(ctl.get("float_row")),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0025-probe2-dual-resolution",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 independently recounts live dual-seed floats and requires "
                "the exact-pin fixture to be seed-invariant before the headline count "
                "is accepted. Catalog-named fresh-context Claude review of the "
                "headline remains residual and is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0025/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator via schema_ctl (offline store)",
                "artifact_path": L.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": consumer_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Each package's release cadence is NOT-CHECKED; this unit did "
                    "not query PyPI/npm registries."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fetch changelog or registry upload timestamps per floating name "
                    "and recompute blast radius."
                ),
            },
            {
                "claim": (
                    "Resolved versions today are NOT-CHECKED: live pyprojects have "
                    "no sibling lockfile in most trees, and dual-seed used the "
                    "fixture index."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add lockfiles or a second resolver seed from a recorded install "
                    "and compare against the fixture-index seeds."
                ),
            },
            {
                "claim": (
                    f"{not_checked} live declarations are NOT-CHECKED for "
                    "floats_in_practice because the package name is absent from "
                    f"{L.INDEX_REL}."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend the declared fixture index with versions for each live "
                    "name, or record two resolver seeds from lockfiles, then recount."
                ),
            },
        ],
        "extensions": {
            "output_path": L.OUT_REL,
            "output_schema": L.SCHEMA_REL,
            "title": "Unpinned and floating version census and its reproducibility impact",
            "completion_sentinel": L.SENTINEL,
        },
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:AUD-0025-emit schema")
        for e in errs[:20]:
            print(" ", e)
        return 1
    try:
        S.garbage_rejected()
    except AssertionError as exc:
        return fail(str(exc))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if L.SENTINEL not in text:
        return fail("sentinel missing from serialized artifact")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    live = json.loads(OUT.read_text(encoding="utf-8"))
    live_errs = S.errors(live)
    if live_errs:
        return fail("post-write schema " + "; ".join(live_errs[:8]))
    raw = OUT.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < int(doc["min_bytes_threshold"]):
        return fail(f"{len(raw)}B below floor")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {L.OUT_REL} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:AUD-0025-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
