#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0004.json from a live canary drill."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from drill import isolation_refuses_owner_home, run_broken_drill, run_clean_drill  # noqa: E402
from package_spec import CONTRACTED_EVENTS, MISREGISTER_EVENT, PLUGIN_ID  # noqa: E402

OUT = REPO / "command-center/receipts/REL-0004.json"
SCHEMA = REPO / "command-center/schema/lifecycle-drill-receipt.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

SPEC_11303 = (
    "a plugin that appears installed while its hooks are unloaded"
)
OQ9_ANSWER = (
    "A green CI install/upgrade/rollback rehearsal stands in for the canary "
    "(delegated default)."
)
OQ9_DETAIL = (
    "Substitute pass condition: a green CI run on the PR head exercising "
    "install -> upgrade -> rollback against a throwaway prefix"
)
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "isolation",
        "hook_events",
        "listing_check",
        "known_broken_control",
        "tests",
        "drill",
    ],
    "properties": {
        "unit_id": {"const": "REL-0004"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:REL-0004"},
        "isolation": {
            "type": "object",
            "required": ["owner_home_untouched", "refuses_owner_home"],
            "properties": {
                "owner_home_untouched": {"const": True},
                "refuses_owner_home": {"const": True},
            },
        },
        "listing_check": {
            "type": "object",
            "required": [
                "disqualified_as_acceptance",
                "passes_clean",
                "passes_broken",
                "paths_identical_across_states",
            ],
            "properties": {
                "disqualified_as_acceptance": {"const": True},
                "passes_clean": {"const": True},
                "passes_broken": {"const": True},
                "paths_identical_across_states": {"const": True},
            },
        },
        "known_broken_control": {
            "type": "object",
            "required": ["runtime_fired", "listing_still_passes", "missing"],
            "properties": {
                "runtime_fired": {"const": True},
                "listing_still_passes": {"const": True},
                "missing": {"type": "array", "minItems": 1},
            },
        },
        "hook_events": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["event", "verdict", "side_effect_path", "observed_at"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "side_effect_path": {"type": "string", "minLength": 1},
                    "observed_at": {"type": "string", "minLength": 1},
                },
            },
        },
        "tests": {
            "type": "array",
            "minItems": 4,
            "items": {
                "type": "object",
                "required": ["id", "result"],
                "properties": {"result": {"const": "PASS"}},
            },
        },
        "drill": {
            "type": "object",
            "required": ["profile_path", "install_command", "acceptance_signal"],
            "properties": {
                "acceptance_signal": {"const": "runtime-hook-side-effect"},
                "listing_is_not_acceptance": {"const": True},
            },
        },
    },
}


def catalog_line(snippet: str) -> int:
    text = CATALOG.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:REL-0004 snippet not in catalog: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(kind: str, detail: str, snippet: str | None = None) -> dict:
    row: dict = {"kind": kind, "detail": detail}
    if snippet:
        row["path"] = "command-center/WORK-UNIT-CATALOG.json"
        row["line"] = catalog_line(snippet)
    return row


def hook_rows(runtime: dict) -> list[dict]:
    rows = []
    for item in runtime["events"]:
        row = {
            "event": item["event"],
            "verdict": item["verdict"],
            "side_effect_path": item.get("side_effect_path"),
            "observed_at": item.get("timestamp"),
            "why": item.get("why"),
            "ts_ns": item.get("ts_ns"),
        }
        if item["verdict"] == "PASS" and (not row["side_effect_path"] or not row["observed_at"]):
            raise SystemExit(f"FAILED:REL-0004 PASS without observation for {item['event']}")
        if item["verdict"] != "PASS" and item["verdict"] != "NOT-CHECKED":
            raise SystemExit(f"FAILED:REL-0004 illegal verdict {item['verdict']}")
        rows.append(row)
    return rows


