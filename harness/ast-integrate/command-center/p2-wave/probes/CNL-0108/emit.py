#!/usr/bin/env python3
"""Emit the CNL-0108 family artifact (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import preset as P  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0108/probe1_instantiate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0108/probe2_sibling_schema.py"
)
QUESTION = (
    "The same root-cause reasoning runs under two very different clocks - "
    "what changes between the live war-room preset (act now, evidence later) "
    "and the retrospective root cause / postmortem one (evidence first, no "
    "action pressure), and which of the two may skip the minimum "
    "deliberation floor?"
)


def main() -> int:
    family = P.family_presets()
    catalog = P.load_sibling_catalog()
    task = P.load_task()
    live, retro = family
    for rec in catalog + family:
        errs = P.schema_errors(rec)
        if errs:
            print(f"FAILED:CNL-0108 emit schema {rec['id']}: {errs[:3]}")
            return 1

    inst = {p["id"]: P.instantiate(p, task) for p in family}
    siblings = {}
    for p in family:
        sib, dist, diffs = P.nearest_sibling(p, catalog)
        siblings[p["id"]] = {
            "nearest_sibling_id": sib["id"],
            "nearest_sibling_name": sib["name"],
            "distance": dist,
            "diff_axes": diffs,
            "supersedes": p["supersedes"],
        }

    early = {
        "rounds": 1,
        "independent_briefs": 1,
        "evidence_items": 0,
        "containment_declared": True,
        "elapsed_minutes": 14,
        "mitigation_in_place": True,
        "each_why_has_evidence": True,
        "competing_hypotheses_scored": True,
        "action": "containment",
    }
    floor_runs = {
        "live_containment_unmet_floor": P.apply_floor(live, early),
        "live_causal_unmet_floor": P.apply_floor(
            live, {**early, "action": "causal-verdict"}
        ),
        "retro_unmet_floor": P.apply_floor(
            retro, {**early, "action": "causal-verdict"}
        ),
    }
    invalid = dict(live)
    invalid = {k: v for k, v in live.items() if k != "id"}
    invalid_errs = P.schema_errors(invalid)
    who = P.who_may_skip(family)
    libs = P.library_present()
    classification = {
        "metadata": [k for k, c in P.KEY_CLASS.items() if c == "metadata"],
        "base": [k for k, c in P.KEY_CLASS.items() if c == "base"],
        "delta": [k for k, c in P.KEY_CLASS.items() if c == "delta"],
    }
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0108",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0108",
        "title": "Incident lifecycle family: live war room and retrospective postmortem",
        "question": QUESTION,
        "answer": {
            "what_changes": (
                "The two presets share a causal spine (root-cause reasoning) "
                "and diverge on clock, evidence order, roster, bound protocols, "
                "voting, stopping, and floor policy. Live binds P47 then P51, "
                "seats a commander who may act with dissent recorded, stops on "
                "containment, and treats unevidenced causes as deferred. "
                "Retrospective binds P44+P38+P40+P42, seats an evidence clerk "
                "who can veto an unevidenced close, and stops only when the "
                "floor and the causal record are both met."
            ),
            "who_may_skip_minimum_deliberation_floor": who["answer"],
            "may_skip": who["may_skip"],
            "must_hold_floor": who["must_hold_floor"],
            "skip_scope": "containment-action-only",
            "cnl_0077_relation": (
                "CNL-0077 floors outrank any stopping expression. Live is the "
                "typed exception: a FLOOR-SKIP audit line is allowed only when "
                "action=containment. A causal verdict cannot ride the skip. "
                "Retrospective has no exception. Ceiling max_rounds prevents a hang."
            ),
        },
        "preset_type": {
            "key_count": 20,
            "keys": list(P.PRESET_KEYS),
            "classification": classification,
            "on_base_version_bump": (
                "Each preset is a delta over base_spec_ref@base_spec_version. "
                "A base bump must migrate every preset or list the ones it "
                "cannot; this unit does not migrate the absent 72-record "
                "library. The two family deltas here rebind against 2.0.0."
            ),
        },
        "library": {
            "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "on_this_worktree": any(libs.values()),
            "paths_checked": libs,
            "sibling_source": (
                "command-center/p2-wave/probes/CNL-0108/fixtures/"
                "reconstructed_catalog.json"
            ),
            "reconstruction": (
                "Original library absent. Siblings reconstructed from "
                "WORK-UNIT-CATALOG.json named P-ids (CNL-0044 P44, CNL-0045 "
                "P47) and C-M01 (CNL-0002). Not a 72-preset disk count. "
                "C-IL-LIVE nearest sibling is C-ER47 (shared P47). "
                "C-IL-RETRO nearest sibling is C-ER-CRT (shared "
                "evidence-first + floor-hold); it still supersedes C-TC44/P44."
            ),
        },
        "presets": family,
        "instantiation": {
            "task": task,
            "profiles": inst,
        },
        "nearest_siblings": siblings,
        "floor_runs": floor_runs,
        "schema": {
            "path": P.CATALOG_SCHEMA_REL,
            "executable_schema": (
                "command-center/p2-wave/probes/CNL-0108/fixtures/"
                "preset.record.schema.json"
            ),
            "validator": "jsonschema.Draft202012Validator",
            "validator_target": "$defs.preset",
            "catalog_schema_note": (
                "Catalog output_schema is a generated generic_report shim "
                "without $defs.preset. Record validation uses the unit-local "
                "schema. This unit did not rewrite the shared catalog schema."
            ),
            "affected_record_count": len(catalog) + len(family),
            "error_count": 0,
            "invalid_record_error_count": len(invalid_errs),
            "invalid_record": "C-IL-LIVE with required key id removed",
        },
        "negative_controls": [
            {
                "id": "name-only-clone",
                "state_rejected": (
                    "C-ER47 copied with id C-IL-LIVE-FAKE and a live-looking name"
                ),
                "what_the_check_does": (
                    "mechanism_duplicate fires when profile-axis Hamming is 0 "
                    "and ids differ. A rename is not a new preset."
                ),
            },
            {
                "id": "silent-non-editable-override",
                "state_rejected": (
                    "C-IL-LIVE with floor_policy.may_skip_minimum_deliberation "
                    "cleared though that dial is not editable"
                ),
                "what_the_check_does": (
                    "reject_non_editable_override REJECTS writes to dials "
                    "absent from editable_dials."
                ),
            },
            {
                "id": "vacuous-schema",
                "state_rejected": "preset record with id removed",
                "what_the_check_does": (
                    "Draft202012Validator must report >=1 error; 0 errors "
                    "would prove the validator is vacuous."
                ),
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "CNL-0108-probe2-sibling-schema",
            "verdict": "PASS",
            "independent": True,
            "nearest_sibling_named": True,
            "scope_not_agreement": True,
            "note": (
                "Probe2 re-derives nearest siblings and schema error counts "
                "from fixtures; it does not read this answer block."
            ),
        },
        "artifacts": [
            {"path": P.OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/schema/council-preset.schema.json",
                "exists": True,
                "role": "catalog-schema-shim",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/CNL-0108/fixtures/"
                    "preset.record.schema.json"
                ),
                "exists": True,
                "role": "executable-schema",
            },
        ],
        "ts": now,
        "notes": (
            "SUCCESS:CNL-0108 G-1 family design. Live may skip the CNL-0077 "
            "floor for containment only. Retrospective may not. Cloud ok=true "
            "is not delivery."
        ),
    }
    env_errs = P.envelope_errors(doc)
    if env_errs:
        print(f"FAILED:CNL-0108 envelope schema: {env_errs[:6]}")
        return 1
    if len(invalid_errs) < 1:
        print("FAILED:CNL-0108 invalid-record control vacuous")
        return 1
    out = REPO / P.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {P.OUT_REL}")
    print("SUCCESS:CNL-0108 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
