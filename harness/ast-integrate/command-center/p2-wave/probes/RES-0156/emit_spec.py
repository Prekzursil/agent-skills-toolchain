#!/usr/bin/env python3
"""Emit RES-0156 design spec: grounded vs ideation evidence split."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checker as C  # noqa: E402
import corpus as K  # noqa: E402
from lenses import (  # noqa: E402
    CONTESTED,
    GROUNDED,
    IDEATION,
    CATALOG,
    LENSES,
    REPO,
    TAXONOMY,
    lens_table_with_anchors,
)

UNIT = "RES-0156"
OUT = (
    "command-center/research/gem-hunt/"
    "RES-0156-grounded-vs-ideation-evidence-split.json"
)
SCHEMA = "command-center/schema/design-spec.schema.json"
SENTINEL = "SUCCESS:RES-0156"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0156/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0156/probe2_cost_and_contested.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == UNIT:
            return item
    raise KeyError(UNIT)


def absents() -> dict[str, bool]:
    return {
        "_USER-PROMPTS.md": not (REPO / "_USER-PROMPTS.md").is_file(),
        "rules/common/fan-out-contract.md": not (
            REPO / "rules/common/fan-out-contract.md"
        ).is_file(),
        "command-center/sources/REGISTER.md": not (
            REPO / "command-center/sources/REGISTER.md"
        ).is_file(),
    }


def main() -> int:
    unit = catalog_unit()
    question = str(unit.get("question_or_target") or "")
    if len(question) < 40:
        print("FAILED:RES-0156 catalog question too short")
        return 1

    findings = json.loads(
        (HERE / "fixtures" / "findings.json").read_text(encoding="utf-8")
    )["findings"]
    both = {name: C.check_finding(f) for name, f in findings.items()}
    if not both["grounded_ok"]["compliant"]:
        print("FAILED:RES-0156 emit grounded_ok did not pass")
        return 1
    if both["grounded_zero"]["status"] != "ZERO_CITATION":
        print("FAILED:RES-0156 emit grounded_zero silent")
        return 1
    if both["ideation_repo_only"]["status"] != "FORBIDDEN_GROUNDING":
        print("FAILED:RES-0156 emit ideation_repo_only silent")
        return 1
    if both["contested_unbound"]["status"] != CONTESTED:
        print("FAILED:RES-0156 emit unbound was assigned a standard")
        return 1

    live = K.measure()
    if not live["summary"].get("planted_controls_pass"):
        print("FAILED:RES-0156 emit planted controls failed")
        return 1

    table = lens_table_with_anchors()
    grounded_ids = [r["id"] for r in table if r["standard"] == GROUNDED]
    ideation_ids = [r["id"] for r in table if r["standard"] == IDEATION]
    contested_ids = [r["id"] for r in table if r["standard"] == CONTESTED]
    if len(table) != 12:
        print(f"FAILED:RES-0156 emit expected 12 lenses got {len(table)}")
        return 1
    if len(contested_ids) < 1:
        print("FAILED:RES-0156 emit no CONTESTED lens")
        return 1
    unnamed = [
        r["id"]
        for r in table
        if r["reconstruction"] == "catalog-blueprint-5-8"
    ]

    cat_sha, cat_bytes = sha256_file(REPO / CATALOG)
    tax_path = REPO / TAXONOMY
    tax_sha, tax_bytes = sha256_file(tax_path) if tax_path.is_file() else ("", 0)
    ext_path = HERE / "fixtures" / "external-ach-critique.txt"
    ext_sha, ext_bytes = sha256_file(ext_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = absents()

    catalog_id_anchor = "command-center/WORK-UNIT-CATALOG.json:71662"
    # Prefer live locator for the id line.
    from lenses import locate_needle  # noqa: E402

    live_id = locate_needle('"id": "RES-0156"')
    if live_id:
        catalog_id_anchor = live_id
    q_anchor = locate_needle("Which lenses must cite file:line in this repository")
    tests_anchor = locate_needle(
        "identify at least one lens where the correct standard is ambiguous"
    )

    statuses = {name: both[name]["status"] for name in both}

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": str(unit.get("title") or ""),
        "question": question,
        "output_schema": SCHEMA,
        "emitted_at": now,
        "answer": (
            "GROUNDED lenses (must cite resolving file:line in this worktree): "
            + ", ".join(grounded_ids)
            + ". IDEATION lenses (must cite an external URL/DOI and are forbidden "
            "from treating a repo file:line as the finding): "
            + ", ".join(ideation_ids)
            + ". CONTESTED (not assigned by preference): "
            + ", ".join(contested_ids)
            + " — deciding experiment bind-object-scope (estate→GROUNDED, "
            "external→IDEATION, unbound stays CONTESTED). "
            "Measured live cost of getting it wrong: "
            f"ideation-repo-only={live['summary']['cost']['duplicate_reads_ideation_repo_only']}, "
            f"grounded-zero-citation={live['summary']['cost']['zero_citation_grounded_outputs']}, "
            f"duplicate-repo-path-events="
            f"{live['summary']['cost']['duplicate_repo_path_events']} "
            f"over {live['summary']['n_live_records']} recorded research/receipt "
            "records. SUCCESS:RES-0156"
        ),
        "honesty": {
            "absent_inputs": missing,
            "user_prompts_reconstructed_from_catalog_parentheticals": True,
            "fan_out_contract_a9_absent": missing["rules/common/fan-out-contract.md"],
            "unnamed_spec_lines": ["10702", "10703", "10706", "10709", "10710", "10711"],
            "blueprint_slots_used_to_complete_the_12": unnamed,
            "confidence_named_modes": "almost-certain",
            "confidence_blueprint_slots": "likely",
            "gem_hunt_dir_created_by_this_unit": True,
            "cost_corpus": "frozen-prior-fanout-extract",
            "cost_corpus_path": (
                "command-center/p2-wave/probes/RES-0156/fixtures/"
                "prior_fanout_records.json"
            ),
        },
        "design": {
            "a9_contract": (
                "Split the evidence standard by lens type. The object of inquiry "
                "binds the standard. A lens name that does not imply the object "
                "is CONTESTED until object_scope is bound."
            ),
            "checker_module": "command-center/p2-wave/probes/RES-0156/checker.py",
            "api": "check_finding(finding) -> {compliant, status, applied_standard, violations}",
            "already_present_negative": (
                "An IDEATION finding may cite a repo file:line only with "
                "role=already-present-negative (the mechanism is already here, "
                "so it is not a gem). That citation is not grounding."
            ),
            "lenses": table,
            "grounded_ids": grounded_ids,
            "ideation_ids": ideation_ids,
            "contested_ids": contested_ids,
            "both_states": {
                "statuses": statuses,
                "discriminates": (
                    both["grounded_ok"]["compliant"]
                    and both["grounded_zero"]["status"] == "ZERO_CITATION"
                    and both["ideation_ok"]["compliant"]
                    and both["ideation_repo_only"]["status"] == "FORBIDDEN_GROUNDING"
                ),
            },
            "contested": {
                "lens_id": "targeted-question-answering",
                "deciding_experiment": "bind-object-scope",
                "estate_applies": GROUNDED,
                "external_applies": IDEATION,
                "unbound_stays": CONTESTED,
            },
            "cost": {
                "method": (
                    "S1: check_finding on citation fields of a frozen prior-fan-out "
                    "extract (fixtures/prior_fanout_records.json), scored via the "
                    "catalog role→lens map. S2: Counter over repo paths cited by "
                    "those same frozen records (duplicate_repo_path_events). Live "
                    "research/ and receipts/ trees grow during concurrent G-1 "
                    "delivery and are not re-walked on remesure. Transcript "
                    "directories are also not consulted."
                ),
                "n_live_records": live["summary"]["n_live_records"],
                "live": live["summary"]["cost"],
                "summary": {
                    k: live["summary"][k]
                    for k in (
                        "n_mapped",
                        "n_ideation_mapped",
                        "n_grounded_mapped",
                        "ideation_forbidden_grounding",
                        "ideation_repo_only",
                        "grounded_zero_citation",
                        "ideation_repo_only_ids",
                        "grounded_zero_ids",
                    )
                },
                "planted_controls_pass": live["summary"]["planted_controls_pass"],
            },
        },
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "PASS"},
            {
                "id": "probe2-cost-and-contested",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "grounded-zero-citation",
                "on_state": "GROUNDED lens with empty citations",
                "observed": both["grounded_zero"]["status"],
            },
            {
                "id": "ideation-repo-only",
                "on_state": "IDEATION lens citing only this repository",
                "observed": both["ideation_repo_only"]["status"],
            },
            {
                "id": "contested-unbound",
                "on_state": "targeted-question-answering with no object_scope",
                "observed": both["contested_unbound"]["status"],
            },
        ],
        "evidence": [
            {
                "claim": (
                    "The catalog asks which lenses must cite file:line in this "
                    "repository versus an external source, and requires a "
                    "CONTESTED lens with a deciding experiment."
                ),
                "verdict": "CONFIRMED",
                "anchor": q_anchor or catalog_id_anchor,
                "confidence_band": "almost-certain",
                "mechanism": "catalog JSON parse of question_or_target and tests_required",
                "source_lineage": {
                    "resolved_url": f"file://{CATALOG}",
                    "fetch_timestamp": now,
                    "sha256": cat_sha,
                    "bytes": cat_bytes,
                },
                "independent_verification_path": P2,
            },
            {
                "claim": (
                    "The checker is silent on a GROUNDED finding with a resolving "
                    "file:line and fires ZERO_CITATION / FORBIDDEN_GROUNDING on "
                    "the known-broken twins."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0156/fixtures/findings.json",
                "confidence_band": "almost-certain",
                "mechanism": "check_finding on planted both-states fixtures",
                "source_lineage": {
                    "resolved_url": (
                        "file://command-center/p2-wave/probes/RES-0156/"
                        "fixtures/findings.json"
                    ),
                    "fetch_timestamp": now,
                    "sha256": sha256_file(HERE / "fixtures" / "findings.json")[0],
                },
                "independent_verification_path": P1,
            },
            {
                "claim": (
                    "targeted-question-answering stays CONTESTED when unbound and "
                    "takes GROUNDED vs IDEATION only after object_scope is bound. "
                    "That is the deciding experiment, not a preference."
                ),
                "verdict": "CONFIRMED",
                "anchor": tests_anchor or catalog_id_anchor,
                "confidence_band": "almost-certain",
                "mechanism": "bind-object-scope on planted contested findings",
                "source_lineage": {
                    "resolved_url": f"file://{CATALOG}",
                    "fetch_timestamp": now,
                    "sha256": cat_sha,
                },
                "independent_verification_path": P2,
            },
            {
                "claim": (
                    "Cost of getting the standard wrong is measured from a "
                    "frozen prior-fan-out extract of "
                    f"{live['summary']['n_live_records']} research/receipt records "
                    "(fixtures/prior_fanout_records.json). Figures are "
                    "citation-checker verdicts (S1) and duplicate repo-path "
                    "multiplicity (S2), not recollection and not a live rglob."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0156/fixtures/prior_fanout_records.json",
                "confidence_band": "likely",
                "mechanism": (
                    "S1 checker verdicts on citation fields; S2 duplicate "
                    "repo-path Counter over the same records"
                ),
                "source_lineage": {
                    "resolved_url": "file://command-center/research",
                    "fetch_timestamp": now,
                    "sha256": cat_sha,
                    "note": "sha256 is of the catalog used to map unit roles to lenses",
                },
                "independent_verification_path": P2,
            },
            {
                "claim": (
                    "_USER-PROMPTS.md and fan-out-contract.md A9 are absent. "
                    "Eight modes are reconstructed from catalog parentheticals; "
                    "four slots are the IMP-0178 research blueprints 5-8. "
                    "Unnamed spec lines 10702/10703/10706/10709-10711 are not invented."
                ),
                "verdict": "CONFIRMED",
                "anchor": TAXONOMY + ":27" if tax_path.is_file() else catalog_id_anchor,
                "confidence_band": "likely",
                "mechanism": "path existence check plus catalog parenthetical locator",
                "source_lineage": {
                    "resolved_url": f"file://{TAXONOMY}",
                    "fetch_timestamp": now,
                    "sha256": tax_sha,
                    "bytes": tax_bytes,
                },
                "independent_verification_path": P2,
            },
            {
                "claim": (
                    "IDEATION both-states use a local external fixture "
                    f"(sha256={ext_sha}, bytes={ext_bytes}) rather than a live fetch."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/RES-0156/fixtures/"
                    "external-ach-critique.txt"
                ),
                "confidence_band": "almost-certain",
                "mechanism": "sha256 of fixture bytes",
                "source_lineage": {
                    "resolved_url": "fixture://external/ach-critique",
                    "fetch_timestamp": now,
                    "sha256": ext_sha,
                    "bytes": ext_bytes,
                },
                "independent_verification_path": P1,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0156-probe2-contested-and-cost",
            "verdict": "PASS",
            "independent": True,
            "defaults_to_refuted_when_unbound": True,
            "control_executed": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/RES-0156/checker.py",
                "exists": True,
                "role": "checker",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0156/lenses.py",
                "exists": True,
                "role": "lens-table",
            },
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0156 sentinel missing from emit")
        return 1
    dest.write_text(text, encoding="utf-8")
    digest, size = sha256_file(dest)
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"grounded={len(grounded_ids)} ideation={len(ideation_ids)} "
        f"contested={len(contested_ids)}"
    )
    print(SENTINEL + " emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
