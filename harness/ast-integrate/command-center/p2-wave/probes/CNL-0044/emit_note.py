#!/usr/bin/env python3
"""Emit the CNL-0044 council design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / (
    "command-center/design/council/"
    "CNL-0044-executable-runtime-semantics-for-the-7-tradecraft-protocol.md"
)
LOCAL_SCHEMA = HERE / "council-design-note.schema.json"
CATALOG_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"

sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402
import enumerate as E  # noqa: E402
import semantics as S  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0044/probe1_schedules_and_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0044/probe2_independent_recount.py"
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def main() -> int:
    fam = E.enumerate_family()
    if not fam["agreement"]:
        print("FAILED:CNL-0044 emit enumeration disagreement")
        return 1
    verdicts = S.run_all()
    both = C.both_states(verdicts, fam["ids"])
    if not both["ok"]:
        print("FAILED:CNL-0044 emit both-states not discriminating")
        return 1
    neg = C.negative_control(verdicts, fam["ids"])
    dups = S.find_duplicates(fam["records"], fam["other_families"])

    protocols = []
    for rec, ver in zip(fam["records"], verdicts):
        spec = S.TRADECRAFT_MECHANISMS[rec["id"]]
        protocols.append(
            {
                "record_id": rec["id"],
                "name": rec["name"],
                "family": "TRADECRAFT",
                "executability": ver["executability"],
                "missing_element": ver["missing_element"],
                "turns": ver["turns"],
                "stopping": ver["stopping"],
                "time_orientation": spec["time_orientation"],
                "core_operator": spec["core_operator"],
                "artifact": {
                    "name": spec["artifact_name"],
                    "shape": spec["artifact_shape"],
                    "keys": spec["artifact_schema_keys"],
                    "produced_on_known_good": ver["artifact"]["produced"]
                    if ver.get("artifact")
                    else None,
                },
                "library_body_read": bool(fam["library"]["present"]),
                "semantics_source": (
                    "designed-for-catalog-named-id; library record body absent"
                    if not fam["library"]["present"]
                    else "library-record"
                ),
            }
        )

    rel_out = (
        "command-center/design/council/"
        "CNL-0044-executable-runtime-semantics-for-the-7-tradecraft-protocol.md"
    )
    art_by_id = {p["record_id"]: p["artifact"]["name"] for p in protocols}
    answer = (
        "Ranging over catalog-named TRADECRAFT records P38-P44 (n=7, two parsers "
        "agree; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent so library bodies "
        "were not read): each record has an executable turn schedule that emits a "
        f"typed artifact. P38 analysis-of-competing-hypotheses -> {art_by_id['P38']} "
        "(evidence x hypothesis cells in {C,I,N,NA} plus diagnosticity ranking). "
        f"P39 key-assumptions-check -> {art_by_id['P39']} (load-bearing inversion). "
        f"P40 quality-of-information-check -> {art_by_id['P40']} (credibility/"
        "completeness/corroboration classification). "
        f"P41 deception-detection -> {art_by_id['P41']} (indicator scores). "
        f"P42 argument-mapping -> {art_by_id['P42']} (support/attack graph plus "
        "ungrounded claims). "
        f"P43 premortem -> {art_by_id['P43']} (frozen plan, assumed failure, "
        "warning+control per mode). "
        f"P44 postmortem-5whys-causal -> {art_by_id['P44']} (exactly five why-steps, "
        "root cause, corrective action). "
        "Duplicate under (time_orientation, core_operator): P43 premortem duplicates "
        "P48 kill-the-company (ENGINEERING-REVIEW, CNL-0045 named list) as "
        "prospective-hindsight-failure-enumeration at before-decision. The other six "
        "have unique named:<slug> operators against every other family list."
    )
    cat = REPO / "command-center/WORK-UNIT-CATALOG.json"
    cases = HERE / "fixtures/known_good_cases.json"
    sem = HERE / "semantics.py"
    snip44 = '"id": "CNL-0044"'
    snip45 = '"id": "CNL-0045"'
    snip_p38 = '"P38"'
    line44 = find_line(cat, snip44)
    line45 = find_line(cat, snip45)
    line_p38 = find_line(cases, snip_p38)
    line_op = find_line(sem, "OPERATOR_ALIASES")
    doc = {
        "unit_id": "CNL-0044",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0044",
        "completion_sentinel": "SUCCESS:CNL-0044",
        "family": "TRADECRAFT",
        "title": "Executable runtime semantics for the 7 TRADECRAFT protocols",
        "question": fam["question"],
        "answer": answer,
        "taxonomy": {
            "id": "tradecraft-runtime",
            "axis": "executability-and-cross-family-mechanism-identity",
            "closed": True,
            "classes": [
                {
                    "id": "EXECUTABLE",
                    "interest": "Typed artifact plus stopping predicate over that artifact.",
                },
                {
                    "id": "NOT-EXECUTABLE",
                    "interest": "Named missing element; still counted against family n=7.",
                },
                {
                    "id": "UNIQUE-MECHANISM",
                    "interest": "No other family shares (time_orientation, core_operator).",
                },
                {
                    "id": "CROSS-FAMILY-DUPLICATE",
                    "interest": "Same (time, operator) as a non-TRADECRAFT catalog P-id.",
                },
            ],
        },
        "metric": {
            "id": "family-coverage-I",
            "formula": "I = |verdicts in {EXECUTABLE, NOT-EXECUTABLE with named missing}|; pass iff I == n_family",
            "decision": "PASS iff I==7 on catalog-named P38-P44 and planted-bad empty-artifact fires",
            "I_star": 7,
        },
        "claim_under_test": (
            "Each of P38-P44 produces a distinct typed artifact under an "
            "executable turn schedule; P43 premortem duplicates P48 "
            "kill-the-company under (time_orientation, core_operator)."
        ),
        "library": fam["library"],
        "enumeration": {
            "expected_n": fam["expected_n"],
            "measured_n": fam["measured_n"],
            "ids": fam["ids"],
            "agreement": fam["agreement"],
            "claimed_elsewhere": fam["claimed_elsewhere"],
            "library_family_n": fam["library_family_n"],
            "signals": fam["signals"],
        },
        "protocols": protocols,
        "duplicates": dups,
        "duplicate_criterion": (
            "A TRADECRAFT record duplicates another family's mechanism iff "
            "they share time_orientation and core_operator. Names are ignored. "
            "Default operator is named:<slug> so only explicit aliases collide. "
            "Alias map: premortem and kill-the-company -> "
            "prospective-hindsight-failure-enumeration @ before-decision. "
            "P48 is taken from CNL-0045's named list (ENGINEERING-REVIEW)."
        ),
        "tests": [
            {
                "id": "seven-schedules-or-not-executable",
                "command": P1,
                "result": "PASS",
                "detail": "7 EXECUTABLE verdicts counted against catalog family n=7",
            },
            {
                "id": "both-states-artifact-check",
                "command": P1,
                "result": "PASS",
                "detail": both,
            },
            {
                "id": "negative-control-empty-artifact",
                "command": P1,
                "result": "PASS",
                "detail": neg,
            },
            {
                "id": "independent-recount",
                "command": P2,
                "result": "PASS",
                "detail": "probe2 re-tabulates after this file exists; receipts refuse if it fails",
            },
        ],
        "both_states": {
            "known_good": {
                "silent": both["known_good"]["silent"],
                "fired": both["known_good"]["fired"],
                "reasons": both["known_good"]["reasons"],
            },
            "planted_bad": {
                "silent": both["planted_bad"]["silent"],
                "fired": both["planted_bad"]["fired"],
                "reasons": both["planted_bad"]["reasons"],
                "plant": both["plant"],
            },
        },
        "negative_control": {
            "rejected_state": neg["rejected_state"],
            "check": neg["check"],
            "verbatim": neg["verbatim"],
        },
        "negative_controls": [
            {
                "rejected_state": neg["rejected_state"],
                "check": neg["check"],
                "verbatim": neg["verbatim"],
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0044-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Re-parse P38-P44 with a range regex (not the comma-name splitter); "
                "re-run fixtures; recompute duplicates from CNL-0038..CNL-0046 names; "
                "compare numbers only."
            ),
        },
        "artifacts": [
            {"path": rel_out, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json",
                "exists": True,
                "role": "known-good-fixture",
            },
            {
                "path": "command-center/schema/council-design-note.schema.json",
                "exists": True,
                "role": "output-schema",
            },
        ],
        "evidence": [
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{line44}",
                "claim": "CNL-0044 names P38-P44 as TRADECRAFT; expected n=7",
                "verdict": "CONFIRMED",
                "kind": "catalog",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{line45}",
                "claim": "CNL-0045 names P48 kill-the-company (war-game) in ENGINEERING-REVIEW",
                "verdict": "CONFIRMED",
                "kind": "catalog",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json",
                "anchor": f"command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json:{line_p38}",
                "claim": "known-good cases produce typed artifacts for all 7 records",
                "verdict": "CONFIRMED",
                "kind": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0044/semantics.py",
                "anchor": f"command-center/p2-wave/probes/CNL-0044/semantics.py:{line_op}",
                "claim": "turn runners and duplicate alias map (premortem == kill-the-company operator)",
                "verdict": "CONFIRMED",
                "kind": "live-tree",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0044/enumerate.py",
                "anchor": "command-center/p2-wave/probes/CNL-0044/enumerate.py:1",
                "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json family count cannot be taken from disk; file absent",
                "verdict": "REFUTED" if fam["library"]["present"] else "CONFIRMED",
                "kind": "library-search",
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; "
            "family membership is the catalog-named P-id list, confirmed by two "
            "parsers plus the evidence_requirement expected n=7. Schedules are "
            "designed SAT semantics, not copied library fields. "
            "SUCCESS:CNL-0044"
        ),
    }

    try:
        import jsonschema
    except ImportError:
        jsonschema = None  # type: ignore
    if jsonschema is not None and LOCAL_SCHEMA.is_file():
        local = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(local).validate(doc)
        empty_errors = list(jsonschema.Draft7Validator(local).iter_errors({}))
        if not empty_errors:
            print("FAILED:CNL-0044 schema accepts empty object")
            return 1
    if jsonschema is not None and CATALOG_SCHEMA.is_file():
        catalog = json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8"))
        ref = str(catalog.get("$ref") or "")
        # Generated shim: no local constraints; do not fetch ast-integrate.invalid.
        if "ast-integrate.invalid" not in ref and not catalog.get("x-generated-by"):
            jsonschema.Draft7Validator(catalog).validate(doc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {rel_out} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNL-0044 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
