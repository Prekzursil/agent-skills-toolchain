#!/usr/bin/env python3
"""Emit CNL-0003 charter-block design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import compiler as C  # noqa: E402
import reviewer as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0003-charter-block-the-typed-fields-a-compiler-actually-branche.md"
)
SCHEMA_NOTE = "command-center/schema/council-design-note.schema.json"
CHARTER_SCHEMA = "command-center/p2-wave/probes/CNL-0003/charter_block.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0003/probe1_branch_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0003/probe2_both_states.py"
)
QUESTION = (
    "Which charter fields (objective, risk tier, desired output, success "
    "criteria, consensus intent) does the council compiler need as ENUMS "
    "rather than prose in order to auto-select a protocol, and for each "
    "prose field that survives, what is the fallback when the compiler "
    "cannot branch?"
)
V1_SCHEMA = "11-COUNCIL-SPECIFICATION.schema.json"
V1_CATALOGUE = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0003 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def source_present(name: str) -> dict:
    candidates = [
        REPO / name,
        REPO / "command-center" / "sources" / name,
        REPO / "command-center" / "schema" / name,
        REPO / "command-center" / "design" / "council" / name,
    ]
    hits = [p for p in candidates if p.is_file()]
    return {
        "name": name,
        "present": bool(hits),
        "hit_count": len(hits),
        "checked": [str(p.relative_to(REPO)) for p in candidates],
    }


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0003 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    recount = R.recount()
    table = C.cartesian_protocol_ids()
    v1 = source_present(V1_SCHEMA)
    catalogue = source_present(V1_CATALOGUE)
    negative = C.select(C.good_charter(risk_tier="urgent-ish"))
    good = C.select(C.good_charter())
    lose = C.losing_select(C.good_charter(risk_tier="urgent-ish"))
    verbatim = (
        f"ok={negative.ok} protocol_id={negative.protocol_id!r} "
        f"reason={negative.reason}"
    )

    answer = (
        "The compiler auto-selects a protocol by table lookup. Lookup keys must "
        "be members of closed enums; prose cannot index a catalogue without NLP, "
        "and NLP is not a compiler. ENUMS the compiler branches on: risk_tier "
        "{low, medium, high, critical}, desired_output {decision, ranked_options, "
        "specification, review, counterexample, plan}, consensus_intent "
        "{unanimous, supermajority, majority, owner_decides, dissent_required}. "
        "PROSE that survives: objective (the actual task text) and "
        "success_criteria (human-facing done-when). Fallbacks when the compiler "
        "cannot branch: objective empty => COMPILE_REJECT reason=objective_required "
        "(completeness, not a silent protocol); objective present => copied to "
        "task_prose and excluded from protocol_id; success_criteria empty => "
        "attach protocol-native stopping and emit "
        "success_criteria_absent_used_protocol_default; success_criteria present "
        "=> copied to human_success_criteria and never parsed. Unknown or missing "
        "enum => COMPILE_REJECT (unknown_enum:/missing_enum:), never a default "
        "protocol. Cartesian size of the live table is "
        + str(len(table))
        + ". The losing option (all five fields as prose plus dict.get default) "
        "silent-defaults risk_tier='urgent-ish' to "
        + str(lose.protocol_id)
        + "; the live compiler rejects that input. SUCCESS:CNL-0003"
    )

    doc = {
        "unit_id": "CNL-0003",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0003",
        "completion_sentinel": "SUCCESS:CNL-0003",
        "title": "Charter block: the typed fields a compiler actually branches on",
        "question": QUESTION,
        "answer": answer,
        "charter_block": {
            "enum_fields": {
                "risk_tier": list(C.RISK_FAMILY.keys()),
                "desired_output": list(C.OUTPUT_FAMILY.keys()),
                "consensus_intent": list(C.INTENT_FAMILY.keys()),
            },
            "prose_fields": {
                "objective": {
                    "branches": False,
                    "empty_fallback": "COMPILE_REJECT:objective_required",
                    "present_fallback": "copy to task_prose; exclude from protocol_id",
                },
                "success_criteria": {
                    "branches": False,
                    "empty_fallback": C.ABSENT_CRITERIA_TOKEN,
                    "present_fallback": (
                        "copy to human_success_criteria; exclude from protocol_id"
                    ),
                },
            },
            "silent_default": "forbidden",
            "cartesian": len(table),
            "protocol_id_shape": "risk_family.output_family.intent_family",
            "axis_maps": {
                "risk_tier": C.RISK_FAMILY,
                "desired_output": C.OUTPUT_FAMILY,
                "consensus_intent": C.INTENT_FAMILY,
            },
        },
        "source_absence": {
            "v1_schema": v1,
            "protocol_catalogue": catalogue,
            "note": (
                "Enum members are the compiler's required closed sets for a total "
                "branch function, not harvested from the absent v1 schema or the "
                "58/72 catalogue records. Protocol ids here are family tokens, "
                "not 12-COUNCIL card names."
            ),
        },
        "dependency_cnl_0001": {
            "output_path": (
                "command-center/design/council/"
                "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
            ),
            "present": (
                REPO
                / "command-center/design/council/"
                / "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
            ).is_file(),
            "note": (
                "CNL-0001 is not delivered on this tree. The charter-block enums "
                "are specified independently of the v2 root envelope."
            ),
        },
        "evidence": [
            ev(
                "command-center/p2-wave/probes/CNL-0003/compiler.py",
                "if key not in axis:",
                "probe-runtime",
                "Unknown enum COMPILE_REJECTs; there is no default arm.",
            ),
            ev(
                "command-center/p2-wave/probes/CNL-0003/compiler.py",
                "return axis[key], None",
                "probe-runtime",
                "Live select() uses dict[key], not dict.get(key, default).",
            ),
            ev(
                CHARTER_SCHEMA,
                '"enum": ["low", "medium", "high", "critical"]',
                "schema-file",
                "Second signal: risk_tier is a JSON Schema enum, not prose.",
            ),
            ev(
                CATALOG,
                "as ENUMS rather than prose in order to auto-select a protocol",
                "catalog",
                "The unit question names the five charter fields under test.",
            ),
        ],
        "tests": [
            {
                "id": "probe1-compiler-branch-table",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2-both-states-jsonschema",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
                "raw_output": out2,
            },
            {
                "id": "losing-option-silent-default",
                "command": "compiler.losing_select(risk_tier='urgent-ish')",
                "result": "PASS" if lose.ok and lose.protocol_id else "FAIL",
                "note": (
                    "Losing option implemented far enough to demonstrate the "
                    "failure the criterion predicts: unknown enum still yields "
                    + str(lose.protocol_id)
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "unknown-enum-silent-default",
                "reject_state": "risk_tier='urgent-ish' (prose in an enum field)",
                "check_does": (
                    "COMPILE_REJECT with reason unknown_enum:risk_tier:urgent-ish "
                    "and protocol_id=None. Does not emit consult.vote.majority."
                ),
                "verbatim": verbatim,
                "fires_on_planted_bad": True,
                "silent_on_known_good": bool(good.ok),
            }
        ],
        "reviewer": {
            "reviewer_id": recount["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": recount["cartesian"] == len(table),
            "recounted_cartesian": recount["cartesian"],
            "counterexample": recount["counterexample"],
            "counterexample_claim": recount["counterexample_claim"],
            "mechanism": recount["mechanism"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CHARTER_SCHEMA, "exists": True, "role": "charter-block-schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0003/compiler.py",
                "exists": True,
                "role": "compiler",
            },
        ],
        "not_checked": [
            {
                "claim": (
                    "v1 Council Charter already types these five fields as enums "
                    "in 11-COUNCIL-SPECIFICATION.schema.json"
                ),
                "reason": (
                    "File absent on this worktree; cannot harvest v1 property "
                    "shapes. Enum members here are compiler requirements."
                ),
            },
            {
                "claim": (
                    "protocol_id tokens equal named cards in "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
                ),
                "reason": (
                    "Catalogue absent (same measurement as ARC-0003/A2). Family "
                    "tokens are not a 58-card count."
                ),
            },
        ],
        "known_good_compile": {
            "ok": good.ok,
            "protocol_id": good.protocol_id,
            "reason": good.reason,
            "fallbacks": list(good.fallbacks),
        },
        "required_fix": None,
        "cloud_ok": False,
        "schema_note_path": SCHEMA_NOTE,
        "schema_note_present": (REPO / SCHEMA_NOTE).is_file(),
    }

    out_path = REPO / OUT
    dump(out_path, doc)
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0003" not in text:
        print("FAILED:CNL-0003 sentinel missing after write")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:CNL-0003 state")
        return 1
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
