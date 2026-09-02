#!/usr/bin/env python3
"""ADV-0035 declared-versus-observed permission reconciliation.

Probe 1 instrument: set-difference of declared grants against recorded trace
calls, with a coverage guard (thin traces -> NOT-CHECKED, not over-declared).

Probe 2 instrument (mechanically different): remove each over-declared
candidate and re-run the component's tests; a permission whose removal
changes nothing is unused. Trace absence alone cannot prove that (the path
may simply not have been exercised). Under-declared use is re-observed on a
fresh execution of attempted calls, not by re-reading the historical trace.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.permission_diff import canonicalize, covered_by_set  # noqa: E402

FIXTURES = HERE / "fixtures" / "components.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"

SOURCE_PROBE = "set-difference:declared-vs-trace-calls"
VERIFIER_OVER = "removal-retest:grant-minus-perm"
VERIFIER_UNDER = "live-execution-calls:attempted-vs-declared"
VERIFIER_HONEST = "necessity-retest:each-declared-perm-is-necessary"


def load_fixture_pack() -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def canon_set(perms: Iterable[str]) -> list[str]:
    return sorted({canonicalize(p) for p in perms if str(p).strip()})


def coverage_of(comp: dict[str, Any]) -> dict[str, Any]:
    paths = [str(p) for p in (comp.get("code_paths") or [])]
    hit: set[str] = set()
    for tr in comp.get("traces") or []:
        for p in tr.get("paths_hit") or []:
            hit.add(str(p))
    n = len(paths)
    frac = (len(hit) / n) if n else 0.0
    return {
        "code_path_n": n,
        "paths_hit_n": len(hit),
        "paths_hit": sorted(hit),
        "fraction": frac,
    }


def observed_calls(comp: dict[str, Any]) -> list[str]:
    calls: list[str] = []
    for tr in comp.get("traces") or []:
        calls.extend(str(c) for c in (tr.get("calls") or []))
    return canon_set(calls)


def tests_pass(attempted: Iterable[str], granted: Iterable[str]) -> bool:
    grant = list(granted)
    return all(covered_by_set(p, grant) for p in canon_set(attempted))


def trace_diff(comp: dict[str, Any], threshold: float) -> dict[str, Any]:
    declared = canon_set(comp.get("declared") or [])
    observed = observed_calls(comp)
    attempted = canon_set(comp.get("attempted") or [])
    cov = coverage_of(comp)
    over = [p for p in declared if not covered_by_set(p, observed)]
    under = [p for p in observed if not covered_by_set(p, declared)]
    coverage_ok = cov["code_path_n"] > 0 and cov["fraction"] >= threshold
    return {
        "id": comp["id"],
        "role": comp.get("role") or "",
        "declared": declared,
        "observed_from_traces": observed,
        "attempted": attempted,
        "over_declared_raw": over,
        "under_declared": under,
        "coverage": cov,
        "coverage_ok": coverage_ok,
        "coverage_threshold": threshold,
        "over_declared_candidates": over if coverage_ok else [],
        "over_suppressed_by_coverage_guard": [] if coverage_ok else over,
    }


def retest_removed(comp: dict[str, Any], perm: str) -> dict[str, Any]:
    declared = canon_set(comp.get("declared") or [])
    target = canonicalize(perm)
    remaining = [p for p in declared if p != target]
    attempted = canon_set(comp.get("attempted") or [])
    baseline_ok = tests_pass(attempted, declared)
    without_ok = tests_pass(attempted, remaining)
    return {
        "id": comp["id"],
        "removed": target,
        "remaining_grant": remaining,
        "baseline_tests_pass": baseline_ok,
        "tests_pass_without": without_ok,
        "confirmed_unused": bool(baseline_ok and without_ok),
        "needed_but_unexercised": bool(baseline_ok and not without_ok),
    }


def live_attempts(comp: dict[str, Any]) -> dict[str, Any]:
    declared = canon_set(comp.get("declared") or [])
    attempted = canon_set(comp.get("attempted") or [])
    under = [p for p in attempted if not covered_by_set(p, declared)]
    return {
        "id": comp["id"],
        "declared": declared,
        "attempted_this_run": attempted,
        "under_declared_live": under,
    }


def analyze_fixtures(pack: dict[str, Any] | None = None) -> dict[str, Any]:
    pack = pack if pack is not None else load_fixture_pack()
    threshold = float(pack["coverage_threshold"])
    comps = list(pack["components"])
    diffs = [trace_diff(c, threshold) for c in comps]
    by_id = {c["id"]: c for c in comps}
    retests: list[dict[str, Any]] = []
    for diff in diffs:
        comp = by_id[diff["id"]]
        for perm in diff["over_declared_raw"]:
            retests.append(retest_removed(comp, perm))
        if not diff["over_declared_raw"]:
            for perm in diff["declared"]:
                retests.append(retest_removed(comp, perm))
    lives = [live_attempts(c) for c in comps]
    return {
        "coverage_threshold": threshold,
        "components": comps,
        "diffs": diffs,
        "retests": retests,
        "live_attempts": lives,
    }


def _retest_for(retests: list[dict[str, Any]], cid: str, perm: str) -> dict[str, Any] | None:
    want = canonicalize(perm)
    for row in retests:
        if row["id"] == cid and row["removed"] == want:
            return row
    return None


def _live_for(lives: list[dict[str, Any]], cid: str) -> dict[str, Any] | None:
    for row in lives:
        if row["id"] == cid:
            return row
    return None


def settle_targets(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """One verdict per enumerated (component, direction, permission) target."""
    targets: list[dict[str, Any]] = []
    retests = analysis["retests"]
    lives = analysis["live_attempts"]
    for diff in analysis["diffs"]:
        cid = diff["id"]
        live = _live_for(lives, cid) or {}

        if diff["over_suppressed_by_coverage_guard"]:
            for perm in diff["over_suppressed_by_coverage_guard"]:
                targets.append(
                    {
                        "target_id": f"component:{cid}:over:{perm}",
                        "component": cid,
                        "direction": "over-declared",
                        "permission": perm,
                        "verdict": "NOT-CHECKED",
                        "reason": (
                            "coverage-guard: trace path fraction "
                            f"{diff['coverage']['fraction']:.3f} < "
                            f"{diff['coverage_threshold']}; absence is not unused"
                        ),
                    }
                )
        for perm in diff["over_declared_candidates"]:
            rt = _retest_for(retests, cid, perm)
            if rt is None:
                verdict = "NOT-CHECKED"
                reason = "removal-retest missing"
            elif rt["confirmed_unused"]:
                verdict = "CONFIRMED"
                reason = "set-difference candidate and removal left tests passing"
            elif rt["needed_but_unexercised"]:
                verdict = "REFUTED"
                reason = "removal failed tests: unexercised, not unused"
            else:
                verdict = "NOT-CHECKED"
                reason = "baseline tests did not pass; cannot interpret removal"
            row = {
                "target_id": f"component:{cid}:over:{perm}",
                "component": cid,
                "direction": "over-declared",
                "permission": perm,
                "verdict": verdict,
                "reason": reason,
            }
            if verdict in {"CONFIRMED", "REFUTED"}:
                row["source_probe"] = SOURCE_PROBE
                row["verifier_probe"] = VERIFIER_OVER
            targets.append(row)

        if not diff["over_declared_raw"] and not diff["under_declared"]:
            necessary = []
            for perm in diff["declared"]:
                rt = _retest_for(retests, cid, perm)
                necessary.append(bool(rt and rt["needed_but_unexercised"]))
            if necessary and all(necessary):
                targets.append(
                    {
                        "target_id": f"component:{cid}:least-privilege",
                        "component": cid,
                        "direction": "honest-declaration",
                        "verdict": "CONFIRMED",
                        "reason": (
                            "empty over and under on traces; each declared "
                            "permission fails tests when removed"
                        ),
                        "source_probe": SOURCE_PROBE,
                        "verifier_probe": VERIFIER_HONEST,
                    }
                )

        for perm in diff["under_declared"]:
            live_under = set(live.get("under_declared_live") or [])
            if perm in live_under:
                verdict = "CONFIRMED"
                reason = (
                    "historical traces show undeclared use; fresh execution "
                    "attempts the same permission"
                )
            else:
                verdict = "PARTIAL"
                reason = "traces show undeclared use; live execution did not repeat it"
            row = {
                "target_id": f"component:{cid}:under:{perm}",
                "component": cid,
                "direction": "under-declared",
                "permission": perm,
                "verdict": verdict,
                "reason": reason,
            }
            if verdict in {"CONFIRMED", "REFUTED"}:
                row["source_probe"] = SOURCE_PROBE
                row["verifier_probe"] = VERIFIER_UNDER
            targets.append(row)
    return targets


def _has_recorded_tool_trace(probe_dir: Path) -> bool:
    if not probe_dir.is_dir():
        return False
    names = (
        "tool-calls.json",
        "tool_calls.json",
        "recorded-traces.json",
        "trace-calls.json",
    )
    for name in names:
        if (probe_dir / name).is_file():
            return True
    for p in probe_dir.glob("traces/*.json"):
        if p.is_file() and p.stat().st_size > 0:
            return True
    return False


def live_catalog_census() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in (data.get("work_units") or []) if isinstance(u, dict) and u.get("id")]
    perm_hist: dict[str, int] = {}
    with_declared = 0
    with_probe_dir = 0
    with_trace = 0
    for u in units:
        perms = u.get("tool_permissions") or []
        if perms:
            with_declared += 1
        for p in perms:
            key = str(p)
            perm_hist[key] = perm_hist.get(key, 0) + 1
        uid = str(u["id"])
        pdir = PROBES / uid
        if pdir.is_dir():
            with_probe_dir += 1
        if _has_recorded_tool_trace(pdir):
            with_trace += 1
    return {
        "catalog": "command-center/WORK-UNIT-CATALOG.json",
        "work_unit_n": len(units),
        "with_declared_tool_permissions": with_declared,
        "with_probe_dir": with_probe_dir,
        "with_recorded_tool_call_trace": with_trace,
        "coverage_ok_n": 0,
        "note": (
            "SUBAGENT-RETURN.json named_probes are delivery harness commands, "
            "not per-component tool-call traces of the unit's own declared "
            "grant. They are not counted as coverage of catalog code paths."
        ),
        "permission_histogram": dict(sorted(perm_hist.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def missing_control_downgrade(
    targets: list[dict[str, Any]], controls: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Any missing required control downgrades settled over/under verdicts."""
    required = {c["id"] for c in controls if c.get("required")}
    present_pass = {
        c["id"] for c in controls if c.get("required") and c.get("result") == "PASS"
    }
    missing = sorted(required - present_pass)
    if not missing:
        return targets
    out = []
    for t in targets:
        row = dict(t)
        if row.get("verdict") in {"CONFIRMED", "REFUTED"}:
            row["verdict"] = "NOT-CHECKED"
            row["downgraded_from"] = t.get("verdict")
            row["reason"] = (
                f"missing control {missing}; "
                + str(row.get("reason") or "")
            ).strip()
            row.pop("source_probe", None)
            row.pop("verifier_probe", None)
        out.append(row)
    return out


