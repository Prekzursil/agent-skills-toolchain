#!/usr/bin/env python3
"""Run the 21 encoded stopping predicates and adjudicate the terminal verdict.

A NOT-CHECKED never folds into PROGRAM-COMPLETE. DECORATIVE is never TRUE.
Condition 13 under PR-ONLY is recorded FALSE with an explicit resolution;
it is not skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conditions import BY_ID, SPEC  # noqa: E402

CATALOG = "command-center/WORK-UNIT-CATALOG.json"
EVAL_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0043/evaluate.py"
)
SCANNER_TOKENS = (
    "codeql",
    "trivy",
    "grype",
    "osv-scanner",
    "pip-audit",
    "license-check",
    "fossology",
    "dependabot",
    "snyk",
    "gitleaks",
    "nancy",
    "govulncheck",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _exists(rel: str) -> bool:
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def _completion_gates_green() -> bool | None:
    """Read the recorded program-stopping tally. File present is not green."""
    path = REPO / "command-center/COMPLETION-GATES.json"
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    tally = (doc.get("gate_b_program_stopping_rule") or {}).get("assessment_tally")
    if not isinstance(tally, dict):
        return False
    return (
        int(tally.get("TRUE") or 0) == 21
        and int(tally.get("FALSE") or 0) == 0
        and int(tally.get("NOT-CHECKED") or 0) == 0
    )


def _oq9_pr_only_substitute() -> dict[str, Any]:
    path = REPO / "command-center/OWNER-DECISIONS.md"
    if not path.is_file():
        return {"recorded": False, "path": "command-center/OWNER-DECISIONS.md"}
    text = path.read_text(encoding="utf-8")
    recorded = (
        "OQ-9" in text
        and "PR-ONLY" in text
        and "install" in text.lower()
        and "rollback" in text.lower()
    )
    return {
        "recorded": recorded,
        "path": "command-center/OWNER-DECISIONS.md",
        "substitute": (
            "green CI install/upgrade/rollback rehearsal (OQ-9 delegated default)"
            if recorded
            else ""
        ),
        "as_written_still_unsatisfiable": True,
    }


def clone_world(world: dict[str, Any], **kw: Any) -> dict[str, Any]:
    out = dict(world)
    out.update(kw)
    return out


def load_live_world() -> dict[str, Any]:
    catalog_path = REPO / CATALOG
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    units = catalog.get("work_units") or []
    meta = catalog.get("work_units_meta") or {}
    ids = [u.get("id") for u in units if isinstance(u, dict) and u.get("id")]
    wf_dir = REPO / ".github" / "workflows"
    workflows = []
    scanner_hits: list[str] = []
    if wf_dir.is_dir():
        for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
            rel = p.relative_to(REPO).as_posix()
            workflows.append(rel)
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            hits = [tok for tok in SCANNER_TOKENS if tok in text]
            if hits:
                scanner_hits.append(f"{rel}:{'+'.join(hits)}")

    present = {
        "cc0015": _exists("command-center/receipts/CC-0015.json"),
        "tst0347": _exists("command-center/receipts/TST-0347.json"),
        "owner_decisions": _exists("command-center/OWNER-DECISIONS.md"),
        "completion_gates": _exists("command-center/COMPLETION-GATES.json"),
        "phase_graph": _exists("command-center/PHASE-GRAPH.json"),
        "option_closure": _exists("command-center/synthesis/SYN-0028.option-closure.json"),
        "improvement_ledger": _exists(
            "command-center/synthesis/SYN-0034.improvement-ledger.json"
        ),
        "docs_code": _exists("command-center/receipts/SYN-0020.json")
        or _exists("command-center/synthesis/SYN-0020.docs-code.json"),
        "test_registry": _exists("command-center/TEST-REGISTRY.json"),
        "claim_registry": _exists("command-center/CLAIM-REGISTRY.json"),
        "cc0014": _exists("command-center/receipts/CC-0014.json"),
        "cc0024": _exists("command-center/receipts/CC-0024.json"),
        "unknowns": _exists("command-center/UNKNOWNS-REGISTER.md"),
        "bld0029": _exists("command-center/receipts/BLD-0029.json"),
        "option_universe": _exists("07-OPTION-UNIVERSE.json")
        or _exists("command-center/sources/07-OPTION-UNIVERSE.json"),
        "blueprints": _exists("09-WORKFLOW-BLUEPRINT-LIBRARY.json")
        or _exists("command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json"),
        "council": _exists("12-COUNCIL-PROTOCOLS-AND-PRESETS.json")
        or _exists("command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
        "rel0003": _exists("command-center/receipts/REL-0003.json"),
        "imp0457": _exists("command-center/receipts/IMP-0457.json"),
        "imp0458": _exists("command-center/receipts/IMP-0458.json"),
        "user_prompts": _exists("_USER-PROMPTS.md"),
        "rollback_manifest": _exists("command-center/ROLLBACK-MANIFEST.json")
        or _exists("command-center/receipts/REL-0006.json"),
        "compat_matrix": _exists("command-center/phase4/contracts/ARC-0095.json"),
    }

    oq9 = _oq9_pr_only_substitute()
    # As-written C13 stays unsatisfiable under PR-ONLY even when OQ-9 is recorded.
    # Do not set owner_c13_ruling: that would skip the explicit PR-ONLY resolution.
    return {
        "kind": "live",
        "present": present,
        "work_unit_count": len(ids),
        "work_unit_unique": len(set(ids)),
        "work_units_meta_count": meta.get("work_unit_count"),
        "work_units_meta_target": meta.get("target"),
        "work_units_meta_shortfall": meta.get("shortfall"),
        "release_mode": "PR-ONLY",
        "canary_channel_exists": False,
        "canary_succeeded": False,
        "owner_c13_ruling": None,
        "oq9": oq9,
        "workflows": workflows,
        "scanner_hits": scanner_hits,
        "option_undisposed": None,
        "requirements_unbound": None,
        "rerun_until_green_count": None,
        "required_tests_red": None,
        "mutation_unproven_suites": None,
        "claims_single_signal": None,
        "untested_marked_supported": None,
        "improvement_net": None,
        "secrets_in_artifacts": None,
        "completion_gates_green": _completion_gates_green(),
        "release_scan_fresh": bool(scanner_hits) if workflows else None,
        "docs_code_agree": None,
        "rollback_tested": None,
        "unknowns_without_experiment": None,
        "workflow_candidates": None,
        "blueprints": None,
        "protocols": None,
        "presets": None,
        "platform_options": None,
    }


def all_true_world() -> dict[str, Any]:
    """Synthetic world in which every predicate is TRUE (CANARY mode)."""
    return {
        "kind": "synthetic-all-true",
        "present": {},
        "work_unit_count": 2048,
        "work_unit_unique": 2048,
        "work_units_meta_count": 2048,
        "work_units_meta_target": 2048,
        "work_units_meta_shortfall": 0,
        "release_mode": "CANARY",
        "canary_channel_exists": True,
        "canary_succeeded": True,
        "owner_c13_ruling": "canary-channel-present",
        "workflows": ["synthetic/release.yml"],
        "scanner_hits": ["synthetic/release.yml:trivy"],
        "option_undisposed": 0,
        "requirements_unbound": 0,
        "rerun_until_green_count": 0,
        "required_tests_red": (),
        "mutation_unproven_suites": 0,
        "claims_single_signal": 0,
        "untested_marked_supported": 0,
        "improvement_net": "IMPROVED",
        "secrets_in_artifacts": False,
        "completion_gates_green": True,
        "release_scan_fresh": True,
        "docs_code_agree": True,
        "rollback_tested": True,
        "unknowns_without_experiment": 0,
        "workflow_candidates": 160,
        "blueprints": 96,
        "protocols": 48,
        "presets": 64,
        "platform_options": 160,
    }


def _checked(value: Any, ok: bool, why_nc: str, why_false: str, why_true: str) -> dict:
    if value is None:
        return {"verdict": "NOT-CHECKED", "reason": why_nc}
    if ok:
        return {"verdict": "TRUE", "reason": why_true}
    return {"verdict": "FALSE", "reason": why_false}


def eval_condition(cid: int, world: dict[str, Any]) -> dict[str, Any]:
    spec = BY_ID[cid]
    present = world.get("present") or {}

    if cid == 1:
        r = _checked(
            world.get("option_undisposed"),
            world.get("option_undisposed") == 0,
            "option-closure artifact and option universe are absent; selected set cannot be enumerated",
            f"undisposed option ids={world.get('option_undisposed')}",
            "selected-set undisposed count is 0",
        )
    elif cid == 2:
        r = _checked(
            world.get("requirements_unbound"),
            world.get("requirements_unbound") == 0,
            "CC-0024 requirement register and _USER-PROMPTS.md are absent",
            f"unbound requirements={world.get('requirements_unbound')}",
            "unbound requirement count is 0",
        )
    elif cid == 3:
        r = _checked(
            world.get("rerun_until_green_count"),
            world.get("rerun_until_green_count") == 0,
            "CI run history for cited greens is not on this worktree",
            f"rerun-until-green count={world.get('rerun_until_green_count')}",
            "no cited green required discarded failures",
        )
    elif cid == 4:
        red = world.get("required_tests_red")
        r = _checked(
            red if red is not None else None,
            red == () or red == [],
            "TEST-REGISTRY.json and required-test run results are absent",
            f"required tests red={list(red) if red is not None else None}",
            "required-test red list is empty",
        )
    elif cid == 5:
        r = _checked(
            world.get("mutation_unproven_suites"),
            world.get("mutation_unproven_suites") == 0,
            "CC-0014 TEST-REGISTRY mutation records are absent",
            f"unproven suites={world.get('mutation_unproven_suites')}",
            "every registered suite has a FAIL-on-mutation record",
        )
    elif cid == 6:
        r = _checked(
            world.get("claims_single_signal"),
            world.get("claims_single_signal") == 0,
            "CLAIM-REGISTRY.json is absent; load-bearing claims cannot be joined to probe pairs",
            f"single-signal claims={world.get('claims_single_signal')}",
            "no load-bearing claim is single-signal",
        )
    elif cid == 7:
        r = _checked(
            world.get("untested_marked_supported"),
            world.get("untested_marked_supported") == 0,
            "ARC-0095 compatibility matrix contract is absent",
            f"untested-marked-supported cells={world.get('untested_marked_supported')}",
            "no UNTESTED cell is labelled SUPPORTED",
        )
    elif cid == 8:
        net = world.get("improvement_net")
        r = _checked(
            net,
            net == "IMPROVED",
            "SYN-0034 improvement ledger is absent",
            f"improvement net={net}",
            "ledger net verdict is IMPROVED with no hidden UNMEASURED-as-NEUTRAL",
        )
    elif cid == 9:
        secrets = world.get("secrets_in_artifacts")
        r = _checked(
            secrets,
            secrets is False,
            "IMP-0458 secret-scrub receipt is absent; this unit does not scan live secret values",
            "secret-scrub gate reported a finding (name/scope only; value not printed)",
            "secret-scrub gate reported zero findings",
        )
    elif cid == 10:
        green = world.get("completion_gates_green")
        if not present.get("completion_gates") and world.get("kind") == "live":
            r = {
                "verdict": "NOT-CHECKED",
                "reason": "command-center/COMPLETION-GATES.json is absent",
            }
        else:
            r = _checked(
                green,
                green is True,
                "COMPLETION-GATES.json is absent",
                "at least one required completion gate is not green",
                "recorded completion gates are green",
            )
    elif cid == 11:
        fresh = world.get("release_scan_fresh")
        hits = world.get("scanner_hits") or []
        wfs = world.get("workflows") or []
        if world.get("kind") == "live":
            if not wfs:
                r = {
                    "verdict": "NOT-CHECKED",
                    "reason": ".github/workflows is empty; release gate cannot be read",
                }
            elif not hits:
                r = {
                    "verdict": "FALSE",
                    "reason": (
                        "inspected workflows "
                        + ",".join(wfs)
                        + " contain no vulnerability/license scanner step"
                    ),
                }
            else:
                r = {
                    "verdict": "TRUE",
                    "reason": "scanner tokens present: " + ",".join(hits),
                }
        else:
            r = _checked(
                fresh,
                fresh is True,
                "release workflow not supplied",
                "release-time scanner is missing or cache-backed",
                "release-time scanner re-runs",
            )
    elif cid == 12:
        r = _checked(
            world.get("docs_code_agree"),
            world.get("docs_code_agree") is True,
            "SYN-0020 docs-code measurement is absent",
            "docs-code measurement reported disagreement",
            "docs-code measurement reported agreement",
        )
    elif cid == 13:
        mode = str(world.get("release_mode") or "UNKNOWN")
        ruling = world.get("owner_c13_ruling")
        channel = bool(world.get("canary_channel_exists"))
        succeeded = bool(world.get("canary_succeeded"))
        if mode == "PR-ONLY" and not ruling:
            oq9 = world.get("oq9") or {}
            oq9_recorded = bool(oq9.get("recorded"))
            r = {
                "verdict": "FALSE",
                "reason": (
                    "as-written 'release/canary succeeds' has no referent under "
                    "binding PR-ONLY (no canary channel); REL-0003.json absent"
                    + (
                        "; OQ-9 recorded as install/upgrade/rollback substitute "
                        "but as-written remains unsatisfiable"
                        if oq9_recorded
                        else "; OQ-9/REL-0003 ruling packet absent"
                    )
                ),
                "pr_only": {
                    "release_mode": mode,
                    "as_written_satisfiable": False,
                    "skipped": False,
                    "ruling_present": oq9_recorded,
                    "ruling_id": "OQ-9" if oq9_recorded else None,
                    "rel0003_packet_present": bool(
                        (world.get("present") or {}).get("rel0003")
                    ),
                    "oq9": oq9,
                    "canary_channel_exists": channel,
                    "canary_succeeded": succeeded,
                    "default_if_unanswered": (
                        "redefine C13 as a merged PR plus clean-profile "
                        "install/upgrade/rollback rehearsal (REL-0003 / OQ-9); "
                        "until then as-written is FALSE"
                    ),
                },
            }
        elif succeeded and channel:
            r = {
                "verdict": "TRUE",
                "reason": f"release_mode={mode} canary_succeeded=true",
            }
        else:
            r = {
                "verdict": "FALSE",
                "reason": (
                    f"release_mode={mode} channel={channel} succeeded={succeeded} "
                    f"ruling={ruling!r}"
                ),
            }
    elif cid == 14:
        r = _checked(
            world.get("rollback_tested"),
            world.get("rollback_tested") is True,
            "REL-0006 / ROLLBACK-MANIFEST rollback-tested evidence is absent",
            "rollback rehearsal is missing or failed",
            "rollback rehearsal evidence is present and passing",
        )
    elif cid == 15:
        r = _checked(
            world.get("unknowns_without_experiment"),
            world.get("unknowns_without_experiment") == 0,
            "UNKNOWNS-REGISTER.md and BLD-0029 closure are absent",
            f"unknowns without named experiment={world.get('unknowns_without_experiment')}",
            "every residual unknown names a settling experiment",
        )
    elif cid == 16:
        n = world.get("workflow_candidates")
        r = _checked(
            n,
            isinstance(n, int) and n >= 160,
            "workflow candidate registry is absent; floor 160 cannot be counted",
            f"qualified candidates={n} floor=160",
            f"qualified candidates={n} >= 160",
        )
    elif cid == 17:
        n = world.get("blueprints")
        r = _checked(
            n,
            isinstance(n, int) and n >= 96,
            "blueprint library is absent; floor 96 cannot be counted",
            f"executable blueprints={n} floor=96",
            f"executable blueprints={n} >= 96",
        )
    elif cid == 18:
        n = world.get("protocols")
        r = _checked(
            n,
            isinstance(n, int) and n >= 48,
            "council protocol registry is absent; floor 48 cannot be counted",
            f"protocols={n} floor=48",
            f"protocols={n} >= 48",
        )
    elif cid == 19:
        n = world.get("presets")
        r = _checked(
            n,
            isinstance(n, int) and n >= 64,
            "council preset registry is absent; floor 64 cannot be counted",
            f"presets={n} floor=64",
            f"presets={n} >= 64",
        )
    elif cid == 20:
        n = int(world.get("work_unit_count") or 0)
        target = int(world.get("work_units_meta_target") or 2048)
        shortfall = world.get("work_units_meta_shortfall")
        ok = n >= target
        r = {
            "verdict": "TRUE" if ok else "FALSE",
            "reason": (
                f"work_units={n} unique={world.get('work_unit_unique')} "
                f"target={target} meta_shortfall={shortfall}"
            ),
        }
    elif cid == 21:
        n = world.get("platform_options")
        r = _checked(
            n,
            isinstance(n, int) and n >= 160,
            "option universe is absent; floor 160 platform options cannot be counted",
            f"platform options={n} floor=160",
            f"platform options={n} >= 160",
        )
    else:
        raise ValueError(f"unknown condition {cid}")

    if world.get("decorative_ids") and cid in set(world["decorative_ids"]):
        r = {
            "verdict": "DECORATIVE",
            "reason": r.get("reason", "") + " | classified DECORATIVE (unfalsifiable)",
        }

    cmd = f"{EVAL_CMD} --condition {cid}"
    payload = {
        "condition_id": cid,
        "verdict": r["verdict"],
        "reason": r["reason"],
        "spec_line": spec["spec_line"],
        "world_kind": world.get("kind"),
    }
    if "pr_only" in r:
        payload["pr_only"] = r["pr_only"]
    tail = json.dumps(payload, sort_keys=True)
    return {
        "condition_id": cid,
        "condition_text": spec["text"],
        "spec_line": spec["spec_line"],
        "reconstructed": spec["reconstructed"],
        "catalog_citation": spec["catalog_citation"],
        "floor": spec["floor"],
        "verdict": r["verdict"],
        "reason": r["reason"],
        "pr_only": r.get("pr_only"),
        "probe": {"command": cmd, "output_tail": tail[-2000:], "exit_code": 0},
        "timestamp": world.get("timestamp") or utc_now(),
    }


def evaluate_all(world: dict[str, Any], timestamp: str | None = None) -> list[dict]:
    ts = timestamp or utc_now()
    w = clone_world(world, timestamp=ts)
    return [eval_condition(i, w) for i in range(1, 22)]


def adjudicate(rows: list[dict]) -> dict[str, Any]:
    ids = [r.get("condition_id") for r in rows]
    if ids != list(range(1, 22)):
        missing = [i for i in range(1, 22) if i not in ids]
        return {
            "overall_verdict": "PROGRAM-INCOMPLETE",
            "blocking_class": "MISSING-ROW",
            "blocking_condition_ids": missing,
            "named_missing_probe": (
                f"{EVAL_CMD} --condition {missing[0]}" if missing else ""
            ),
            "reason": f"row ids {ids} are not 1..21",
        }
    counts = {"TRUE": 0, "FALSE": 0, "NOT-CHECKED": 0, "DECORATIVE": 0}
    for r in rows:
        v = str(r.get("verdict") or "")
        if v not in counts:
            return {
                "overall_verdict": "PROGRAM-INCOMPLETE",
                "blocking_class": "MISSING-ROW",
                "blocking_condition_ids": [r.get("condition_id")],
                "named_missing_probe": (r.get("probe") or {}).get("command", ""),
                "reason": f"row {r.get('condition_id')} has illegal verdict {v!r}",
            }
        counts[v] += 1
    counts["row_total"] = 21
    if counts["NOT-CHECKED"]:
        first = next(r for r in rows if r["verdict"] == "NOT-CHECKED")
        return {
            "overall_verdict": "PROGRAM-INCOMPLETE",
            "blocking_class": "NOT-CHECKED",
            "blocking_condition_ids": [
                r["condition_id"] for r in rows if r["verdict"] == "NOT-CHECKED"
            ],
            "named_missing_probe": first["probe"]["command"],
            "reason": (
                "NOT-CHECKED must not fold into a pass; first missing probe is "
                f"condition {first['condition_id']}"
            ),
            "counts": counts,
        }
    if counts["DECORATIVE"]:
        first = next(r for r in rows if r["verdict"] == "DECORATIVE")
        return {
            "overall_verdict": "PROGRAM-INCOMPLETE",
            "blocking_class": "DECORATIVE",
            "blocking_condition_ids": [
                r["condition_id"] for r in rows if r["verdict"] == "DECORATIVE"
            ],
            "named_missing_probe": first["probe"]["command"],
            "reason": (
                "unfalsifiable predicates are DECORATIVE and never TRUE; "
                f"first is condition {first['condition_id']}"
            ),
            "counts": counts,
        }
    if counts["FALSE"]:
        first = next(r for r in rows if r["verdict"] == "FALSE")
        return {
            "overall_verdict": "PROGRAM-INCOMPLETE",
            "blocking_class": "FALSE",
            "blocking_condition_ids": [
                r["condition_id"] for r in rows if r["verdict"] == "FALSE"
            ],
            "named_missing_probe": first["probe"]["command"],
            "reason": f"condition {first['condition_id']} is FALSE",
            "counts": counts,
        }
    if counts["TRUE"] != 21:
        return {
            "overall_verdict": "PROGRAM-INCOMPLETE",
            "blocking_class": "MISSING-ROW",
            "blocking_condition_ids": [],
            "named_missing_probe": "",
            "reason": f"TRUE count {counts['TRUE']} != 21",
            "counts": counts,
        }
    return {
        "overall_verdict": "PROGRAM-COMPLETE",
        "blocking_class": "NONE",
        "blocking_condition_ids": [],
        "named_missing_probe": "",
        "reason": "all 21 rows are TRUE",
        "counts": counts,
    }


def mutate_for(cid: int, world: dict[str, Any]) -> dict[str, Any]:
    """World mutation that MUST flip condition cid to FALSE if the predicate is live."""
    if cid == 1:
        return clone_world(world, option_undisposed=1)
    if cid == 2:
        return clone_world(world, requirements_unbound=1)
    if cid == 3:
        return clone_world(world, rerun_until_green_count=1)
    if cid == 4:
        return clone_world(world, required_tests_red=("required-test-red",))
    if cid == 5:
        return clone_world(world, mutation_unproven_suites=1)
    if cid == 6:
        return clone_world(world, claims_single_signal=1)
    if cid == 7:
        return clone_world(world, untested_marked_supported=1)
    if cid == 8:
        return clone_world(world, improvement_net="REGRESSED")
    if cid == 9:
        return clone_world(world, secrets_in_artifacts=True)
    if cid == 10:
        return clone_world(world, completion_gates_green=False)
    if cid == 11:
        return clone_world(
            world,
            release_scan_fresh=False,
            scanner_hits=[],
            workflows=["synthetic/release.yml"],
        )
    if cid == 12:
        return clone_world(world, docs_code_agree=False)
    if cid == 13:
        return clone_world(world, canary_succeeded=False)
    if cid == 14:
        return clone_world(world, rollback_tested=False)
    if cid == 15:
        return clone_world(world, unknowns_without_experiment=1)
    if cid == 16:
        return clone_world(world, workflow_candidates=10)
    if cid == 17:
        return clone_world(world, blueprints=10)
    if cid == 18:
        return clone_world(world, protocols=10)
    if cid == 19:
        return clone_world(world, presets=10)
    if cid == 20:
        return clone_world(world, work_unit_count=100, work_units_meta_shortfall=1948)
    if cid == 21:
        return clone_world(world, platform_options=10)
    raise ValueError(cid)


def falsifiability_table() -> dict[str, Any]:
    """TST-0347 stand-in: one mutation per predicate on an all-TRUE CANARY world."""
    base = all_true_world()
    base_rows = evaluate_all(base, timestamp="2026-08-24T00:00:00Z")
    base_adj = adjudicate(base_rows)
    rows = []
    unfalsifiable = []
    for cid in range(1, 22):
        before = base_rows[cid - 1]["verdict"]
        mutated = evaluate_all(mutate_for(cid, base), timestamp="2026-08-24T00:00:01Z")
        after = mutated[cid - 1]["verdict"]
        flipped = before == "TRUE" and after == "FALSE"
        others_ok = all(
            mutated[i]["verdict"] == base_rows[i]["verdict"]
            for i in range(21)
            if i != cid - 1
        )
        klass = "FALSIFIABLE" if flipped else "UNFALSIFIABLE"
        if not flipped:
            unfalsifiable.append(cid)
        rows.append(
            {
                "condition_id": cid,
                "mutation": f"mutate_for({cid})",
                "before": before,
                "after": after,
                "flipped_to_false": flipped,
                "other_rows_unchanged": others_ok,
                "class": klass,
            }
        )
    # Opposite pathology: C13 under PR-ONLY cannot become TRUE.
    pr_only = clone_world(
        all_true_world(),
        kind="synthetic-pr-only",
        release_mode="PR-ONLY",
        canary_channel_exists=False,
        canary_succeeded=True,
        owner_c13_ruling=None,
    )
    c13 = eval_condition(13, clone_world(pr_only, timestamp="2026-08-24T00:00:02Z"))
    return {
        "tst0347_receipt_present": _exists("command-center/receipts/TST-0347.json"),
        "base_overall": base_adj["overall_verdict"],
        "rows": rows,
        "unfalsifiable_ids": unfalsifiable,
        "decorative_ids": unfalsifiable,
        "condition_13_pr_only": {
            "verdict": c13["verdict"],
            "as_written_satisfiable": False,
            "canary_succeeded_forced_true": True,
            "still_false": c13["verdict"] == "FALSE",
            "class": "UNSATISFIABLE-AS-WRITTEN",
        },
    }


def run_required_tests() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    # 1. all 21 rows, no omission
    live = load_live_world()
    live_rows = evaluate_all(live)
    ids = [r["condition_id"] for r in live_rows]
    texts = [r["condition_text"] for r in live_rows]
    probes = [r["probe"]["command"] for r in live_rows]
    verdicts_ok = all(r["verdict"] in {"TRUE", "FALSE", "NOT-CHECKED", "DECORATIVE"} for r in live_rows)
    t1_ok = ids == list(range(1, 22)) and len(set(texts)) == 21 and len(set(probes)) == 21 and verdicts_ok
    tests.append(
        {
            "id": "test_all_21_conditions_appear_as_rows_with_no_omission",
            "requirement": "all 21 conditions appear as rows with verdict and probe, no omission",
            "verdict": "PASS" if t1_ok else "FAIL",
            "evidence": (
                f"ids={ids} unique_texts={len(set(texts))} unique_probes={len(set(probes))} "
                f"verdicts_ok={verdicts_ok}"
            ),
        }
    )

    # 2. a single NOT-CHECKED forces PROGRAM-INCOMPLETE
    complete = evaluate_all(all_true_world(), timestamp="2026-08-24T00:00:10Z")
    complete_adj = adjudicate(complete)
    nc_world = clone_world(all_true_world(), required_tests_red=None)
    nc_rows = evaluate_all(nc_world, timestamp="2026-08-24T00:00:11Z")
    nc_adj = adjudicate(nc_rows)
    t2_ok = (
        complete_adj["overall_verdict"] == "PROGRAM-COMPLETE"
        and nc_rows[3]["verdict"] == "NOT-CHECKED"
        and nc_adj["overall_verdict"] == "PROGRAM-INCOMPLETE"
        and nc_adj["blocking_class"] == "NOT-CHECKED"
        and 4 in nc_adj["blocking_condition_ids"]
        and " --condition 4" in nc_adj["named_missing_probe"]
    )
    tests.append(
        {
            "id": "test_a_single_NOT_CHECKED_forces_PROGRAM_INCOMPLETE",
            "requirement": "20 TRUE + 1 NOT-CHECKED must not report the program complete",
            "verdict": "PASS" if t2_ok else "FAIL",
            "evidence": (
                f"all-true={complete_adj['overall_verdict']} "
                f"nc_c4={nc_rows[3]['verdict']} overall={nc_adj['overall_verdict']} "
                f"class={nc_adj.get('blocking_class')} ids={nc_adj.get('blocking_condition_ids')} "
                f"probe={nc_adj.get('named_missing_probe')}"
            ),
        }
    )

    # 3. planted false on condition 4 flips overall
    planted = clone_world(all_true_world(), required_tests_red=("required-test-red",))
    planted_rows = evaluate_all(planted, timestamp="2026-08-24T00:00:12Z")
    planted_adj = adjudicate(planted_rows)
    t3_ok = (
        complete_adj["overall_verdict"] == "PROGRAM-COMPLETE"
        and planted_rows[3]["verdict"] == "FALSE"
        and planted_adj["overall_verdict"] != complete_adj["overall_verdict"]
        and planted_adj["overall_verdict"] == "PROGRAM-INCOMPLETE"
        and planted_adj["blocking_class"] == "FALSE"
        and 4 in planted_adj["blocking_condition_ids"]
    )
    tests.append(
        {
            "id": "planted_false_condition_4_flips_overall",
            "requirement": "force condition 4 (no required test is red) false -> overall verdict must flip",
            "verdict": "PASS" if t3_ok else "FAIL",
            "evidence": (
                f"before={complete_adj['overall_verdict']} after={planted_adj['overall_verdict']} "
                f"c4={planted_rows[3]['verdict']} class={planted_adj.get('blocking_class')}"
            ),
        }
    )

    # 4. condition 13 resolution explicit under PR-ONLY
    c13 = next(r for r in live_rows if r["condition_id"] == 13)
    res = c13.get("pr_only") or {}
    t4_ok = (
        c13["verdict"] == "FALSE"
        and res.get("skipped") is False
        and res.get("as_written_satisfiable") is False
        and res.get("release_mode") == "PR-ONLY"
        and "PR-ONLY" in (c13.get("reason") or "")
    )
    tests.append(
        {
            "id": "test_condition_13_resolution_is_explicit_under_PR_ONLY",
            "requirement": "condition 13 carries its PR-ONLY resolution or is reported FALSE, never skipped",
            "verdict": "PASS" if t4_ok else "FAIL",
            "evidence": (
                f"verdict={c13['verdict']} skipped={res.get('skipped')} "
                f"satisfiable={res.get('as_written_satisfiable')} "
                f"mode={res.get('release_mode')} reason={c13.get('reason')}"
            ),
        }
    )
    return tests


def live_bundle() -> dict[str, Any]:
    ts = utc_now()
    world = load_live_world()
    rows = evaluate_all(world, timestamp=ts)
    adj = adjudicate(rows)
    tests = run_required_tests()
    fals = falsifiability_table()
    # Apply TST-0347 rule: unfalsifiable -> DECORATIVE, never TRUE.
    decorative = set(fals.get("decorative_ids") or [])
    if decorative:
        for r in rows:
            if r["condition_id"] in decorative and r["verdict"] == "TRUE":
                r["verdict"] = "DECORATIVE"
                r["reason"] = (
                    (r.get("reason") or "")
                    + " | TST-0347-stand-in: unfalsifiable, rewritten DECORATIVE"
                )
        adj = adjudicate(rows)
    c13 = next(r for r in rows if r["condition_id"] == 13)
    return {
        "timestamp": ts,
        "world": {
            "kind": world["kind"],
            "work_unit_count": world["work_unit_count"],
            "work_unit_unique": world["work_unit_unique"],
            "work_units_meta_count": world["work_units_meta_count"],
            "work_units_meta_target": world["work_units_meta_target"],
            "work_units_meta_shortfall": world["work_units_meta_shortfall"],
            "release_mode": world["release_mode"],
            "present": world["present"],
            "workflows": world["workflows"],
            "scanner_hits": world["scanner_hits"],
        },
        "rows": rows,
        "adjudication": adj,
        "tests": tests,
        "falsifiability": fals,
        "condition_13_resolution": {
            "release_mode": (c13.get("pr_only") or {}).get("release_mode", world["release_mode"]),
            "as_written_satisfiable": bool(
                (c13.get("pr_only") or {}).get("as_written_satisfiable", False)
            ),
            "skipped": bool((c13.get("pr_only") or {}).get("skipped", False)),
            "verdict": c13["verdict"],
            "justification": c13.get("reason") or "",
            "default_if_unanswered": (c13.get("pr_only") or {}).get(
                "default_if_unanswered", ""
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        tests = run_required_tests()
        failed = [t for t in tests if t["verdict"] != "PASS"]
        print(json.dumps({"tests": tests, "failed": len(failed)}, indent=2, sort_keys=True))
        if failed:
            print("FAILED:SYN-0043-self-test")
            return 1
        print("SUCCESS:SYN-0043-self-test all four required tests PASS")
        return 0
    if args.condition:
        if args.condition < 1 or args.condition > 21:
            print("FAILED:SYN-0043 condition id out of range")
            return 2
        world = load_live_world()
        row = eval_condition(args.condition, clone_world(world, timestamp=utc_now()))
        print(row["probe"]["output_tail"])
        print(
            f"condition={args.condition} verdict={row['verdict']} "
            f"line={row['spec_line']}"
        )
        print(f"SUCCESS:SYN-0043-condition-{args.condition}")
        return 0
    bundle = live_bundle()
    if args.json or args.all:
        slim = {
            "overall": bundle["adjudication"],
            "counts": bundle["adjudication"].get("counts"),
            "rows": [
                {
                    "condition_id": r["condition_id"],
                    "verdict": r["verdict"],
                    "spec_line": r["spec_line"],
                    "reason": r["reason"],
                }
                for r in bundle["rows"]
            ],
        }
        print(json.dumps(slim, indent=2, sort_keys=True))
    adj = bundle["adjudication"]
    print(
        f"overall={adj['overall_verdict']} class={adj['blocking_class']} "
        f"counts={adj.get('counts')}"
    )
    print("SUCCESS:SYN-0043-evaluate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
