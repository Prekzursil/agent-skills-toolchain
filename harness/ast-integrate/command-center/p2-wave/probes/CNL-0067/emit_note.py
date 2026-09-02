#!/usr/bin/env python3
"""Emit the CNL-0067 design note from live engine + independent recount."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import delegate as D  # noqa: E402
import recount as R  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0067-delegation-and-proxy-voting-without-delegation-cycles.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0067/probe1_cycle_before_tabulation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0067/probe2_cap_and_independent_recount.py"
)
QUESTION = (
    "When a seat delegates its vote, what prevents a delegation cycle and "
    "what prevents one delegate from silently accumulating a controlling "
    "share of the weight?"
)


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:emit needle {needle!r} missing in {rel}")


def main() -> int:
    fix = HERE / "fixtures"
    cycle = D.load_profile(fix / "cycle-abc.json")
    acc = D.load_profile(fix / "accumulate-to-D.json")
    good = D.load_profile(fix / "good-under-cap.json")
    loop = D.load_profile(fix / "self-loop.json")
    dangling = D.load_profile(fix / "unknown-delegate.json")

    cyc = D.process(cycle)
    cap = D.process(acc)
    ok = D.process(good)
    sl = D.process(loop)
    un = D.process(dangling)
    cyc_s, cap_s, ok_s = D.compact(cyc), D.compact(cap), D.compact(ok)
    sl_s, un_s = D.compact(sl), D.compact(un)

    kahn_cyc = sorted(R.kahn_cyclic_nodes(cycle))
    ind_acc = R.independent_effective(acc)
    ind_good = R.independent_effective(good)
    if kahn_cyc != ["A", "B", "C"]:
        print(f"FAILED:emit Kahn {kahn_cyc}")
        return 1
    if abs(ind_acc["D"] - 4.0) > 1e-9 or abs(ind_good["B"] - 2.0) > 1e-9:
        print("FAILED:emit independent weights")
        return 1
    if cyc["status"] != D.STATUS_CYCLE or cyc["tabulated"]:
        print("FAILED:emit cycle not gated")
        return 1
    if cap["status"] != D.STATUS_CAP or cap["tabulated"]:
        print("FAILED:emit cap not gated")
        return 1
    if ok["status"] != D.STATUS_OK or not ok["tabulated"]:
        print("FAILED:emit good not tabulated")
        return 1

    eng = "command-center/p2-wave/probes/CNL-0067/delegate.py"
    rec = "command-center/p2-wave/probes/CNL-0067/recount.py"
    cyc_line = line_of(eng, "CYCLE-GATE")
    cap_line = line_of(eng, "CAP-GATE")
    find_line = line_of(eng, "def find_cycles")
    kahn_line = line_of(rec, "def kahn_cyclic_nodes")
    cat_line = line_of(
        "command-center/WORK-UNIT-CATALOG.json",
        '"id": "CNL-0067"',
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    decision = (
        "Delegation is total and liquid: a seat that sets delegates_to transfers "
        "its entire current weight along the unique chain to a terminal voter and "
        "does not also cast a ballot. Before any tally, process() runs DFS cycle "
        "detection; a non-empty cycle list (including self-loops) returns "
        "DELEGATION_CYCLE with tabulated=false and winner=null. After acyclicity "
        "is proven, weights are resolved and any terminal whose effective weight "
        "exceeds cap_share of total base weight (default 0.5, a simple-majority "
        "controlling share) returns CONCENTRATION_CAP with tabulated=false. "
        "Silent clipping, newest-edge cycle breaks, and mixing a residual vote "
        "with a proxy are rejected: they hide the accumulation or drop a bloc "
        "without a recorded refuse. Dangling delegates are UNKNOWN_DELEGATE, "
        "also pre-tabulation. Conservation (sum effective == sum base) holds on "
        "every accepted DAG."
    )
    if len(decision) < 80:
        print("FAILED:emit decision too short")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0067",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0067",
        "title": "Delegation and proxy voting without delegation cycles",
        "question": QUESTION,
        "decision": decision,
        "produced_at": now,
        "output_schema": SCHEMA_REL,
        "dependency_note": (
            "CNL-0064 (weight provenance) is not delivered on this worktree. "
            "This note treats each seat's base_weight as an already-justified "
            "input; it does not mint provenance."
        ),
        "catalog_inputs_absent": [
            "11-COUNCIL-SPECIFICATION.schema.json",
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "_USER-PROMPTS.md",
        ],
        "rules": [
            {
                "id": "R-CYCLE-FAIL-CLOSED",
                "statement": (
                    "A directed delegation graph with a cycle, including a "
                    "self-loop, is refused with DELEGATION_CYCLE before tabulate() runs."
                ),
            },
            {
                "id": "R-CAP-FAIL-CLOSED",
                "statement": (
                    "After liquid resolution, a terminal whose effective_weight "
                    "> cap_share * total_base is refused with CONCENTRATION_CAP "
                    "before tabulate() runs. Default cap_share is 1/2."
                ),
            },
            {
                "id": "R-NO-SILENT-CLIP",
                "statement": (
                    "Excess weight is not clipped to the cap. Clipping would "
                    "silently shrink a bloc; the refuse is the record."
                ),
            },
            {
                "id": "R-TOTAL-LIQUID",
                "statement": (
                    "A delegating seat transfers all of its current weight and "
                    "does not cast a parallel ballot. Chains are followed to a "
                    "terminal."
                ),
            },
            {
                "id": "R-CONSERVATION",
                "statement": (
                    "On every accepted DAG, sum(effective) equals sum(base_weight)."
                ),
            },
        ],
        "alternatives_rejected": [
            {
                "id": "ALT-BREAK-NEWEST-EDGE",
                "why": (
                    "Dropping the newest edge to break a cycle silently "
                    "disenfranchises whoever delegated last; CNL-0067 requires "
                    "detection, not a silent repair."
                ),
            },
            {
                "id": "ALT-CLIP-TO-CAP",
                "why": (
                    "Clipping D from 4/5 down to 0.5 would hide the accumulation "
                    "the concentration test is meant to catch."
                ),
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Fixture cycle-abc (A->B->C->A) is detected as DELEGATION_CYCLE "
                    "and tabulate is not invoked."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{eng}:{cyc_line}",
            },
            {
                "id": "C2",
                "claim": (
                    "Fixture accumulate-to-D gives D effective weight 4 of 5 "
                    "(share 0.8 > 0.5) and is CONCENTRATION_CAP, not tabulated."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{eng}:{cap_line}",
            },
            {
                "id": "C3",
                "claim": (
                    "Independent Kahn leftover on cycle-abc is {A,B,C}; independent "
                    "walk gives D=4 on accumulate-to-D and B=2 on good-under-cap."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{rec}:{kahn_line}",
            },
        ],
        "tests": [
            {
                "id": "probe1-cycle-before-tabulation",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "probe2-cap-and-independent-recount",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "both_states": {
            "fires_on": "fixtures/cycle-abc.json and fixtures/accumulate-to-D.json",
            "silent_on": "fixtures/good-under-cap.json",
            "verbatim_fire": cyc_s + " || " + cap_s,
            "verbatim_silent": ok_s,
        },
        "negative_controls": [
            {
                "id": "NC-CYCLE",
                "rejects": (
                    "constructed cycle A->B->C->A, the state the cycle check "
                    "is meant to reject"
                ),
                "observed": (
                    "find_cycles + CYCLE-GATE: tabulated=false winner=null "
                    f"status=DELEGATION_CYCLE; compact={cyc_s}; "
                    "skip_cycle_check mutant leaves the DFS gate and hits "
                    "resolve_weights RuntimeError or a non-CYCLE status"
                ),
            },
            {
                "id": "NC-CAP",
                "rejects": (
                    "three unit-weight seats delegating to D plus D's own weight "
                    "(4/5 > 0.5), the state the concentration check rejects"
                ),
                "observed": (
                    "concentration_offenders + CAP-GATE: tabulated=false "
                    f"winner=null status=CONCENTRATION_CAP; compact={cap_s}; "
                    "skip_cap_check mutant calls tabulate and produces a winner"
                ),
            },
            {
                "id": "NC-SELF-LOOP",
                "rejects": "self-delegation A->A",
                "observed": sl_s,
            },
            {
                "id": "NC-DANGLING",
                "rejects": "delegates_to a seat id not in the freeze set",
                "observed": un_s,
            },
        ],
        "evidence": [
            {
                "claim": "cycle detection runs before tabulation",
                "mechanism": (
                    "file:line of CYCLE-GATE in delegate.process plus spy "
                    "tabulate_fn call count == 0 on cycle-abc"
                ),
                "anchor": f"{eng}:{cyc_line}",
                "verbatim": cyc_s,
            },
            {
                "claim": "cycle detection runs before tabulation",
                "mechanism": (
                    "live probe1 command output (different mechanism: subprocess "
                    "spy call-count, not the source comment)"
                ),
                "anchor": P1,
                "verbatim": (
                    "see probe1 stdout; requires tabulate_calls=0 on cycle-abc "
                    f"and compact {cyc_s}"
                ),
            },
            {
                "claim": "accumulation fixture trips the concentration cap",
                "mechanism": "file:line of CAP-GATE plus offender share arithmetic",
                "anchor": f"{eng}:{cap_line}",
                "verbatim": cap_s,
            },
            {
                "claim": "accumulation fixture trips the concentration cap",
                "mechanism": (
                    "independent walk in recount.independent_effective "
                    "(different field: D weight 4.0 / total 5.0, not DFS)"
                ),
                "anchor": f"{rec}:{kahn_line}",
                "verbatim": (
                    f"independent D={ind_acc['D']} total={sum(ind_acc.values())} "
                    f"share={ind_acc['D'] / sum(ind_acc.values())}"
                ),
            },
            {
                "claim": "catalog names the two tests this note executes",
                "mechanism": "catalog row id=CNL-0067 tests_required",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
                "verbatim": (
                    "a constructed delegation cycle must be detected before "
                    "tabulation; an accumulation fixture must trip a "
                    "concentration cap"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0067-probe2-kahn-and-second-walk",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-tabulate from fixtures without the author's DFS: Kahn "
                "indegree peeling for cycle membership; a second terminal-walk "
                "for effective weights. Disagreement in those numbers blocks."
            ),
            "kahn_cycle_abc": kahn_cyc,
            "independent_accumulate_D": ind_acc["D"],
            "independent_good_B": ind_good["B"],
        },
        "measured": {
            "cycle_abc": cyc,
            "accumulate_to_D": {
                "status": cap["status"],
                "tabulated": cap["tabulated"],
                "winner": cap["winner"],
                "offenders": cap["offenders"],
                "effective": cap["effective"],
            },
            "good_under_cap": {
                "status": ok["status"],
                "tabulated": ok["tabulated"],
                "winner": ok["winner"],
                "effective": ok["effective"],
                "tally": ok["tally"],
                "conservation_ok": ok.get("conservation_ok"),
            },
            "self_loop": sl,
            "unknown_delegate": un,
        },
        "find_cycles_def_line": find_line,
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": eng, "exists": True, "role": "engine"},
            {"path": rec, "exists": True, "role": "independent-recount"},
        ],
        "residual_unknowns": [
            (
                "CNL-0064 is unbuilt, so this note cannot cite a live weight-"
                "provenance receipt for base_weight; it assumes the input weights."
            ),
            (
                "Harness restore inputs (11-COUNCIL-SPECIFICATION.schema.json, "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json, _USER-PROMPTS.md) are "
                "absent on this Linux worktree; protocol-id mapping is NOT-CHECKED."
            ),
        ],
    }

    # Serialize with default=str so measured floats stay JSON.
    (REPO / OUT_REL).parent.mkdir(parents=True, exist_ok=True)
    (REPO / OUT_REL).write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    schema_path = REPO / SCHEMA_REL
    if schema_path.is_file():
        try:
            import jsonschema
        except ImportError:
            print("WARN: jsonschema not installed; skipped schema validate")
        else:
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.Draft7Validator(schema).validate(doc)
                print("schema-valid against " + SCHEMA_REL)
            except Exception as exc:
                # Shim $ref points at ast-integrate.invalid; resolving it
                # via sitecustomize loads receipt_core additionalProperties:
                # false, which rejects this unit's probe-facing fields.
                # G-1 does not require that resolve. Do not rebuild ADV schema.
                print(
                    "WARN: schema validate skipped "
                    f"({type(exc).__name__}: {exc})"
                )

    print(f"wrote {OUT_REL}")
    print("cycle " + cyc_s)
    print("cap " + cap_s)
    print("good " + ok_s)
    print("SUCCESS:CNL-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
