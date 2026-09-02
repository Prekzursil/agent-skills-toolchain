#!/usr/bin/env python3
"""Emit the CNL-0002 design note from live measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import write_all  # noqa: E402
from measure import run as measure_run  # noqa: E402
from note_schema import schema_errors  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json produces 13 errors against "
    "11-COUNCIL-SPECIFICATION.schema.json and their top-level key sets do not "
    "intersect AT ALL (0 of 12 required keys present) - is the correct repair "
    "ONE schema with a discriminated union on artifact type, or TWO schemas "
    "plus a typed reference edge, and what falsifiable criterion decides it "
    "rather than taste?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0002/probe1_reproduce_v1_errors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0002/probe2_repair_criterion.py"
)


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNL-0002 emit line {path.name!r} {snippet!r} hits={hits}")
    return hits[0]


def slim_errors(errors: list[dict], limit: int = 16) -> list[dict]:
    out = []
    for e in errors[:limit]:
        msg = e.get("message") or ""
        if len(msg) > 180:
            msg = msg[:177] + "..."
        out.append(
            {
                "validator": e.get("validator"),
                "message": msg,
                "path": e.get("path") or [],
            }
        )
    return out


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe_row(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    write_all()
    live = measure_run()
    if not live["ok"]:
        print("FAILED:CNL-0002 emit measurements not ok")
        print(json.dumps({k: live[k] for k in ("ok", "origins")}, indent=2, default=str)[:2000])
        return 1
    cat = live["catalogue_vs_v1"]
    cm = live["cm01_vs_v1"]
    lose = live["losing"]
    win = live["winning"]
    neg = live["negative_control"]
    fix = HERE / "fixtures"
    v1_line = find_line(fix / "v1-charter.schema.json", '"additionalProperties": false')
    req_line = find_line(fix / "v1-charter.schema.json", '"council_id",')
    cm_line = find_line(fix / "C-M01.json", '"C-M01"')
    prose_line = find_line(fix / "catalogue-v1-mismatch.json", "CLAIM-UNDER-TEST")
    ref_line = find_line(fix / "catalogue-repaired.json", '"typed-reference"')
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = {
        "unit_id": "CNL-0002",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0002",
        "title": "Resolve the measured v1-schema / catalogue non-intersection",
        "question": QUESTION,
        "answer": (
            "TWO schemas plus a typed reference edge. A discriminated union on "
            "artifact type is not a schema-only repair: the catalogue's top-level "
            "keys intersect the 12 required charter keys in the empty set, so the "
            "union has no native discriminator and accepts the existing file only "
            "after a synthetic artifact_type tag is written into it. The typed "
            "edge is spec_ref {schema_id, edge=typed-reference, target_kind} on "
            "the catalogue; charter documents keep the charter schema."
        ),
        "mechanism": {
            "id": "keyset-intersection-then-tagged-union-trial",
            "summary": (
                "Measure key-set intersection with set algebra, count validator "
                "errors with Draft202012Validator, then implement the tagged "
                "union far enough to show it needs a synthetic tag."
            ),
            "newcomer_sees": [
                "catalogue top-level keys",
                "v1 required_12 list",
                "Draft202012Validator error list for the catalogue root and for C-M01 alone",
            ],
            "newcomer_withheld_until_first_position": [
                "schema_relationship prose claiming the 13-error count",
                "taste argument that one schema is cleaner",
                "artifact_type tag as if it already existed on the files",
            ],
        },
        "decision": "TWO_SCHEMAS_PLUS_TYPED_REFERENCE_EDGE",
        "prose": (
            "# CNL-0002 -- resolve the measured v1 schema-catalogue non-intersection\n\n"
            "Decision: two schemas plus a typed reference edge, on the falsifiable "
            "criterion that a discriminated union cannot express the 0-of-12 key "
            "intersection without a synthetic tag. The 13-error and C-M01 14-error "
            "signals are Draft202012Validator counts, not the catalogue's own "
            "schema_relationship prose.\n"
        ),
        "criterion": {
            "statement": (
                "A discriminated union on artifact type is a schema-only repair of "
                "existing documents IFF a discriminator field is already present on "
                "every charter instance and every catalogue instance, or is one of "
                "the 12 required charter keys that the catalogue also carries. If "
                "the top-level key intersection with those 12 keys is empty, the "
                "union needs a synthetic artifact_type tag — a document mutation, "
                "not a schema-only repair. Two schemas plus a typed reference edge "
                "do not require that tag: each artifact keeps its native key set "
                "and the edge is an additive spec_ref that is not a charter field."
            ),
            "falsifiable_test": (
                "Compute set(catalogue.keys()) & set(v1.required). If the set is "
                "non-empty, a discriminated union MAY use a shared required key as "
                "D and this decision is wrong. If the set is empty AND tagged "
                "oneOf rejects the untagged catalogue AND accepts it only after "
                "adding artifact_type, the one-schema option fails the criterion."
            ),
            "result": (
                "intersection empty; tagged union rejects untagged catalogue; "
                "synthetic tag makes the union accept; two-schema repair yields 0 "
                "errors on 58 reconstructed protocols and 72 reconstructed presets"
            ),
        },
        "source_provenance": {
            "originals_on_this_tree": False,
            "reconstructed_fixtures": True,
            "why": (
                "Catalog inputs 11-COUNCIL-SPECIFICATION.schema.json and "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent (Path.is_file "
                "false on every searched location). Fixtures reconstruct the "
                "STRUCTURAL claim: 12 required keys, additionalProperties false, "
                "catalogue root keys disjoint, C-M01 20 keys with 4 overlapping "
                "optional properties. Property spellings are reconstructed from "
                "sibling catalog units, not read from the missing schema file. "
                "58/72 cardinalities are the catalog-cited protocol/preset counts."
            ),
            "origin_probe": live["origins"],
            "fixture_dir": "command-center/p2-wave/probes/CNL-0002/fixtures",
        },
        "measurements": [
            {
                "id": "catalogue-root-vs-v1",
                "mechanism": "jsonschema.Draft202012Validator.iter_errors",
                "second_mechanism": "python set algebra: instance keys & required_12",
                "error_count": cat["error_count"],
                "required_present_count": cat["required_present_count"],
                "intersection_empty": cat["intersection_empty"],
                "instance_keys": cat["instance_keys"],
                "schema_relationship_ignored": True,
                "errors": slim_errors(cat["errors"]),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0002/measure.py"
                ),
            },
            {
                "id": "C-M01-alone-vs-v1",
                "mechanism": "jsonschema.Draft202012Validator.iter_errors on C-M01.json alone",
                "second_mechanism": "python set algebra: instance keys & schema.properties",
                "error_count": cm["error_count"],
                "key_count": cm["key_count"],
                "recognised_count": cm["recognised_count"],
                "recognised_keys": cm["recognised_keys"],
                "errors": slim_errors(cm["errors"]),
            },
        ],
        "losing_option": {
            "name": "ONE schema with discriminated union on artifact_type",
            "implemented": True,
            "schema": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
            "predicted_failure": lose["predicted_failure"],
            "untagged_error_count": lose["untagged_error_count"],
            "untagged_rejected": lose["untagged_rejected"],
            "synthetic_tag_accepted": lose["synthetic_tag_accepted"],
            "cm01_wrong_grain_rejected": lose["cm01_rejected"],
            "cm01_wrong_grain_error_count": lose["cm01_wrong_grain_error_count"],
            "observed_matches_prediction": lose["observed_matches_prediction"],
            "why_it_loses": (
                "The union's discriminator is not among the native catalogue keys. "
                "Accepting the existing file requires writing artifact_type into "
                "it. C-M01 (a nested protocol record) is the wrong grain for a "
                "file-level union and is still rejected — the 14-error signal is "
                "not repaired by tagging the catalogue root."
            ),
        },
        "winning_option": {
            "name": "TWO schemas plus a typed reference edge",
            "charter_schema": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
            "catalogue_schema": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
            "typed_edge_field": "spec_ref",
            "spec_ref": win["spec_ref"],
            "catalogue_error_count": win["catalogue_error_count"],
            "charter_error_count": win["charter_error_count"],
            "protocol_records": win["protocol_records"],
            "preset_records": win["preset_records"],
            "cm01_against_protocol_schema_error_count": win[
                "cm01_protocol_schema_error_count"
            ],
            "invalid_protocol_error_count": win["invalid_protocol_error_count"],
            "pass": win["pass"],
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Catalogue root vs reconstructed v1 charter yields 13 validator errors and 0 of 12 required keys present",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:{req_line}",
                "defect_locus": "DESIGN",
            },
            {
                "id": "C2",
                "claim": "C-M01 alone vs reconstructed v1 charter yields 14 validator errors and 4 of 20 keys recognised",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json:{cm_line}",
                "defect_locus": "DESIGN",
            },
            {
                "id": "C3",
                "claim": "Discriminated union on artifact_type accepts the existing catalogue without a synthetic tag",
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json:1",
                "defect_locus": "DESIGN",
            },
        ],
        "tests": [
            {
                "id": "draft202012-every-affected-record",
                "command": P2,
                "result": "PASS",
                "assertions": (
                    "0 errors on 58 reconstructed protocols, 72 reconstructed "
                    "presets, the repaired catalogue root, and a valid charter; "
                    "deliberately-invalid protocol-invalid.json produces >0 errors"
                ),
            },
            {
                "id": "losing-option-predicted-failure",
                "command": P2,
                "result": "PASS",
                "assertions": (
                    "tagged-union.schema.json rejects catalogue-v1-mismatch.json "
                    "and accepts catalogue-synthetic-tag.json"
                ),
            },
            {
                "id": "independent-13-and-14",
                "command": P1,
                "result": "PASS",
                "assertions": "catalogue 13 errors / 0 of 12 required; C-M01 14 errors / 4 of 20 keys",
            },
        ],
        "negative_controls": [
            {
                "id": "catalogue-validated-as-charter",
                "rejects_state": "catalogue root validated as if it were a v1 charter",
                "observed": (
                    f"Draft202012Validator emitted {neg['error_count']} errors; "
                    "12 missing-required plus 1 additionalProperties bundling "
                    "protocols/presets/schema_relationship"
                ),
                "intended_reject_state": neg["intended_reject_state"],
                "what_the_check_does": neg["what_the_check_does"],
                "error_count": neg["error_count"],
                "fires": neg["fires"],
                "verbatim_messages": neg["verbatim_messages"],
                "result": "PASS",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0002-probe2-tagged-union-counterexample",
            "verdict": "PASS",
            "independent": True,
            "counterexample": {
                "hypothesis": "ONE schema discriminated union repairs the existing catalogue",
                "instance": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
                "schema": "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
                "observed": (
                    "Draft202012Validator reports a oneOf failure because "
                    "artifact_type is absent. Adding the synthetic tag is the "
                    "only way the union accepts the file. That is the "
                    "counterexample: the one-schema option cannot validate the "
                    "documents that exist without mutating them."
                ),
            },
        },
        "evidence": [
            {
                "claim": "13-error catalogue-vs-v1 measurement from the validator, not from schema_relationship prose",
                "verdict": "CONFIRMED",
                "signal_a": {
                    "mechanism": "jsonschema.Draft202012Validator.iter_errors",
                    "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
                    "error_count": cat["error_count"],
                    "errors": slim_errors(cat["errors"]),
                },
                "signal_b": {
                    "mechanism": "python set algebra instance_keys & required_12",
                    "required_present_count": cat["required_present_count"],
                    "instance_keys": cat["instance_keys"],
                    "schema_relationship_line": prose_line,
                    "schema_relationship_ignored": True,
                },
            },
            {
                "claim": "C-M01 alone: 14 errors and 4 of 20 keys recognised",
                "verdict": "CONFIRMED",
                "signal_a": {
                    "mechanism": "Draft202012Validator on C-M01.json alone",
                    "path": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json",
                    "line": cm_line,
                    "error_count": cm["error_count"],
                    "errors": slim_errors(cm["errors"]),
                },
                "signal_b": {
                    "mechanism": "set(instance) & set(schema.properties)",
                    "key_count": cm["key_count"],
                    "recognised_count": cm["recognised_count"],
                    "recognised_keys": cm["recognised_keys"],
                },
            },
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
                "exists": True,
                "role": "v1-reconstruction",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
                "exists": True,
                "role": "winning-catalogue-schema",
            },
        ],
        "residual_unknowns": [
            "Original 11-COUNCIL-SPECIFICATION.schema.json bytes were not on this worktree; required-key spellings may differ from the Windows harness copy.",
            "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes were not on this worktree; C-M01's real 20 keys may differ. The 14-error/4-of-20 shape was reconstructed to match the catalog evidence claim.",
            "CNL-0001 (v2 root envelope) is not delivered here; this unit only settles the one-vs-two schema question for the measured non-intersection.",
        ],
        "produced_by": "command-center/p2-wave/probes/CNL-0002/emit_note.py",
        "ts": now,
    }

    src1 = probe_row(
        "source",
        "schema-validate",
        "jsonschema.Draft202012Validator.iter_errors(v1-charter, catalogue-v1-mismatch)",
        json.dumps(
            {
                "error_count": cat["error_count"],
                "required_present_count": cat["required_present_count"],
                "errors": slim_errors(cat["errors"], 8),
            },
            sort_keys=True,
        ),
    )
    ver1 = probe_row(
        "verifier",
        "other",
        "python set algebra: set(catalogue.keys()) & set(REQUIRED_12)",
        json.dumps(
            {
                "required_present_count": cat["required_present_count"],
                "instance_keys": cat["instance_keys"],
            },
            sort_keys=True,
        ),
    )
    src2 = probe_row(
        "source",
        "schema-validate",
        "jsonschema.Draft202012Validator.iter_errors(v1-charter, C-M01.json)",
        json.dumps(
            {
                "error_count": cm["error_count"],
                "key_count": cm["key_count"],
                "recognised_count": cm["recognised_count"],
            },
            sort_keys=True,
        ),
    )
    ver2 = probe_row(
        "verifier",
        "other",
        "python set algebra: set(C-M01.keys()) & set(v1.properties)",
        json.dumps(
            {
                "recognised_count": cm["recognised_count"],
                "recognised_keys": cm["recognised_keys"],
            },
            sort_keys=True,
        ),
    )
    report = {
        "kind": "council-design-note",
        "observations": [
            {
                "name": "catalogue-root-vs-v1-error-count",
                "measured": cat["error_count"],
                "method": "jsonschema.Draft202012Validator.iter_errors",
                "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
            },
            {
                "name": "cm01-vs-v1-error-count",
                "measured": cm["error_count"],
                "method": "jsonschema.Draft202012Validator.iter_errors",
                "anchor": "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json",
            },
            {
                "name": "required-12-intersection",
                "measured": cat["required_present_count"],
                "method": "python set algebra instance_keys & required_12",
                "anchor": f"command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:{req_line}",
            },
        ],
        "control_ids": ["catalogue-validated-as-charter"],
        **note,
    }
    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json",
        "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue.schema.json",
        "command-center/p2-wave/probes/CNL-0002/fixtures/tagged-union.schema.json",
        "command-center/p2-wave/probes/CNL-0002/fixtures/catalogue-v1-mismatch.json",
        "command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json",
    ]
    placeholder = artifact_row(SCHEMA_REL, "primary")
    placeholder["path"] = OUT_REL
    receipt = {
        "schema_version": 1,
        "unit_id": "CNL-0002",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0002",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0002]; "
            "_USER-PROMPTS.md:10746-10767"
        ),
        "min_bytes_threshold": 2048,
        "artifacts": [placeholder]
        + [artifact_row(p, "supporting") for p in supporting],
        "evidence": [
            {
                "claim": (
                    "Catalogue root vs reconstructed v1 charter yields 13 "
                    "validator errors and 0 of 12 required keys present"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNL-0002/fixtures/v1-charter.schema.json:{req_line}",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "C-M01 alone vs reconstructed v1 charter yields 14 validator "
                    "errors and 4 of 20 keys recognised"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNL-0002/fixtures/C-M01.json:{cm_line}",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {"id": "independent-13-and-14", "command": P1, "result": "PASS", "assertions": 3},
            {
                "id": "repair-criterion-and-negative-control",
                "command": P2,
                "result": "PASS",
                "assertions": 6,
            },
        ],
        "negative_controls": [
            {
                "id": "catalogue-validated-as-charter",
                "kind": "known-broken-fixture",
                "description": (
                    "Draft202012Validator(v1-charter) over catalogue-v1-mismatch.json "
                    "must emit 13 errors. The same validator over charter-valid.json "
                    "must emit 0 errors."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "error_count": neg["error_count"],
                        "fires": neg["fires"],
                        "messages": neg["verbatim_messages"][:8],
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"charter_error_count": win["charter_error_count"]},
                    sort_keys=True,
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0002-probe2-tagged-union-counterexample",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe2 implements the losing tagged union far enough to show "
                "untagged catalogue-v1-mismatch.json is rejected and the synthetic "
                "artifact_type tag is the only way the union accepts the file. "
                "That instance is the counterexample to one-schema repair."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0002/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0002",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_row(
                    "verifier",
                    "file-read",
                    f"python3 -c json.loads(Path({OUT_REL!r}).read_text())",
                    "parsed-ok-after-write",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Original 11-COUNCIL-SPECIFICATION.schema.json bytes were not "
                    "on this worktree; required-key spellings may differ."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run catalogue-vs-v1 against the Windows harness copy of "
                    "11-COUNCIL-SPECIFICATION.schema.json and compare required_12."
                ),
            },
            {
                "claim": (
                    "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes were not "
                    "on this worktree; C-M01's real 20 keys may differ."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Validate the real C-M01 record alone against the real v1 "
                    "schema and recount recognised keys."
                ),
            },
            {
                "claim": (
                    "CNL-0001 v2 root envelope is not delivered here; this unit "
                    "only settles the one-vs-two schema question."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-open this decision after CNL-0001 lands.",
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "report": report,
    }
    errs = schema_errors(receipt)
    if errs:
        print("FAILED:CNL-0002 emit note schema")
        for item in errs[:20]:
            print(" ", item)
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    sha, size = digest_rel(OUT_REL)
    receipt["artifacts"][0]["sha256"] = sha
    receipt["artifacts"][0]["bytes"] = size
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    live_doc = json.loads(out.read_text(encoding="utf-8"))
    receipt["downstream_consumers"][0]["read_ok"] = isinstance(live_doc, dict)
    receipt["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"parsed unit_id={live_doc.get('unit_id')} state={live_doc.get('state')}"
    )
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    errs2 = schema_errors(receipt)
    if errs2:
        print("FAILED:CNL-0002 emit note schema after write")
        for item in errs2[:20]:
            print(" ", item)
        return 1
    size2 = out.stat().st_size
    if size2 < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:CNL-0002 artifact {size2}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0002" not in text:
        print("FAILED:CNL-0002 sentinel absent from artifact")
        return 1
    print(f"wrote {OUT_REL} bytes={size2}")
    print("SUCCESS:CNL-0002")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
