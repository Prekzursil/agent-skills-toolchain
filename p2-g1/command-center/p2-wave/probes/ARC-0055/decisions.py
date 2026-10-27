"""Blast-radius classification: DEFAULTED vs EXPLICIT.

Stance is tied to measured blast radius and reversal cost, not to convenience.
"""
from __future__ import annotations

from typing import Any

from catalog_stats import measure as catalog_measure
from fatigue import load_census
from marketplace import measure_schema, one_click_install


def _a8_design_owned(path):
    import json as _json
    try:
        if not path.is_file():
            return False
        doc = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return doc.get("unit_id") == "ARC-0052" and doc.get("state") == "SUCCESS"

def classify(repo) -> dict[str, Any]:
    cat = catalog_measure(repo)
    mkt = measure_schema(repo)
    inst = one_click_install(repo)
    fat = load_census(repo)["summary"]
    design = repo / "command-center/phase3/A8/DESIGN.json"
    decisions = [
        {
            "id": "D-READ-ONLY-DISCOVERY",
            "title": "Auto-allow Read/Grep/Glob/GetDynamicTools",
            "stance": "DEFAULTED",
            "blast_radius": {
                "metric": "mutating_files_written",
                "value": 0,
                "session_tools_this_class": fat["defaulted_tools"],
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "Local files already in the session are disclosed to the agent. "
                "No worktree bytes are mutated."
            ),
            "reversal_cost": (
                "None. No mutation occurred. Revoke by ending the session."
            ),
            "rationale": (
                "Blast radius is zero mutating files (measured session class "
                f"{fat['defaulted_tools']} of {fat['tool_use']} tool_use). "
                "Convenience is not the reason."
            ),
        },
        {
            "id": "D-MUTATING-TOOLS",
            "title": "Auto-allow Shell/Write/Edit/Delete/StrReplace",
            "stance": "EXPLICIT",
            "blast_radius": {
                "metric": "catalog_units_with_Write_and_no_owner_gate",
                "value": cat["write_without_owner_gate"],
                "session_tools_this_class": fat["explicit_tools"],
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "An agent writes or shells across the worktree. Catalog live "
                f"count: {cat['write_without_owner_gate']} units declare Write "
                "without owner_approval_required."
            ),
            "reversal_cost": (
                "Restore mutated files from VCS or backup. Shell side effects "
                "(network, process spawn) cannot be un-executed."
            ),
            "rationale": (
                "Blast radius is the Write-without-gate catalog set "
                f"({cat['write_without_owner_gate']} units), not the time saved "
                "by skipping a prompt."
            ),
        },
        {
            "id": "D-MARKETPLACE-ONE-CLICK",
            "title": "One-click install of an unreviewed marketplace package",
            "stance": "EXPLICIT",
            "blast_radius": {
                "metric": "files_written_by_generate",
                "value": inst["files_written_count"],
                "owner_prompts_invoked": inst["owner_prompts_invoked"],
                "live_review_like_keys": mkt["live_review_like_count"],
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "An unreviewed package materialises plugin, hook, skill, rule, "
                "docs, catalogs, and a marketplace listing. Live generate() "
                f"wrote {inst['files_written_count']} files and consulted "
                f"{mkt['live_review_like_count']} review-like schema fields."
            ),
            "reversal_cost": (
                f"Delete or regenerate {inst['files_written_count']} files. "
                "If an enabled PreToolUse hook already ran, those invocations "
                "cannot be un-executed."
            ),
            "rationale": (
                "Blast radius equals the generated file count of one install, "
                "measured by generate()+write_tree(), not estimated."
            ),
        },
        {
            "id": "D-OWNER-APPROVAL-GATE",
            "title": "Bypass catalog owner_approval_required",
            "stance": "EXPLICIT",
            "blast_radius": {
                "metric": "owner_gated_units",
                "value": cat["owner_gated"],
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "An executor supplies an owner ruling the owner did not make. "
                f"{cat['owner_gated']} catalog units are behind that gate."
            ),
            "reversal_cost": (
                "Cannot un-dispatch. ready_units.py already excludes these "
                "units; keeping that fail-closed is the reversal of a bypass."
            ),
            "rationale": (
                "Blast radius is the gated-unit count "
                f"({cat['owner_gated']}), not dispatch throughput."
            ),
        },
        {
            "id": "D-COUNCIL-PRESET-NO-ALLOWLIST",
            "title": "Apply a council preset that declares no tool allowlist",
            "stance": "EXPLICIT",
            "blast_radius": {
                "metric": "permission_fields_on_council_preset_schema",
                "value": 0,
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "A UX 'apply preset' click activates roles/voting/stopping "
                "with no permission overlay. The typed council_preset has "
                "roles, voting, stopping only."
            ),
            "reversal_cost": (
                "Remove the generated council/presets/*.json file. Votes "
                "already taken are not reversible."
            ),
            "rationale": (
                "Blast radius is 'no allowlist field exists, so the preset "
                "cannot bound tools'. Absence of a field is measured on the "
                "live schema, not inferred from a missing DESIGN.json."
            ),
        },
        {
            "id": "D-HOOK-ENABLE",
            "title": "Enable a new PreToolUse hook from a package or preset",
            "stance": "EXPLICIT",
            "blast_radius": {
                "metric": "subsequent_tool_calls_in_session",
                "value": fat["tool_use"],
                "computed_not_asserted": True,
            },
            "worst_case_if_default_wrong": (
                "An enabled hook sees every later tool call "
                f"({fat['tool_use']} in the snapshotted sessions). A fail-open "
                "hook is then a silent policy rewrite."
            ),
            "reversal_cost": (
                "Disable the hook file. Past hook executions cannot be undone."
            ),
            "rationale": (
                "Blast radius is every subsequent tool_use in the session, "
                "counted from real transcripts, not from a UX slogan."
            ),
        },
    ]
    defaulted = [d for d in decisions if d["stance"] == "DEFAULTED"]
    explicit = [d for d in decisions if d["stance"] == "EXPLICIT"]
    missing_fields = []
    for d in decisions:
        for key in ("stance", "blast_radius", "reversal_cost", "worst_case_if_default_wrong"):
            if not d.get(key):
                missing_fields.append(f"{d['id']}.{key}")
        br = d["blast_radius"]
        if br.get("computed_not_asserted") is not True:
            missing_fields.append(f"{d['id']}.blast_radius.computed")
        if "value" not in br:
            missing_fields.append(f"{d['id']}.blast_radius.value")
    return {
        "a8_design_present": design.is_file(),
        "a8_design_owned_by_dependency": _a8_design_owned(design),
        "decisions": decisions,
        "defaulted_count": len(defaulted),
        "explicit_count": len(explicit),
        "classification_complete": len(missing_fields) == 0,
        "missing_fields": missing_fields,
        "catalog": cat,
        "marketplace_schema": mkt,
        "one_click": inst,
        "fatigue": fat,
    }