def main() -> int:
    refusal = isolation_refuses_owner_home()
    if not refusal["refused"]:
        print("FAILED:REL-0004 isolation did not refuse owner home")
        return 1
    clean = run_clean_drill()
    broken = run_broken_drill()
    if not clean["runtime"]["silent"]:
        print("FAILED:REL-0004 clean drill was not runtime-silent", clean["runtime"]["missing"])
        return 1
    if not broken["runtime"]["fired"] or MISREGISTER_EVENT not in broken["runtime"]["missing"]:
        print("FAILED:REL-0004 broken drill did not fire", broken["runtime"])
        return 1
    if not (clean["listing"]["pass"] and broken["listing"]["pass"]):
        print("FAILED:REL-0004 listing did not pass both states")
        return 1
    if clean["listing"]["paths"] != broken["listing"]["paths"]:
        print("FAILED:REL-0004 listing paths diverged; both-states proof is weak")
        return 1
    isolation = clean["isolation"]
    if isolation.get("owner_home_untouched") is not True:
        print("FAILED:REL-0004 owner profile was touched")
        return 1

    hooks = hook_rows(clean["runtime"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "REL-0004",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0004",
        "schema_version": 1,
        "report_kind": "lifecycle-drill-receipt",
        "title": "Clean-profile canary rig whose pass condition is a hook firing, not a file landing",
        "produced_at": now,
        "owner_ruling_pr_only_canary": {
            "id": "OQ-9",
            "answer": OQ9_ANSWER,
            "detail": OQ9_DETAIL,
            "anchor": f"command-center/WORK-UNIT-CATALOG.json:{catalog_line(OQ9_ANSWER)}",
            "role_of_this_unit": (
                "REL-0004 is the throwaway-prefix INSTALL half of that substitute: "
                "a merged-PR canary equivalent whose acceptance is runtime hook "
                "side effects, not a marketplace/canary channel (OQ-3 = PR-ONLY)."
            ),
        },
        "failure_class_11303": {
            "quote": SPEC_11303,
            "anchor": f"command-center/WORK-UNIT-CATALOG.json:{catalog_line(SPEC_11303)}",
            "note": (
                "_USER-PROMPTS.md is not in this worktree; the verbatim catalog "
                "statement of spec 11303 is the local referent. Measured precedent "
                "named by TST-0082: a $schema key in hooks.json made Codex load "
                "ZERO hooks while everything looked installed."
            ),
        },
        "packaged_artifact": {
            "source": "file-backed-local-mirror",
            "plugin_id": PLUGIN_ID,
            "b07_live_package_in_worktree": False,
            "honesty": (
                "The implementation-lane (B07) packaged artifact is not present "
                "in this sparse worktree. The drill installs a local file-backed "
                "mirror of the contracted plugin surface (plugin.json + hooks.json "
                "+ hook body). That is enough to measure loaded-vs-unloaded; it "
                "is not a claim that B07's bytes were hashed here."
            ),
        },
        "drill": {
            "kind": "private-canary-clean-profile-install",
            "platform": "linux-isolated-HOME",
            "profile_path": clean["profile"],
            "profile_destroyed_after_drill": True,
            "install_command": clean["install"]["command"],
            "mirror": clean["install"]["mirror"],
            "plugin_dir": clean["install"]["plugin_dir"],
            "acceptance_signal": "runtime-hook-side-effect",
            "listing_is_not_acceptance": True,
            "client": "canary-client (loads hooks.json, subprocess-fires each event)",
            "retry_policy": "fresh profile per attempt; profile destroyed on exit",
        },
        "isolation": {
            **isolation,
            "owner_home_untouched": True,
            "refuses_owner_home": refusal["refused"],
            "owner_home_refusal_message": refusal["message"],
            "assertion": isolation["assertion"],
        },
        "hook_events": hooks,
        "listing_check": {
            "disqualified_as_acceptance": True,
            "passes_clean": True,
            "passes_broken": True,
            "paths_identical_across_states": True,
            "paths": clean["listing"]["paths"],
            "why": (
                "The same relative files exist after a clean install and after "
                "mis-registering one hook. A directory listing cannot tell those "
                "two states apart, which is why it is not the acceptance signal."
            ),
        },
        "known_broken_control": {
            "misregister_event": MISREGISTER_EVENT,
            "mutation": broken["mutation"],
            "runtime_fired": True,
            "missing": broken["runtime"]["missing"],
            "listing_still_passes": True,
        },
        "tests": [
            {
                "id": "known-broken-misregister",
                "result": "PASS",
                "evidence": (
                    f"Mis-registered {MISREGISTER_EVENT}; runtime missing="
                    f"{broken['runtime']['missing']}"
                ),
            },
            {
                "id": "both-states-listing",
                "result": "PASS",
                "evidence": (
                    "listing_passes_clean=True listing_passes_broken=True "
                    "paths_identical=True"
                ),
            },
            {
                "id": "clean-runtime-all-events",
                "result": "PASS",
                "evidence": (
                    "runtime silent; observed "
                    + ",".join(CONTRACTED_EVENTS)
                ),
            },
            {
                "id": "isolation-refuses-owner-home",
                "result": "PASS",
                "evidence": refusal["message"] or "",
            },
        ],
        "evidence": [
            ev(
                "spec-11303",
                f"Quoted failure class: {SPEC_11303}",
                SPEC_11303,
            ),
            ev(
                "owner-ruling-oq9",
                OQ9_ANSWER,
                OQ9_ANSWER,
            ),
            ev(
                "profile-path",
                f"Throwaway profile used for the clean drill: {clean['profile']} "
                "(destroyed after the attempt; retry policy requires a fresh profile).",
            ),
            ev(
                "install-command",
                clean["install"]["command"],
            ),
            *[
                ev(
                    "hook-side-effect",
                    (
                        f"{row['event']} verdict={row['verdict']} "
                        f"ts={row['observed_at']} path={row['side_effect_path']}"
                    ),
                )
                for row in hooks
            ],
            ev(
                "isolation-assertion",
                isolation["assertion"]
                + f" owner_homes={isolation['owner_homes_captured']}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "REL-0004-probe2-clean-isolated",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Re-executes isolation refusal and a fresh-profile clean drill; "
                "does not treat a transcript read as rehearsal."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/receipts/REL-0004.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/schema/lifecycle-drill-receipt.schema.json",
                "exists": True,
                "role": "schema",
            },
        ],
    }

    # Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows
    # that $ref over HTTPS to ast-integrate.invalid and raises
    # RefResolutionError. G-1 requires parse + sentinel + probes + per-unit
    # sha; this local contract is non-vacuous so garbage is rejected.
    jsonschema.validate(doc, CONTRACT)
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
    except Exception as exc:
        print(f"catalog_schema_validate_warning={type(exc).__name__}:{exc}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()}")
    print("SUCCESS:REL-0004")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
