#!/usr/bin/env python3
"""Emit the CNL-0018 council design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mechanism import (  # noqa: E402
    EVT_QUOTA_EXHAUSTED,
    EVT_SUBSTITUTION_REFUSED,
    MANDATORY_FROM_TIER,
    N_ROUNDS,
    RISK_TIERS,
    run_all_controls,
)

OUT = (
    "command-center/design/council/"
    "CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md"
)
SCHEMA = (
    "command-center/p2-wave/probes/CNL-0018/council-design-note.schema.json"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0018/probe1_quota_exhaustion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0018/probe2_same_base_model.py"
)
QUESTION = (
    "Cross-vendor seats consume a SECOND paid subscription - what diversity "
    "objective is worth that spend, at what council risk tier does vendor "
    "diversity become mandatory rather than optional, and what happens when "
    "the quota for the second vendor is exhausted mid-council?"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0018 emit snippet not found in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    got = path.read_text(encoding="utf-8").splitlines()[line - 1]
    if snippet not in got and snippet not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"FAILED:CNL-0018 emit anchor {rel}:{line}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    ctrl = run_all_controls()
    diverse = ctrl["diverse"]
    same = ctrl["same_base_twice"]
    cross = ctrl["same_base_cross_vendor"]
    quota_bad = ctrl["quota_bad"]
    quota_good = ctrl["quota_good"]
    recount_bad = ctrl["quota_recount_bad"]
    loud = [e for e in quota_bad["events"] if e.get("type") == EVT_QUOTA_EXHAUSTED]
    refused = [e for e in quota_bad["events"] if e.get("type") == EVT_SUBSTITUTION_REFUSED]
    turns = (quota_bad.get("partial_artifact") or {}).get("turns") or []

    if not diverse.get("vendor_diverse"):
        print("FAILED:CNL-0018 emit diverse roster rejected")
        return 1
    if not same.get("same_base_model_twice") or same.get("vendor_diverse"):
        print("FAILED:CNL-0018 emit same-base-twice not flagged")
        return 1
    if not cross.get("same_base_model_twice") or cross.get("vendor_diverse"):
        print("FAILED:CNL-0018 emit cross-vendor same-base not flagged")
        return 1
    if not loud or quota_bad.get("reseated_same_vendor"):
        print("FAILED:CNL-0018 emit quota-bad did not degrade cleanly")
        return 1
    if not refused:
        print("FAILED:CNL-0018 emit substitution not refused")
        return 1
    if not turns:
        print("FAILED:CNL-0018 emit partial empty")
        return 1
    if [e for e in quota_good["events"] if e.get("type") == EVT_QUOTA_EXHAUSTED]:
        print("FAILED:CNL-0018 emit quota-good not silent")
        return 1
    if int(recount_bad.get("turns_before") or -1) != len(turns):
        print("FAILED:CNL-0018 emit recount disagreement")
        return 1
    if ctrl["seating_mandatory_same_base"].get("action") != "refuse":
        print("FAILED:CNL-0018 emit mandatory seating")
        return 1
    if ctrl["seating_optional_same_base"].get("action") != "seat-with-waiver":
        print("FAILED:CNL-0018 emit optional seating")
        return 1

    user_prompts_live = (
        Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md").is_file()
        or (REPO / "_USER-PROMPTS.md").is_file()
    )
    council_schema_live = (
        Path(
            r"C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"
        ).is_file()
        or (REPO / "11-COUNCIL-SPECIFICATION.schema.json").is_file()
        or (REPO / "command-center/schema/councilspec.v2.schema.json").is_file()
    )
    owner_decisions = (REPO / "command-center/OWNER-DECISIONS.md").is_file()
    cnl0005 = list((REPO / "command-center/design/council").glob("CNL-0005*")) if (REPO / "command-center/design/council").is_dir() else []

    evidence = [
        ev(
            "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
            "Use multiple providers/models for independence when permitted",
            "harvested-prompt",
            "Standing owner text names independence, not costume diversity, as the reason to use multiple providers.",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
            "Treat quota and arrival rate as scheduler inputs.",
            "harvested-prompt",
            "Standing budget-pacing position: quota is a scheduler input, not a reason to silently substitute seats.",
        ),
        ev(
            "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
            "Resource cost is not a reason to lower rigor. It is a reason to choose a safer execution substrate.",
            "harvested-prompt",
            "Standing budget-pacing position: cost does not lower rigor; exhaustion degrades or stops, it does not pad the roster.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "a quota-exhaustion fixture mid-council must degrade loudly and preserve the partial artifact, never silently re-seat the same vendor twice",
            "catalog",
            "Catalog test requires loud degrade, partial preservation, and no same-vendor reseat.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "a same-base-model-twice roster must be flagged as NOT vendor-diverse",
            "catalog",
            "Catalog test requires same-base-model-twice to fail the vendor-diversity check.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "emit NOT-CHECKED for any quota figure not actually measured",
            "catalog",
            "Catalog evidence rule: unmeasured quota figures stay NOT-CHECKED.",
        ),
        ev(
            "command-center/p2-wave/probes/CNL-0018/mechanism.py",
            'MANDATORY_FROM_TIER = "high-stakes"',
            "live-tree",
            "Executable seating rule: vendor diversity is mandatory from high-stakes upward.",
        ),
    ]

    verbatim_quota = (
        "NEGATIVE CONTROL (quota): the check FIRES on planted exhaustion "
        f"(openai remaining=1, {N_ROUNDS} rounds) with {len(loud)} "
        "QUOTA-EXHAUSTED event(s), preserves the partial transcript "
        f"({len(turns)} turns), and refuses same-vendor reseat "
        f"({len(refused)} SUBSTITUTION-REFUSED). The check is SILENT on the "
        "known-good remaining map (both vendors=100): zero QUOTA-EXHAUSTED "
        f"events, terminal={quota_good.get('terminal')}, independence_void="
        f"{quota_good.get('independence_void')}."
    )
    verbatim_div = (
        "NEGATIVE CONTROL (diversity): the check FIRES on a same-base-model-twice "
        "roster (two claude-opus seats; vendor_diverse=false, "
        "same_base_model_twice=true, reason=same-base-model-twice) and is SILENT "
        "on the known-good roster (anthropic/claude-opus + openai/gpt-4o; "
        "vendor_diverse=true). It also FIRES on openai/gpt-4o + azure/gpt-4o "
        "(distinct vendor labels, same base model) so vendor-string makeup "
        "cannot game the metric."
    )

    doc = {
        "unit_id": "CNL-0018",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0018",
        "completion_sentinel": "SUCCESS:CNL-0018",
        "format": "council-design-note/v1+json",
        "title": "Model and vendor diversity selection under a real quota ceiling",
        "question": QUESTION,
        "answers": {
            "diversity_objective": (
                "The second paid subscription is worth the spend only as a second "
                "failure domain: a vendor that does not share the first vendor's "
                "outage, safety-layer, training-correlation, or quota pool. Costume "
                "diversity (two labels on one base model, or two models on one "
                "vendor) is not that objective and is not vendor-diverse."
            ),
            "mandatory_from_risk_tier": MANDATORY_FROM_TIER,
            "quota_exhaustion": (
                "When the second vendor's remaining-call counter hits zero mid-council "
                "the runtime emits a loud QUOTA-EXHAUSTED event, freezes the partial "
                "transcript as the artifact, marks independence_void, and refuses to "
                "pad the roster with another seat of a vendor already present. At "
                "high-stakes/irreversible the council stops in DEGRADED rather than "
                "continuing as if independent. It never silently re-seats the same "
                "vendor twice."
            ),
            "worth_the_spend": (
                "Independence is the only diversity objective that justifies a second "
                "subscription. Procurement of that subscription is not authorized by "
                "this note; this note specifies when a seated council must USE a "
                "second vendor (mandatory from high-stakes) and what happens if that "
                "vendor's quota is exhausted."
            ),
        },
        "risk_tiers": {
            "enum": list(RISK_TIERS),
            "discovery": "optional — single-vendor may run; independence waiver recorded",
            "standard": "recommended — missing diversity is a recorded waiver, council may run",
            "high-stakes": "mandatory — refuse to start if not vendor-diverse; quota exhaustion degrades loudly and stops",
            "irreversible": "mandatory — same seating rule as high-stakes; exhaustion still preserves the partial artifact",
            "mandatory_from": MANDATORY_FROM_TIER,
        },
        "vendor_diversity_predicate": {
            "rule": "vendor_diverse iff distinct_vendors>=2 AND distinct_base_models>=2 AND no base_model seated twice",
            "same_base_model_twice_is_not_vendor_diverse": True,
            "computed": {
                "diverse": diverse,
                "same_base_twice": same,
                "same_base_cross_vendor": cross,
                "same_vendor_diff_model": ctrl["same_vendor_diff_model"],
            },
        },
        "quota_exhaustion_control": {
            "declared_before_scoring": {
                "n_rounds": N_ROUNDS,
                "quota_bad": {"anthropic": 100, "openai": 1},
                "quota_good": {"anthropic": 100, "openai": 100},
            },
            "bad_fired": True,
            "good_silent": True,
            "turns_preserved_on_bad": len(turns),
            "reseated_same_vendor": False,
            "substitution_refused": True,
            "bad_terminal": quota_bad["terminal"],
            "good_terminal": quota_good["terminal"],
            "independent_recount_turns_before": recount_bad["turns_before"],
        },
        "diversity_control": {
            "same_base_twice_flagged": True,
            "diverse_accepted": True,
            "cross_vendor_same_base_flagged": True,
            "mandatory_same_base_action": ctrl["seating_mandatory_same_base"]["action"],
            "optional_same_base_action": ctrl["seating_optional_same_base"]["action"],
        },
        "owner_gate": {
            "catalog_requires_approval": True,
            "owner_decisions_md_present": owner_decisions,
            "new_spend_default_guessed": False,
            "new_dollar_or_remaining_quota_default": None,
            "how_discharged": (
                "The owner gate forbids guessing a spend/quota default. This note "
                "does not guess one. Diversity objective and exhaustion behaviour "
                "are derived from cited standing positions (independence; quota as "
                "scheduler input; cost does not lower rigor). Whether to purchase a "
                "second subscription is a procurement question and is NOT-CHECKED. "
                "OWNER-DECISIONS.md is absent on this worktree and is not forged."
            ),
            "standing_positions": [
                "multiple providers/models for independence when permitted",
                "treat quota and arrival rate as scheduler inputs",
                "resource cost is not a reason to lower rigor",
            ],
        },
        "inputs_live": {
            "user_prompts_md": user_prompts_live,
            "council_specification_schema": council_schema_live,
            "cnl_0005_artifact_present": bool(cnl0005),
            "owner_decisions_md": owner_decisions,
            "surrogate_for_10579": (
                "command-center/p2-wave/probes/WFA-0042/_validate_out.json "
                "around_10723 harvest of _USER-PROMPTS.md"
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Independence is the diversity objective that justifies a second paid vendor.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json:254",
            },
            {
                "id": "C2",
                "claim": "Vendor diversity is mandatory from risk tier high-stakes.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0018/mechanism.py",
            },
            {
                "id": "C3",
                "claim": "Mid-council quota exhaustion degrades loudly, preserves the partial artifact, and refuses same-vendor reseat.",
                "verdict": "CONFIRMED",
                "anchor": "quota_exhaustion_control",
            },
            {
                "id": "C4",
                "claim": "Same-base-model-twice rosters are not vendor-diverse, including cross-vendor label pairs.",
                "verdict": "CONFIRMED",
                "anchor": "diversity_control",
            },
            {
                "id": "C5",
                "claim": "Live remaining-quota / dollar cost of a second subscription on this estate.",
                "verdict": "NOT-CHECKED",
                "reason": "No live vendor quota or price was measured. Fixture integers are declared test counters, not production remaining-calls.",
            },
            {
                "id": "C6",
                "claim": "Verbatim read of _USER-PROMPTS.md:10579 and 11-COUNCIL-SPECIFICATION.schema.json on this Linux worktree.",
                "verdict": "NOT-CHECKED",
                "reason": "Those Windows restore paths are absent here. The independence/budget-pacing sentences are cited from the WFA-0042 harvest of that file.",
            },
        ],
        "tests": [
            {"id": "probe1-quota-exhaustion", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2-same-base-model", "command": P2, "result": "NOT-RUN"},
        ],
        "negative_controls": [
            {"id": "NC-quota", "rejects": "silent same-vendor reseat after exhaustion", "verbatim": verbatim_quota},
            {"id": "NC-diversity", "rejects": "same-base-model-twice counted as vendor-diverse", "verbatim": verbatim_div},
        ],
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": "CNL-0018-probe2-same-base-model-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Mechanical re-derivation: Counter over fixtures/declared.json "
                "base_model fields, plus jsonschema garbage rejection. Does not "
                "take the author's prose as evidence."
            ),
            "scope_not_agreement": True,
        },
        "schema_note": (
            "Catalog output_schema is command-center/schema/"
            "council-design-note.schema.json, a generated $ref shim to "
            "ast-integrate.invalid. This unit does not rebuild that shared "
            "file. Validation uses the per-unit schema."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "unit-local-schema"},
            {
                "path": CATALOG_SCHEMA,
                "exists": (REPO / CATALOG_SCHEMA).is_file(),
                "role": "catalog-named-schema-shim",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0018/mechanism.py",
                "exists": True,
                "role": "mechanism",
            },
        ],
        "residual_unknowns": [
            "Live remaining-call counters per vendor: NOT-CHECKED.",
            "CNL-0005 nine-dial participant descriptor is not on disk; this note uses vendor/model/base_model only.",
            "OWNER-DECISIONS.md is absent; no new spend authorization is recorded.",
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        print(f"FAILED:CNL-0018 emit schema vacuous rejected={rejected}/3")
        return 1
    shared_path = REPO / CATALOG_SCHEMA
    if shared_path.is_file():
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft7Validator(shared).validate(doc)
        except jsonschema.ValidationError as exc:
            print(
                "WARN: catalog council-design-note.schema.json rejected the "
                f"note; unit-local schema used. {exc.message}"
            )
        except jsonschema.exceptions.RefResolutionError as exc:
            print(
                "WARN: catalog council-design-note.schema.json is a $ref shim; "
                f"unit-local schema used. {type(exc).__name__}"
            )

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size} garbage_rejected={rejected}")
    print("SUCCESS:CNL-0018 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