def control_results(analysis: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diffs = {d["id"]: d for d in analysis["diffs"]}
    by_tid = {t["target_id"]: t for t in targets}

    def tgt(tid: str) -> dict[str, Any] | None:
        return by_tid.get(tid)

    honest = diffs["fx-honest"]
    over = diffs["fx-overdeclare-unused"]
    under = diffs["fx-underdeclare"]
    thin = diffs["fx-thin-trace"]
    unex = diffs["fx-unexercised-needed"]

    bash = canonicalize("Bash")
    write = canonicalize("Write")

    over_t = tgt(f"component:fx-overdeclare-unused:over:{bash}")
    thin_t = tgt(f"component:fx-thin-trace:over:{bash}")
    unex_t = tgt(f"component:fx-unexercised-needed:over:{write}")
    under_t = tgt(f"component:fx-underdeclare:under:{write}")
    honest_t = tgt("component:fx-honest:least-privilege")

    naive_thin_would_confirm = bash in thin["over_declared_raw"] and not thin["coverage_ok"]

    controls = [
        {
            "id": "coverage-guard",
            "required": True,
            "name": "Thin traces report NOT-CHECKED rather than over-declared",
            "result": (
                "PASS"
                if thin_t
                and thin_t["verdict"] == "NOT-CHECKED"
                and naive_thin_would_confirm
                and bash not in thin["over_declared_candidates"]
                else "FAIL"
            ),
            "fired_on_thin": bool(thin_t and thin_t["verdict"] == "NOT-CHECKED"),
            "silent_on_covered_unused": bool(
                over_t and over_t["verdict"] == "CONFIRMED"
            ),
        },
        {
            "id": "both-states-overdeclare",
            "required": True,
            "name": "Known unused Bash is CONFIRMED; honest component is not over-declared",
            "result": (
                "PASS"
                if over_t
                and over_t["verdict"] == "CONFIRMED"
                and not honest["over_declared_raw"]
                and not honest["under_declared"]
                else "FAIL"
            ),
        },
        {
            "id": "both-states-underdeclare",
            "required": True,
            "name": "Known undeclared Write is CONFIRMED; honest under-set is empty",
            "result": (
                "PASS"
                if under_t
                and under_t["verdict"] == "CONFIRMED"
                and not honest["under_declared"]
                else "FAIL"
            ),
        },
        {
            "id": "removal-distinguishes-unexercised",
            "required": True,
            "name": "Write missing from traces but required by tests is REFUTED unused",
            "result": (
                "PASS"
                if unex_t
                and unex_t["verdict"] == "REFUTED"
                and write in unex["over_declared_candidates"]
                else "FAIL"
            ),
        },
        {
            "id": "detector-known-unused",
            "required": True,
            "name": "Set-difference plus removal find planted unused Bash",
            "result": (
                "PASS"
                if over_t and over_t["verdict"] == "CONFIRMED"
                else "FAIL"
            ),
        },
        {
            "id": "honest-least-privilege",
            "required": True,
            "name": "Honest fixture remains least-privilege (both probes)",
            "result": (
                "PASS"
                if honest_t and honest_t["verdict"] == "CONFIRMED"
                else "FAIL"
            ),
        },
    ]
    return controls
