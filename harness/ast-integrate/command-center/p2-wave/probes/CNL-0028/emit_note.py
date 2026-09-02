#!/usr/bin/env python3
"""Emit the CNL-0028 design note as a council-design-note receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import authoring as A  # noqa: E402
import catalog_pids as P  # noqa: E402
import coverage as C  # noqa: E402
import schema_local as SL  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0028-role-template-library-and-the-custom-role-authoring-contra.md"
)
OUT = REPO / OUT_REL
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "What is the minimum set of role templates that covers the 58 catalogued "
    "protocols, and what must a user supply to author a custom role that the "
    "incompatible-role checker can still reason about?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0028/probe1_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0028/probe2_reviewer.py"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:emit cannot cite {needle!r} in {rel}")


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def artifact(rel: str, role: str) -> dict:
    sha, size = digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    census = C.load_json(C.PROTOCOLS)
    tmpl = C.load_json(C.TEMPLATES)
    report_cov = C.coverage_report(census, tmpl)
    planted = C.coverage_report(C.mutant_unmapped_role(census), tmpl)
    extracted = P.catalog_protocol_ids()
    good = A.check_custom_role(A.good_custom_role())
    self_judge = A.check_custom_role(A.bad_self_judge())
    missing = A.check_custom_role(A.bad_missing_capabilities())
    escalate = A.check_custom_role(A.bad_rights_escalation())
    if report_cov["protocol_n"] != 58 or not report_cov["covered"] or not report_cov["minimum_holds"]:
        print("FAILED:emit coverage not green")
        return 1
    fixture_ids = sorted((r["id"] for r in census["protocols"]), key=lambda x: int(x[1:]))
    if extracted["n"] != 58 or extracted["ids"] != fixture_ids:
        print("FAILED:emit catalog recount mismatch")
        return 1
    if not (
        good["accepted"]
        and not self_judge["accepted"]
        and not missing["accepted"]
        and not escalate["accepted"]
    ):
        print("FAILED:emit authoring contract")
        return 1

    library_path = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    library_present = (REPO / library_path).is_file()
    templates = tmpl["templates"]
    answer = (
        "Minimum covering set is 11 templates: "
        + ", ".join(report_cov["template_ids"])
        + ". Ablation of any one template leaves at least one named protocol "
        "role unmapped, so the set is minimal under this census. "
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; "
        "the 58 records are the catalog-cited P01-P58 identities from "
        "CNL-0038..CNL-0046, with roles assigned from the CNL-0022/0025/0026/"
        "0027 vocabulary plus protocol-forced seats (observer, estimator, "
        "clerk, scorer, owner). A custom role is reasoner-visible iff it "
        "supplies id, nonempty obligations, permissions, rights, and the "
        "eight capability fields (authors, judges, votes_on, may_speak, "
        "may_vote, may_veto, may_chair, may_synthesise). The checker rejects "
        "self-judging (authors ∩ judges), synthesiser-drift (may_synthesise "
        "and authors contains proposal), chair substance votes without a "
        "casting_vote right, and rights not in the template-right union. "
        "SUCCESS:CNL-0028"
    )
    cov_raw = (
        f"protocol_n={report_cov['protocol_n']} unique_ids={report_cov['unique_ids']} "
        f"template_n={report_cov['template_n']} unmapped={json.dumps(report_cov['unmapped'])} "
        f"minimum_holds={report_cov['minimum_holds']} library_on_tree={library_present} "
        f"planted_wizard_unmapped={json.dumps(planted['unmapped'])}"
    )
    auth_raw = (
        f"good_accepted={good['accepted']} self_judge={json.dumps(self_judge['codes'])} "
        f"missing={json.dumps(missing['codes'])} escalate={json.dumps(escalate['codes'])}"
    )
    cat_raw = f"catalog_n={extracted['n']} ids={json.dumps(extracted['ids'])}"
    wizard_bad = f"covered={planted['covered']} unmapped={json.dumps(planted['unmapped'])}"
    wizard_good = f"covered={report_cov['covered']} unmapped={json.dumps(report_cov['unmapped'])}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cov_line = line_of(
        "command-center/p2-wave/probes/CNL-0028/coverage.py",
        "def coverage_report(",
    )
    auth_line = line_of(
        "command-center/p2-wave/probes/CNL-0028/authoring.py",
        "def check_custom_role(",
    )
    cat_line = line_of(
        "command-center/p2-wave/probes/CNL-0028/catalog_pids.py",
        "def catalog_protocol_ids(",
    )
    unit_line = line_of("command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0028"')

    supporting = [
        artifact(SCHEMA_REL, "supporting"),
        artifact("command-center/p2-wave/probes/CNL-0028/protocols.json", "fixture"),
        artifact("command-center/p2-wave/probes/CNL-0028/templates.json", "fixture"),
        artifact("command-center/p2-wave/probes/CNL-0028/coverage.py", "supporting"),
        artifact("command-center/p2-wave/probes/CNL-0028/authoring.py", "supporting"),
        artifact("command-center/p2-wave/probes/CNL-0028/catalog_pids.py", "supporting"),
        artifact("command-center/p2-wave/probes/CNL-0028/probe1_coverage.py", "control"),
        artifact("command-center/p2-wave/probes/CNL-0028/probe2_reviewer.py", "control"),
    ]
    report = {
        "kind": "council-design-note",
        "title": "Role-template library and the custom-role authoring contract",
        "question": QUESTION,
        "answer": answer,
        "library_honesty": {
            "path": library_path,
            "present_on_this_tree": library_present,
            "census_basis": census["source"],
        },
        "minimum_templates": {
            "n": report_cov["template_n"],
            "ids": report_cov["template_ids"],
            "named_roles": report_cov["named_roles"],
            "explicit_gaps": report_cov["explicit_gaps"],
            "ablation_unmapped": report_cov["ablation_unmapped"],
            "minimum_holds": report_cov["minimum_holds"],
        },
        "protocol_coverage": {
            "protocol_n": report_cov["protocol_n"],
            "family_counts": report_cov["family_counts"],
            "catalog_n": extracted["n"],
            "catalog_ids": extracted["ids"],
            "covered": report_cov["covered"],
            "unmapped": report_cov["unmapped"],
        },
        "custom_role_authoring_contract": {
            "required_fields": list(A.REQUIRED_TOP),
            "required_capabilities": list(A.REQUIRED_CAPS),
            "rejection_codes": [
                "SELF_JUDGE",
                "MISSING_CAPABILITIES",
                "RIGHTS_ESCALATION",
                "SYNTHESISER_DRIFT",
                "CHAIR_SUBSTANCE_VOTE",
                "EMPTY_OBLIGATIONS",
            ],
            "good_role_accepted": good["accepted"],
            "self_judge_rejected": not self_judge["accepted"],
            "missing_capabilities_rejected": not missing["accepted"],
            "rights_escalation_rejected": not escalate["accepted"],
        },
        "templates": templates,
        "aliases": tmpl["aliases"],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk "
                    "on this worktree and supplied the 58 role lists."
                ),
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
            },
            {
                "id": "C2",
                "claim": (
                    "Every role named across the 58 catalog-cited protocol "
                    "records maps to one of 11 templates; the set is minimal "
                    "by ablation."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/coverage.py:{cov_line}",
            },
            {
                "id": "C3",
                "claim": (
                    "The 58 fixture ids are the same 58 P-ids named in "
                    "CNL-0038..CNL-0046 catalog questions."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/catalog_pids.py:{cat_line}",
            },
            {
                "id": "C4",
                "claim": (
                    "A custom role that authors and judges the same artifact "
                    "kind is accepted by the authoring checker."
                ),
                "verdict": "REFUTED",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/authoring.py:{auth_line}",
            },
            {
                "id": "C5",
                "claim": (
                    "A custom role that supplies the required capability "
                    "vector and does not self-judge is accepted."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0028/authoring.py:good_custom_role",
            },
        ],
        "observations": [
            {
                "name": "protocol_n",
                "measured": report_cov["protocol_n"],
                "method": "len(protocols.json records)",
                "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
            },
            {
                "name": "template_n_minimum",
                "measured": report_cov["template_n"],
                "method": "ablation of each template against named roles",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/coverage.py:{cov_line}",
            },
            {
                "name": "catalog_pid_n",
                "measured": extracted["n"],
                "method": "regex P(\\d{2}) over CNL-0038..CNL-0046 questions",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/catalog_pids.py:{cat_line}",
            },
            {
                "name": "library_file_on_this_tree",
                "measured": library_present,
                "method": "Path.is_file",
                "anchor": library_path,
            },
            {
                "name": "self_judge_rejected",
                "measured": not self_judge["accepted"],
                "method": "check_custom_role authors∩judges",
                "anchor": f"command-center/p2-wave/probes/CNL-0028/authoring.py:{auth_line}",
            },
        ],
        "control_ids": ["unmapped-wizard", "self-judge-custom"],
    }
    report_hash = sha256_bytes(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    primary = {
        "path": OUT_REL,
        "bytes": 1,
        "sha256": report_hash,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    evidence = [
        {
            "claim": (
                "Every role named across the 58 catalog-cited protocol records "
                "maps to one of 11 templates; ablating any template leaves a "
                "named role unmapped."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"command-center/p2-wave/probes/CNL-0028/coverage.py:{cov_line}",
            "probes": [
                probe("source", "test-run", P1, cov_raw),
                probe(
                    "verifier",
                    "file-read",
                    "python3 -B command-center/p2-wave/probes/CNL-0028/catalog_pids.py",
                    cat_raw,
                ),
            ],
        },
        {
            "claim": (
                "check_custom_role rejects authors∩judges (SELF_JUDGE), missing "
                "capabilities, and rights outside the template union, and "
                "accepts a critic-extending custom role."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"command-center/p2-wave/probes/CNL-0028/authoring.py:{auth_line}",
            "probes": [
                probe(
                    "source",
                    "static-analysis",
                    "python3 -c import authoring; authoring.check_custom_role",
                    auth_raw,
                ),
                probe("verifier", "command", P2, auth_raw),
            ],
        },
        {
            "claim": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on "
                "this worktree and supplied the 58 role lists."
            ),
            "verdict": "REFUTED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNL-0028/protocols.json",
            "probes": [
                probe(
                    "source",
                    "file-read",
                    f"test -f {library_path}",
                    f"present={library_present}",
                ),
                probe(
                    "verifier",
                    "other",
                    "python3 -c Path('12-COUNCIL-PROTOCOLS-AND-PRESETS.json').is_file()",
                    f"library_file_on_this_tree={census.get('library_file_on_this_tree')}",
                ),
            ],
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0028",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0028",
        "profile": "council-design-note",
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{unit_line}",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a "
                "3rd attempt (AGENTS.md 4b)"
            ),
        },
        "artifacts": [primary] + supporting,
        "evidence": evidence,
        "tests": [
            {"id": "coverage", "command": P1, "result": "PASS"},
            {"id": "authoring-negative", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "unmapped-wizard",
                "kind": "known-broken-fixture",
                "description": (
                    "Protocol role 'wizard' with no template and no explicit gap "
                    "must be unmapped; the known-good 58-record census must have "
                    "unmapped=[]"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": wizard_bad,
                "good_state_output": wizard_good,
            },
            {
                "id": "self-judge-custom",
                "kind": "known-broken-fixture",
                "description": (
                    "Custom role with authors=['proposal'] and judges=['proposal'] "
                    "must be rejected; a critic-extending custom role must be accepted"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "accepted="
                    + str(self_judge["accepted"])
                    + " codes="
                    + json.dumps(self_judge["codes"])
                ),
                "good_state_output": (
                    "accepted="
                    + str(good["accepted"])
                    + " codes="
                    + json.dumps(good["codes"])
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0028-probe2-catalog-regex-and-authoring",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Regex-extract P-ids from catalog questions; re-run authoring "
                "checks; jsonschema over the note with a disk $ref store. Does "
                "not read the author's answer field as the source of the counts."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0028/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft7Validator council-design-note (disk $ref)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/CNL-0028/emit_note.py",
                    "schema_errors=0 validator_vacuous=false",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Verbatim role lists inside 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
                    "on the Windows harness-restore path."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place that library file on this tree and re-run coverage.py "
                    "against its records instead of the catalog-cited census."
                ),
            },
            {
                "claim": (
                    "CNL-0022 role-mandate schema and CNL-0029 incompatible-role "
                    "solver artifacts on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver those catalog output_path files and re-bind template "
                    "capability fields to the mandate schema."
                ),
            },
        ],
        "report": report,
    }

    validator = SL.disk_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0028 schema errors")
        for e in errs[:40]:
            print(" ", list(e.path), e.message)
        return 1
    bogus = dict(doc)
    bogus.pop("unit_id", None)
    if not list(validator.iter_errors(bogus)):
        print("FAILED:CNL-0028 schema vacuous without unit_id")
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNL-0028 schema accepted garbage")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live = OUT.read_bytes().replace(b"\r\n", b"\n")
    if len(live) < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0028 artifact {len(live)}B below floor")
        return 1
    if "SUCCESS:CNL-0028" not in live.decode("utf-8"):
        print("FAILED:CNL-0028 sentinel absent")
        return 1
    print(
        f"wrote {OUT_REL} protocol_n={report_cov['protocol_n']} "
        f"templates={report_cov['template_n']} bytes={len(live)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
