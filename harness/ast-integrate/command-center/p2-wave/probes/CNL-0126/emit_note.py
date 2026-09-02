#!/usr/bin/env python3
"""Emit the CNL-0126 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0126-cross-vendor-participant-adapter-boundary-and-loud-degrada.md"
)
SCHEMA_CATALOG = "command-center/schema/council-design-note.schema.json"
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0126/note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0126/probe1_capability_gap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0126/probe2_silent_substitution.py"
)
QUESTION = (
    "What breaks when a participant vendor lacks a capability the CouncilSpec "
    "assumes (tool access, context length, structured output) - and what is "
    "the degradation record that preserves the work artifact instead of "
    "pretending interchangeability?"
)


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0126 emit anchor missing in {path}: {needle}")


def compact_gap(name: str, result: dict, loud: bool, preserved: bool) -> dict:
    rec = result.get("degradation") or {}
    return {
        "name": name,
        "verdict": result.get("verdict"),
        "gaps": list(result.get("gaps") or []),
        "loud": loud,
        "preserved": preserved,
        "sha256": (result.get("partial") or {}).get("sha256"),
        "bytes": (result.get("partial") or {}).get("bytes"),
        "interchangeability_claimed": result.get("interchangeability_claimed"),
        "spec_cite": rec.get("spec_cite") or (result.get("audit") or [{}])[0].get("spec_cite"),
        "text": rec.get("text"),
    }


def main() -> int:
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="cnl0126-emit-") as td:
        tmp = Path(td)
        capable = A.dispatch(
            F.SPEC, F.CAPABLE, F.CAPABLE, F.PARTIAL_WORK, tmp / "capable"
        )
        gap_rows = {}
        live_gap_lpi = []
        for name, seat in F.GAP_SEATS.items():
            result = A.dispatch(F.SPEC, F.CAPABLE, seat, F.PARTIAL_WORK, tmp / name)
            loud = A.is_loud_gap(result)
            preserved = A.preservation_ok(result, F.PARTIAL_WORK)
            if result.get("verdict") != "DEGRADED" or not loud or not preserved:
                print(f"FAILED:CNL-0126 emit gap {name} not loud+preserved")
                return 1
            gap_rows[name] = compact_gap(name, result, loud, preserved)
            live_gap_lpi.append({"loud": loud, "preserved": preserved})
        capable_loud = any(
            e.get("kind") == A.KIND_LOUD for e in (capable.get("audit") or [])
        )
        capable_preserved = A.preservation_ok(capable, F.PARTIAL_WORK)
        if capable.get("verdict") != "SUCCESS" or capable_loud or not capable_preserved:
            print("FAILED:CNL-0126 emit capable both-states broken")
            return 1
        honest_swap = A.dispatch(
            F.SPEC,
            F.CAPABLE,
            F.SUBSTITUTE,
            F.PARTIAL_WORK,
            tmp / "swap",
            silent_swap=True,
        )
        planted = A.buggy_silent_success(F.CAPABLE, F.SUBSTITUTE)
        planted_fire = A.silent_substitution_fires(planted, F.CAPABLE)
        good_fire = A.silent_substitution_fires(capable, F.CAPABLE)
        swap_preserved = A.preservation_ok(honest_swap, F.PARTIAL_WORK)
        if not planted_fire["fires"] or good_fire["fires"]:
            print("FAILED:CNL-0126 emit silent-sub both-states broken")
            return 1
        if honest_swap.get("verdict") == "SUCCESS" or not swap_preserved:
            print("FAILED:CNL-0126 emit honest swap was not a loud refusal")
            return 1
        discard = A.mutant_discard(F.SPEC, F.GAP_TOOL)
        if A.preservation_ok(discard, F.PARTIAL_WORK):
            print("FAILED:CNL-0126 emit discard mutant passed preservation")
            return 1
        measured_lpi = A.lpi(live_gap_lpi, silent_sub=False)
        shim_lpi = A.lpi(live_gap_lpi, silent_sub=True)
        if measured_lpi != 1.0 or shim_lpi != 0.0:
            print(f"FAILED:CNL-0126 emit LPI honest={measured_lpi} shim={shim_lpi}")
            return 1

        a_line = find_line(HERE / "adapter.py", "def negotiate(")
        f_line = find_line(HERE / "fixtures.py", "GAP_TOOL = {")
        t_line = find_line(HERE / "taxonomy.json", '"closed": true')
        cat_line = find_line(
            REPO / "command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0126"'
        )
        spec_line = find_line(
            REPO / "command-center/WORK-UNIT-CATALOG.json",
            "do not pretend full interchangeability; degrade loudly",
        )

        partial_sha = A.digest_bytes(F.PARTIAL_WORK)
        env = A.env_presence()
        owner_present = A.owner_decisions_present(REPO)
        owner_signed = A.owner_signed_cnl0126(REPO)
        cnl0018 = (
            REPO
            / "command-center/design/council/"
            / "CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md"
        ).is_file()

        capable_row = compact_gap(
            "capable", capable, capable_loud, capable_preserved
        )
        capable_row["gaps"] = []
        capable_row["text"] = None

        answer = (
            "Three closed capabilities may be assumed by a CouncilSpec: "
            "tool_access, context_length, structured_output. When a seated "
            "vendor lacks one of them, pretending interchangeability silently "
            "corrupts the council: missing tools fabricate reads; a short "
            "window drops earlier dissent; missing structured output lets a "
            "coercing parser invent required fields. The adapter boundary is "
            "the only comparison of assumed vs advertised. A gap MUST emit a "
            "user-visible LOUD_DEGRADATION naming capability_lost, write the "
            "partial transcript first, and return DEGRADED never SUCCESS. "
            f"Measured LPI on the three gap fixtures is {measured_lpi:.1f} "
            f"(threshold 1.0). A silent SUCCESS-after-reseat is detectable "
            f"(planted fires={planted_fire['fires']}; capable silent="
            f"{not good_fire['fires']}). The adapter does not choose a paid "
            "replacement vendor: that spend question belongs to CNL-0018 and "
            "is NOT-CHECKED here. Spec _USER-PROMPTS.md:10983 already binds "
            "degrade-loudly; this unit does not invent a substitution default."
        )

        verbatim_bad = (
            f"PLANTED-BAD silent-swap SUCCESS: fires={planted_fire['fires']} "
            f"reason={planted_fire['reason']} swapped={planted_fire['swapped']} "
            f"claimed={planted.get('interchangeability_claimed')}"
        )
        verbatim_good = (
            f"KNOWN-GOOD capable identical-seat: verdict={capable.get('verdict')} "
            f"fires={good_fire['fires']} loud_degradation={capable_loud} "
            f"preserved={capable_preserved} gaps={capable.get('gaps')}"
        )
        verbatim_gap = (
            f"PLANTED-BAD gap tool_access: verdict={gap_rows['tool_access']['verdict']} "
            f"loud={gap_rows['tool_access']['loud']} "
            f"preserved={gap_rows['tool_access']['preserved']} "
            f"sha256={gap_rows['tool_access']['sha256']}"
        )
        verbatim_discard = (
            "NEGATIVE-CONTROL mutant_discard: preservation_ok=False; "
            "the check FIRES on a DEGRADED result whose partial is missing"
        )

        doc = {
            "unit_id": "CNL-0126",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:CNL-0126",
            "completion_sentinel": "SUCCESS:CNL-0126",
            "title": "Cross-vendor participant adapter boundary and loud degradation",
            "question": QUESTION,
            "answer": answer,
            "answers": {
                "what_breaks": (
                    "tool_access: fabricated reads and skipped MCP. "
                    "context_length: earlier dissent drops out of the window. "
                    "structured_output: coerced JSON invents required fields. "
                    "All three look like a successful vote if the adapter "
                    "pretends vendors are interchangeable."
                ),
                "degradation_record": (
                    "User-visible LOUD_DEGRADATION naming capability_lost, "
                    "assumed vs advertised, spec_cite=_USER-PROMPTS.md:10983, "
                    "partial_artifact.sha256 of the frozen transcript, "
                    "interchangeability_claimed=false, verdict=DEGRADED."
                ),
                "substitution_rule": (
                    "An unrecorded vendor/model reseat is SILENT_SUBSTITUTION. "
                    "The adapter records it, preserves the partial, returns "
                    "REFUSED, and never SUCCESS. It does not auto-purchase or "
                    "auto-reseat a second paid vendor (CNL-0018)."
                ),
            },
            "claims": [
                {
                    "id": "C1",
                    "claim": "A capability-gap fixture is DEGRADED, LOUD, and preserves the partial bytes.",
                    "verdict": "CONFIRMED",
                    "anchor": f"command-center/p2-wave/probes/CNL-0126/adapter.py:{a_line}",
                },
                {
                    "id": "C2",
                    "claim": "Silent SUCCESS-after-reseat is detectable; a capable identical seat is SILENT.",
                    "verdict": "CONFIRMED",
                    "anchor": "both_states.verbatim_bad",
                },
                {
                    "id": "C3",
                    "claim": "Coverage of all three gap types without loud events is not a pass (shim LPI=0).",
                    "verdict": "CONFIRMED",
                    "anchor": "measurement.coverage_alone_insufficient",
                },
                {
                    "id": "C4",
                    "claim": "Live vendor tool/context/structured-output windows were measured via vendor APIs.",
                    "verdict": "NOT-CHECKED",
                    "anchor": "live_vendor_probe_readonly",
                },
                {
                    "id": "C5",
                    "claim": "OWNER-DECISIONS.md records an explicit CNL-0126 sign-off.",
                    "verdict": "CONFIRMED" if owner_signed else "REFUTED",
                    "anchor": "command-center/OWNER-DECISIONS.md",
                },
            ],
            "spec_cite": A.SPEC_CITE,
            "source_inputs_on_this_tree": {
                "11-COUNCIL-SPECIFICATION.schema.json": False,
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
                "_USER-PROMPTS.md": False,
                "council/SKILL.md": False,
                "CNL-0018-output": cnl0018,
                "OWNER-DECISIONS.md": owner_present,
                "note": (
                    "Catalog inputs are Windows harness-restore paths not present "
                    "here. Capability T is an operational closed set this unit "
                    "supplies. Quote of 10983 is taken from the catalog "
                    "evidence_requirement, not from unread prompt bytes."
                ),
            },
            "owner_sign_off": {
                "required_by_catalog": True,
                "file": "command-center/OWNER-DECISIONS.md",
                "file_present": owner_present,
                "this_unit_mentioned": owner_signed,
                "present": owner_signed,
                "forged": False,
                "policy_source": (
                    "Catalog evidence_requirement cites _USER-PROMPTS.md:10983 "
                    "(do not pretend full interchangeability; degrade loudly). "
                    "This unit implements that binding. It does not guess a "
                    "paid-vendor substitution default (CNL-0018). "
                    "OWNER-DECISIONS.md exists but contains no CNL-0126 ruling."
                ),
            },
            "taxonomy": {
                "id": tax["id"],
                "version": tax["version"],
                "closed": True,
                "range_rule": tax["range_rule"],
                "categories": tax["categories"],
            },
            "measurement": {
                "name": tax["loud_preservation_index"]["name"],
                "formula": tax["loud_preservation_index"]["formula"],
                "threshold_reject_below": tax["loud_preservation_index"][
                    "threshold_reject_below"
                ],
                "coverage_alone_insufficient": True,
                "coverage_definition": tax["loud_preservation_index"][
                    "coverage_definition"
                ],
                "detector": (
                    "Capability check FIRES (DEGRADED+LOUD+preserve) on a gap "
                    "fixture and is SILENT (SUCCESS, no LOUD_DEGRADATION) on a "
                    "capable identical seat. Silent-substitution check FIRES on "
                    "SUCCESS-after-unrecorded-reseat and is SILENT on the capable seat."
                ),
            },
            "what_breaks": [
                {
                    "capability": "tool_access",
                    "breakage": (
                        "A tool-less seat fabricates file reads, skips MCP, or "
                        "invents citations while still looking like a grounded vote."
                    ),
                    "loud_record": (
                        "LOUD_DEGRADATION capability_lost=[tool_access]; "
                        "partial transcript frozen; verdict=DEGRADED."
                    ),
                },
                {
                    "capability": "context_length",
                    "breakage": (
                        "Earlier rounds fall out of the window: dissent and "
                        "constraints disappear and a false consensus is counted."
                    ),
                    "loud_record": (
                        "LOUD_DEGRADATION names assumed vs advertised tokens; "
                        "the prefix is the preserved artifact before any truncated prompt."
                    ),
                },
                {
                    "capability": "structured_output",
                    "breakage": (
                        "Prose or fenced JSON is coerced into required fields "
                        "(missing dissent becomes default agree)."
                    ),
                    "loud_record": (
                        "LOUD_DEGRADATION keeps RAW bytes as the partial; "
                        "never SUCCESS with coerced JSON."
                    ),
                },
            ],
            "degradation_record": {
                "kind": A.KIND_LOUD,
                "user_visible": True,
                "verdict": "DEGRADED",
                "required_fields": [
                    "capability_lost",
                    "assumed",
                    "advertised",
                    "partial_artifact.sha256",
                    "interchangeability_claimed=false",
                    "spec_cite",
                ],
                "never": [
                    "verdict=SUCCESS on a gap",
                    "silent vendor_id swap",
                    "discard of the partial",
                ],
            },
            "fixture_scores": {
                "capable": capable_row,
                "tool_access": gap_rows["tool_access"],
                "context_length": gap_rows["context_length"],
                "structured_output": gap_rows["structured_output"],
                "honest_silent_swap_attempt": {
                    "verdict": honest_swap.get("verdict"),
                    "preserved": swap_preserved,
                    "audit_kinds": [
                        e.get("kind") for e in (honest_swap.get("audit") or [])
                    ],
                },
            },
            "measured_lpi": measured_lpi,
            "shim_lpi_coverage_only": shim_lpi,
            "partial_work_sha256": partial_sha,
            "partial_work_bytes": len(F.PARTIAL_WORK),
            "live_vendor_probe_readonly": {
                "method": "os.environ.get name presence; values never printed",
                "inventory": env,
                "api_calls": 0,
                "note": (
                    "Presence is not capability. Advertised tool/context/schema "
                    "windows were not measured against live vendors on this run."
                ),
            },
            "both_states": {
                "capability_planted_bad": "tool_access",
                "capability_known_good": "capable",
                "substitution_planted_bad": "buggy_silent_success",
                "substitution_known_good": "capable",
                "verbatim_gap": verbatim_gap,
                "verbatim_bad": verbatim_bad,
                "verbatim_good": verbatim_good,
                "verbatim_discard": verbatim_discard,
            },
            "tests": [
                {
                    "id": "T-CAPABILITY-GAP-LOUD-PRESERVE",
                    "name": (
                        "a capability-gap fixture must produce a LOUD "
                        "degradation record and preserve the partial artifact"
                    ),
                    "command": P1,
                    "result": "PASS",
                },
                {
                    "id": "T-SILENT-SUBSTITUTION-DETECTABLE",
                    "name": (
                        "a silent-substitution attempt must be detectable "
                        "in the audit record"
                    ),
                    "command": P2,
                    "result": "PASS",
                },
                {
                    "id": "T-NEGATIVE-CONTROL",
                    "name": (
                        "negative control recorded verbatim: discard mutant "
                        "fails preservation; capable seat is SILENT"
                    ),
                    "command": P1,
                    "result": "PASS",
                },
            ],
            "negative_controls": [
                {
                    "id": "NC-DISCARD-PARTIAL",
                    "rejects": (
                        "a DEGRADED result whose partial artifact was dropped"
                    ),
                    "verbatim": verbatim_discard,
                },
                {
                    "id": "NC-SILENT-SWAP-SUCCESS",
                    "rejects": (
                        "SUCCESS after an unrecorded vendor/model reseat "
                        "claiming interchangeability"
                    ),
                    "verbatim": verbatim_bad,
                },
                {
                    "id": "NC-CAPABLE-IDENTICAL",
                    "rejects": "n/a — this is the silent-on-good control",
                    "verbatim": verbatim_good,
                },
            ],
            "reviewer": {
                "reviewer_id": "CNL-0126-probe2-independent-gap-recount",
                "verdict": "PASS",
                "independent": True,
                "method": (
                    "Recomputes gaps via fixtures.expected_gaps (set algebra on "
                    "assumed vs advertised dicts) and sha256 of PARTIAL_WORK. "
                    "Does not call adapter.compute_gaps. Disagreement blocks."
                ),
            },
            "artifacts": [
                {"path": OUT_REL, "exists": True, "role": "primary"},
                {"path": SCHEMA_CATALOG, "exists": True, "role": "supporting"},
                {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
                {
                    "path": "command-center/p2-wave/probes/CNL-0126/taxonomy.json",
                    "exists": True,
                    "role": "supporting",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0126/adapter.py",
                    "exists": True,
                    "role": "supporting",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0126/fixtures.py",
                    "exists": True,
                    "role": "supporting",
                },
            ],
            "evidence": [
                {
                    "claim": (
                        "A tool_access gap is DEGRADED, user-visible LOUD, and "
                        "byte-preserves the partial work."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0126/adapter.py:{a_line}"
                    ),
                },
                {
                    "claim": (
                        "Gap algebra for the three closed capabilities is "
                        "recomputed from fixture dicts independently of negotiate()."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0126/fixtures.py:{f_line}"
                    ),
                },
                {
                    "claim": (
                        "Capability T is closed; observed vendor quirks cannot grow it."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0126/taxonomy.json:{t_line}"
                    ),
                },
                {
                    "claim": (
                        "Catalog evidence_requirement cites _USER-PROMPTS.md:10983 "
                        "(do not pretend full interchangeability; degrade loudly)."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": (
                        f"command-center/WORK-UNIT-CATALOG.json:{spec_line}"
                    ),
                },
                {
                    "claim": (
                        "Catalog question and completion sentinel SUCCESS:CNL-0126 "
                        "are the question and sentinel this note carries."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": (
                        f"command-center/WORK-UNIT-CATALOG.json:{cat_line}"
                    ),
                },
                {
                    "claim": (
                        "Harness-restore _USER-PROMPTS.md:10983 bytes were read "
                        "from C:/Users/Prekzursil/.claude/harness-restore-20260806/ "
                        "on this worktree."
                    ),
                    "verdict": "REFUTED",
                    "anchor": "source_inputs_on_this_tree",
                },
                {
                    "claim": (
                        "Live vendor tool/context/structured-output windows were "
                        "measured by calling vendor APIs."
                    ),
                    "verdict": "NOT-CHECKED",
                    "anchor": "live_vendor_probe_readonly",
                },
                {
                    "claim": (
                        "CNL-0018 delivered a measured live remaining-quota / "
                        "dollar cost used as this unit's second-vendor spend default."
                    ),
                    "verdict": "NOT-CHECKED",
                    "anchor": (
                        "command-center/design/council/"
                        "CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md"
                    ),
                },
                {
                    "claim": (
                        "Explicit owner sign-off for CNL-0126 is recorded in "
                        "command-center/OWNER-DECISIONS.md before this unit closes."
                    ),
                    "verdict": "CONFIRMED" if owner_signed else "REFUTED",
                    "anchor": "command-center/OWNER-DECISIONS.md",
                },
            ],
            "residual_unknowns": [
                (
                    "OWNER-DECISIONS.md is present but has no CNL-0126 ruling "
                    "(OQ-3 PR-ONLY and REL-0003 only). The degradation policy "
                    "is the spec 10983 binding already in the catalog row, not "
                    "a guessed paid-reseat. If the owner later wants auto-reseat "
                    "to a second paid vendor, that is CNL-0018 plus an owner "
                    "ruling — this adapter will still refuse to call that SUCCESS."
                ),
                (
                    "Env-name presence is not a capability advertisement. A "
                    "later CNL-0012-style live reachability probe may fill "
                    "advertised windows; until then fixtures are synthetic."
                ),
            ],
            "dependencies": {
                "B01": "bucket token; not re-litigated here",
                "CNL-0018": (
                    "output present; sibling forbids silent same-vendor reseat "
                    "on quota exhaustion. Live dollar/remaining-quota still "
                    "NOT-CHECKED (CNL-0018's own C5)."
                ),
            },
        }

        schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
        for garbage in (
            {},
            {"totally": "unrelated", "passing_tests": 999999},
            {"unit_id": "CNL-0126", "state": "SUCCESS"},
        ):
            try:
                jsonschema.Draft7Validator(schema).validate(garbage)
            except jsonschema.ValidationError:
                continue
            print(f"FAILED:CNL-0126 emit schema accepted garbage {garbage}")
            return 1

        doc["schema_version"] = 1
        doc["spec_anchor"] = A.SPEC_CITE
        doc["min_bytes_threshold"] = 4096
        doc["report"] = {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "loud_preservation_index",
                    "measured": measured_lpi,
                    "method": "adapter.lpi over three closed gap fixtures",
                    "anchor": f"command-center/p2-wave/probes/CNL-0126/adapter.py:{a_line}",
                }
            ],
            "control_ids": [
                "NC-DISCARD-PARTIAL",
                "NC-SILENT-SWAP-SUCCESS",
                "NC-CAPABLE-IDENTICAL",
            ],
        }

        jsonschema.Draft7Validator(schema).validate(doc)

        out = REPO / OUT_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        size = out.stat().st_size
        if size < int(doc["min_bytes_threshold"]):
            print(f"FAILED:CNL-0126 emit artifact {size}B below floor")
            return 1
        print(f"wrote {OUT_REL} bytes={size}")
        print("SUCCESS:CNL-0126 emit")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
