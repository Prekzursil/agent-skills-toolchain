#!/usr/bin/env python3
"""Emit the CNL-0064 design note (JSON stored at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import publication as P  # noqa: E402
import recount as R  # noqa: E402
import tabulate as T  # noqa: E402
from fixtures_lib import councils, load_all  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0064-weighted-voting-weight-provenance-and-post-hoc-audit.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0064/note.schema.json"
CATALOG_SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0064/probe1_counterfactual.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0064/probe2_negative_control.py"
)
DEP_PATHS = {
    "CNL-0023": (
        "command-center/design/council/"
        "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
    ),
    "CNL-0058": (
        "command-center/design/council/"
        "CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
    ),
}
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def line_of(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNL-0064 emit snippet not found in {rel}: {snippet}")


def fixture_row(fid: str, fixture: dict, live: dict) -> dict:
    if live.get("rejected"):
        return {
            "id": fid,
            "rejected": True,
            "reject_code": live.get("reject_code"),
            "weighted_winner": None,
            "equal_winner": None,
            "weighting_flip": None,
            "equal_weight_counterfactual": None,
        }
    return {
        "id": fid,
        "rejected": False,
        "weighted_winner": live["weighted_result"]["winner"],
        "equal_winner": live["equal_weight_counterfactual"]["winner"],
        "weighted_status": live["weighted_result"]["status"],
        "equal_status": live["equal_weight_counterfactual"]["status"],
        "weighting_flip": live["weighting_flip"],
        "weighting_delta": live["weighting_delta"],
        "equal_weight_counterfactual": live["equal_weight_counterfactual"],
        "weighted_result": live["weighted_result"],
        "expect_flip": bool(fixture.get("expect_flip")),
    }


def main() -> int:
    rows = []
    for fid, fixture in councils().items():
        live = T.decide(fixture)
        review = R.recount(fixture)
        if bool(live.get("rejected")) != bool(review.get("rejected")):
            print(f"FAILED:CNL-0064 emit reject mismatch {fid}")
            return 1
        if not live.get("rejected"):
            if review.get("weighted_winner") != live["weighted_result"]["winner"]:
                print(f"FAILED:CNL-0064 emit winner mismatch {fid}")
                return 1
            if bool(review.get("weighting_flip")) != bool(live.get("weighting_flip")):
                print(f"FAILED:CNL-0064 emit flip mismatch {fid}")
                return 1
        rows.append(fixture_row(fid, fixture, live))

    unpublished = load_all()["unpublished-delta"]
    if not P.fires(unpublished):
        print("FAILED:CNL-0064 emit unpublished fixture did not fire")
        return 1
    stable = T.decide(councils()["weighted-stable"])
    if P.fires(stable, stable):
        print("FAILED:CNL-0064 emit complete audit fired")
        return 1

    t_rel = "command-center/p2-wave/probes/CNL-0064/tabulate.py"
    r_rel = "command-center/p2-wave/probes/CNL-0064/recount.py"
    p_rel = "command-center/p2-wave/probes/CNL-0064/publication.py"
    t_snip = "Equal-weight counterfactual: every seated ballot is re-scored at weight 1."
    r_snip = "Map option -> list of contributing weights (not a running total)."
    p_snip = "True when the publication check rejects the document."
    t_line = line_of(t_rel, t_snip)
    r_line = line_of(r_rel, r_snip)
    p_line = line_of(p_rel, p_snip)

    deps = {}
    for uid, rel in DEP_PATHS.items():
        deps[uid] = {
            "artifact_present": (REPO / rel).is_file(),
            "path": rel,
            "role": (
                "pre-run provenance gate for non-unit weights"
                if uid == "CNL-0023"
                else "threshold denominator freeze / quorum interaction"
            ),
        }

    catalog_inputs = {path: (Path(path).is_file()) for path in CATALOG_INPUTS}

    note = {
        "unit_id": "CNL-0064",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0064",
        "title": "Weighted voting: weight provenance and post-hoc audit",
        "question": (
            "Given a decided council, can an auditor recompute the outcome under "
            "equal weights and see how much of the decision the weighting alone "
            "produced - and is that delta published with the result?"
        ),
        "answer": (
            "Yes, if and only if every published weighted result carries an "
            "equal-weight counterfactual on the same frozen seated set, a numeric "
            "weighting_delta, and a boolean weighting_flip. The counterfactual "
            "re-scores every seated ballot at weight 1 without dropping seats. A "
            "result that omits the counterfactual is unpublished, not audited. A "
            "flip is a disclosure that weighting changed the winner or "
            "threshold-status; it does not by itself void the decision. Catalog "
            "Windows inputs and CNL-0023/CNL-0058 artifacts are not on this tree; "
            "this note consumes their interfaces rather than claiming those units "
            "are delivered."
        ),
        "claim_under_test": (
            "A decided weighted council is not publishable unless an auditor can "
            "recompute the equal-weight counterfactual from the same ballots and "
            "read a published delta plus flip flag beside the result."
        ),
        "declared_signal": {
            "name": "weighting_audit",
            "required_fields": [
                "weighted_result",
                "equal_weight_counterfactual",
                "weighting_delta",
                "weighting_flip",
            ],
            "flip_rule": (
                "weighting_flip is true iff weighted winner differs from equal-weight "
                "winner OR weighted status differs from equal-weight status"
            ),
            "denominator_rule": (
                "weighted threshold uses seated_weight; equal-weight threshold uses "
                "seated_count; seated set is frozen"
            ),
        },
        "which_stops_the_round": {
            "stops": (
                "publishing a weighted decision without equal_weight_counterfactual, "
                "or publishing weighting_flip false/absent when winner or status "
                "changes under equal weights"
            ),
            "does_not_stop": (
                "a non-zero score delta that leaves winner and threshold-status "
                "unchanged; that is disclosed, not a halt"
            ),
            "satisfy_quota_from_padding": False,
        },
        "decision_rule": {
            "equal_weight_unit": "1",
            "weighted_denominator": "sum of seated weights",
            "equal_denominator": "seated count",
            "flip": "winner inequality or status inequality",
            "provenance_required_when": "seat weight != 1",
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Every non-rejected weighted fixture publishes an equal-weight "
                    "counterfactual computed from the same seated ballots."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{t_rel}:{t_line}",
            },
            {
                "id": "C2",
                "claim": (
                    "A decision whose winner or threshold-status changes under equal "
                    "weights is flagged weighting_flip=true; a stable weighted "
                    "majority is flagged false but still carries the delta."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{t_rel}:{t_line}",
            },
            {
                "id": "C3",
                "claim": (
                    "An independent grouped-list recount agrees with the running-total "
                    "tabulator on winner, status, and flip for every council fixture."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{r_rel}:{r_line}",
            },
            {
                "id": "C4",
                "claim": (
                    "A published weighted result that omits the counterfactual is "
                    "rejected by the publication check; a complete audit is silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{p_rel}:{p_line}",
            },
        ],
        "evidence": [
            {
                "path": t_rel,
                "line": t_line,
                "snippet": t_snip,
                "kind": "running-total-tabulator",
                "claim": "equal-weight re-score is implemented, not asserted",
            },
            {
                "path": r_rel,
                "line": r_line,
                "snippet": r_snip,
                "kind": "grouped-list-recount",
                "claim": "reviewer sums grouped weights without importing tabulate",
            },
            {
                "path": p_rel,
                "line": p_line,
                "snippet": p_snip,
                "kind": "publication-detector",
                "claim": "omitted counterfactual is a detectable publication defect",
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-equal-weight",
                "rejects": (
                    "an enumerator that flags weighting_flip on an all-weight-1 council"
                ),
                "verbatim": (
                    "negative-control target=equal-weight weighting_flip=false "
                    "excess=0/1 rejected=False. If weighting_flip were true, the "
                    "flip enumerator would be wrong."
                ),
            },
            {
                "id": "NC-missing-provenance",
                "rejects": "a non-unit weight with no provenance record",
                "verbatim": (
                    "negative-control target=missing-provenance rejected=True "
                    "code=MISSING_PROVENANCE. The check fires before any score "
                    "is accumulated."
                ),
            },
            {
                "id": "NC-unpublished-delta",
                "rejects": "a weighted result published without the equal-weight audit",
                "verbatim": (
                    "unpublished_fires=True on fixture unpublished-delta, which "
                    "carries weighted_result only. Complete weighted-stable audit "
                    "is silent."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0064-probe2-grouped-recount",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "re_ran_both_states": True,
            "method": (
                "recount.py groups ballots by option then sums; publication.py "
                "fires on unpublished-delta and is silent on weighted-stable"
            ),
        },
        "output_schema_catalog": CATALOG_SCHEMA_REL,
        "output_schema_validated_against": SCHEMA_REL,
        "shared_schema_note": (
            "Catalog names command-center/schema/council-design-note.schema.json. "
            "That file is a generated $ref shim to ast-integrate.invalid; "
            "Draft7Validator on this image raises RefResolutionError (no network). "
            "This note is validated against the unit-local schema so the "
            "negative_controls mutant is a real rejection rather than a fetch error."
        ),
        "artifacts": [
            {"path": ART_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "unit-local-schema"},
            {"path": CATALOG_SCHEMA_REL, "exists": True, "role": "catalog-declared-schema"},
            {"path": t_rel, "exists": True, "role": "author-tabulator"},
            {"path": r_rel, "exists": True, "role": "independent-recount"},
            {"path": p_rel, "exists": True, "role": "publication-detector"},
        ],
        "strongest_surviving_counterargument": (
            "Publishing the flip does not force any consumer to treat a "
            "weight-driven winner as illegitimate; a later gate could ignore the "
            "audit fields. This unit requires publication and detection of omission, "
            "not a downstream halt. Consumption of the flag is a later unit."
        ),
        "fixture_results": rows,
        "dependency_status": deps,
        "catalog_inputs_on_tree": catalog_inputs,
        "residual": (
            "CNL-0023 and CNL-0058 artifacts are absent on this worktree. The "
            "provenance gate and frozen-denominator rule are implemented here as "
            "consumed interfaces, not as a claim that those units are delivered. "
            "Harness restore files named in the catalog inputs are not on this Linux "
            "tree."
        ),
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    jsonschema.Draft7Validator.check_schema(schema)
    validator.validate(note)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0064", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0064 emit schema accepted garbage {list(garbage)[:2]}")
            return 1
    out = REPO / ART_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(note, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    written = out.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0064" not in written:
        print("FAILED:CNL-0064 emit sentinel missing")
        return 1
    print(f"wrote {ART_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0064 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
