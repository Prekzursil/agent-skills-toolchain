#!/usr/bin/env python
"""Work-unit authorization census + gate (defect D2).

Two jobs, deliberately in one runnable file so the before/after numbers and the
both-states control come from the SAME command:

1. **CENSUS** - read the catalog OFF DISK and count the authorization surface:
   approval declarations, ``Task`` holders, ``mcp__`` holders, and wildcard tokens split
   by wildcard POSITION (identity = a broadening, scope = a narrowing).
2. **GATE** - run SEM-008..SEM-011 over the real corpus and, separately, over a battery of
   SEEDED violations. Each rule must FIRE on its seed and be SILENT on the corpus. A rule
   that is silent in both states measures nothing
   (``rules/common/single-signal-verification.md`` 3b).

Fails closed: an unreadable catalog, an empty ``work_units`` array, or a rule that does not
fire on its own seed is a FAILURE, never "nothing found -> pass"
(``rules/common/ci-hygiene.md`` section 1).

The BEFORE half of the census is recomputed from the pinned commit's catalog object rather
than quoted from a console log - ``*.log`` is gitignored here, so a log is evidence that does
not survive the commit.

Usage::

    python platform/lib/wfdsl/authz_census.py
    python platform/lib/wfdsl/authz_census.py --json command-center/D2-WORKUNIT-AUTHZ.json
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # allow `python platform/lib/wfdsl/authz_census.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from wfdsl import semantics  # type: ignore[no-redef]
else:
    from . import semantics

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
AUTHZ_RULES = ("SEM-008", "SEM-009", "SEM-010", "SEM-011")

#: The commit whose catalog IS the BEFORE state for defect D2 - main as pinned for this wave,
#: before any authorization fix landed. Re-deriving the before/after delta from a committed
#: object rather than from a log file keeps both halves reproducible: `*.log` is gitignored,
#: so a log is evidence that cannot survive the commit.
BASELINE_REV = "0aa6f8fa1ee8852c18616c0cd590665136976f10"
BASELINE_PATH = "command-center/WORK-UNIT-CATALOG.json"


class AuthzCensusError(RuntimeError):
    """The catalog could not be read, or held no units. Never degrade to a pass.

    Deliberately distinct from ``ci/skill_surface_census.py``'s ``CensusError``: that one
    guards a content-addressed skill-root comparison in another tree and is not importable
    from here. Sharing an exception across two unrelated domains buys nothing.
    """


# ------------------------------------------------------------------------------ census


def census(catalog: dict[str, Any]) -> dict[str, Any]:
    units = catalog.get("work_units") or []
    if not units:
        raise AuthzCensusError(
            "catalog holds no work_units - refusing to report a clean census"
        )

    def toks(u: dict[str, Any]) -> list[semantics.ToolToken]:
        return [
            semantics.parse_tool_token(t) for t in (u.get("tool_permissions") or [])
        ]

    def approved(u: dict[str, Any]) -> bool:
        return u.get("owner_approval_required") is True

    task = [u for u in units if any(t.base == "Task" for t in toks(u))]
    mcp = [u for u in units if any(t.is_mcp for t in toks(u))]
    id_wc = [u for u in units if any(t.identity_wildcard for t in toks(u))]
    scope_only_wc = [
        u
        for u in units
        if any(t.scope_wildcard for t in toks(u))
        and not any(t.identity_wildcard for t in toks(u))
    ]
    any_wc = [
        u
        for u in units
        if any("*" in str(t) for t in (u.get("tool_permissions") or []))
    ]
    remote_local = [
        u
        for u in units
        if str(u.get("execution_substrate")) in semantics.REMOTE_SUBSTRATES
        and any(t.base in semantics.SESSION_LOCAL_TOOLS for t in toks(u))
    ]
    return {
        "work_units": len(units),
        "owner_approval_required_true": sum(1 for u in units if approved(u)),
        "hold_Task": len(task),
        "hold_Task_unapproved": sum(1 for u in task if not approved(u)),
        "hold_mcp_token": len(mcp),
        "hold_mcp_token_unapproved": sum(1 for u in mcp if not approved(u)),
        "wildcard_token_any_position": len(any_wc),
        "wildcard_in_token_identity": len(id_wc),
        "wildcard_in_token_identity_unapproved": sum(
            1 for u in id_wc if not approved(u)
        ),
        "wildcard_in_scope_only": len(scope_only_wc),
        "remote_substrate_holding_session_local_tool": len(remote_local),
        "tool_policy_declared": bool(catalog.get("tool_policy")),
        "tool_policy_default": str(
            (catalog.get("tool_policy") or {}).get("default", "")
        ),
        "tool_policy_allow_entries": len(
            (catalog.get("tool_policy") or {}).get("allow", [])
        ),
        "tool_policy_deny_entries": len(
            (catalog.get("tool_policy") or {}).get("deny", [])
        ),
        "tool_policy_require_owner_approval_entries": len(
            (catalog.get("tool_policy") or {}).get("require_owner_approval", [])
        ),
        "offenders": {
            "hold_Task_unapproved": sorted(
                str(u["id"]) for u in task if not approved(u)
            ),
            "wildcard_identity": sorted(str(u["id"]) for u in id_wc),
            "remote_substrate_session_local": sorted(
                str(u["id"]) for u in remote_local
            ),
        },
    }


def baseline_census(rev: str = BASELINE_REV) -> dict[str, Any]:
    """The BEFORE census, re-derived from a committed catalog object.

    Uses ``git cat-file -p <rev>:<path>`` - never ``git archive`` (it applies EOL conversion
    and hands back CRLF on this box) and never the working tree. Degrades to a recorded
    reason rather than a number if the object is unreachable (a shallow CI checkout), because
    an invented baseline is worse than a missing one.
    """
    try:
        out = subprocess.run(
            ["git", "cat-file", "-p", f"{rev}:{BASELINE_PATH}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        before = json.loads(out.stdout.decode("utf-8"))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {
            "rev": rev,
            "available": False,
            "reason": f"NOT-CHECKED: {type(exc).__name__} reading {rev}:{BASELINE_PATH}",
        }
    return {
        "rev": rev,
        "available": True,
        "census": census(before),
        "rules": {
            r.rule: {"checked": r.checked, "violations": len(r.violations)}
            for r in semantics.check_work_unit_authorization(
                before.get("work_units") or [], before.get("tool_policy")
            )
        },
    }


def corpus_rules(catalog: dict[str, Any]) -> dict[str, Any]:
    units = catalog.get("work_units") or []
    results = semantics.check_work_unit_authorization(units, catalog.get("tool_policy"))
    return {r.rule: r.to_json(sample=6) for r in results}


# ------------------------------------------------------------- seeded both-states battery


def _clean_unit() -> dict[str, Any]:
    """A minimal unit that every authorization rule must accept."""
    return {
        "id": "AUZ-0001",
        "execution_substrate": "local-serialized",
        "owner_approval_required": False,
        "tool_permissions": ["Read", "Grep", "Write(command-center/research/**)"],
    }


def _fires(
    rule: str, units: list[dict[str, Any]], policy: dict[str, Any] | None
) -> int:
    hit = next(
        (
            r
            for r in semantics.check_work_unit_authorization(units, policy)
            if r.rule == rule
        ),
        None,
    )
    if hit is None:  # pragma: no cover - would mean the rule id was renamed
        raise AuthzCensusError(
            f"rule {rule} not returned by check_work_unit_authorization"
        )
    return len(hit.violations)


def both_states(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Every rule against a GOOD unit and against a seeded BAD unit, under `policy`."""
    good = _clean_unit()
    seeds: dict[str, tuple[str, dict[str, Any]]] = {
        # The seed MUST name a tool the policy does not list. An earlier version of this
        # seed used mcp__cloud-hub__modal_sandbox_exec, which the corpus legitimately
        # requests and the allowlist therefore permits - so the control read bad=0 and
        # measured nothing. It is kept named here because the failure is the lesson: a
        # seed has to be verified against the live allowlist, not assumed.
        "SEM-008": (
            "requests a tool that is not in tool_policy.allow "
            "(compute_provision rents a GPU; nothing in the catalog asks for it)",
            {**good, "tool_permissions": ["Read", "mcp__cloud-hub__compute_provision"]},
        ),
        "SEM-008-deny": (
            "requests a tool that tool_policy.deny names explicitly",
            {**good, "tool_permissions": ["Read", "mcp__github__merge_pull_request"]},
        ),
        "SEM-009": (
            "holds Task with owner_approval_required false",
            {**good, "tool_permissions": ["Read", "Task"]},
        ),
        "SEM-009-wildcard": (
            "holds an identity wildcard with owner_approval_required false",
            {**good, "tool_permissions": ["Read", "mcp__search-hub__*"]},
        ),
        "SEM-010": (
            "cloud-batch unit holds the session-local AskUserQuestion",
            {
                **good,
                "execution_substrate": "cloud-batch",
                "tool_permissions": ["Read", "AskUserQuestion"],
            },
        ),
        "SEM-011": (
            "mcp token wildcards its tool segment",
            {
                **good,
                "owner_approval_required": True,
                "tool_permissions": ["Read", "mcp__paper-search__*"],
            },
        ),
    }
    rows: dict[str, Any] = {}
    for key, (why, bad) in seeds.items():
        rule = key.split("-deny")[0].split("-wildcard")[0]
        clean_n = _fires(rule, [copy.deepcopy(good)], policy)
        bad_n = _fires(rule, [bad], policy)
        rows[key] = {
            "rule": rule,
            "seed": why,
            "violations_on_clean_unit": clean_n,
            "violations_on_seeded_unit": bad_n,
            "fires_on_bad": bad_n > 0,
            "silent_on_good": clean_n == 0,
            "discriminating": bad_n > 0 and clean_n == 0,
        }

    # The policy must not be loosenable past the hardcoded approval floor: even a policy
    # that says nothing requires approval must still gate Task (APPROVAL_FLOOR_TOOLS).
    loose = {
        "default": "allow",
        "allow": ["Task", "Read"],
        "require_owner_approval": [],
    }
    rows["SEM-009-floor-survives-a-loosened-policy"] = {
        "rule": "SEM-009",
        "seed": "policy loosened to default=allow with an empty require_owner_approval",
        "violations_on_clean_unit": _fires("SEM-009", [_clean_unit()], loose),
        "violations_on_seeded_unit": _fires(
            "SEM-009", [{**good, "tool_permissions": ["Read", "Task"]}], loose
        ),
        "fires_on_bad": True,
        "silent_on_good": True,
        "discriminating": True,
    }
    r = rows["SEM-009-floor-survives-a-loosened-policy"]
    r["fires_on_bad"] = r["violations_on_seeded_unit"] > 0
    r["silent_on_good"] = r["violations_on_clean_unit"] == 0
    r["discriminating"] = r["fires_on_bad"] and r["silent_on_good"]

    # SEM-008 fails CLOSED with no policy at all: the same clean unit must be rejected.
    rows["SEM-008-fails-closed-without-a-policy"] = {
        "rule": "SEM-008",
        "seed": "no tool_policy declared at all; a tool-holding unit must be denied",
        "violations_on_clean_unit": _fires("SEM-008", [_clean_unit()], None),
        "violations_on_seeded_unit": _fires("SEM-008", [_clean_unit()], None),
        "fires_on_bad": _fires("SEM-008", [_clean_unit()], None) > 0,
        "silent_on_good": _fires("SEM-008", [_clean_unit()], policy) == 0,
        "discriminating": _fires("SEM-008", [_clean_unit()], None) > 0
        and _fires("SEM-008", [_clean_unit()], policy) == 0,
    }
    return rows


# --------------------------------------------------------------------------------- main


def build_report(catalog_path: Path) -> dict[str, Any]:
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthzCensusError(f"cannot read {catalog_path}: {exc}") from exc
    report: dict[str, Any] = {
        "artifact": "command-center/D2-WORKUNIT-AUTHZ.json",
        "unit": "defect/d2-workunit-authz",
        "catalog": str(catalog_path),
        "rules": list(AUTHZ_RULES),
        "baseline_before": baseline_census(),
        "census": census(catalog),
        "corpus_rules": corpus_rules(catalog),
        "both_states": both_states(catalog.get("tool_policy")),
    }
    corpus_clean = {
        rule: report["corpus_rules"][rule]["violations"] == 0 for rule in AUTHZ_RULES
    }
    controls_ok = all(row["discriminating"] for row in report["both_states"].values())
    report["corpus_clean"] = corpus_clean
    report["controls_discriminating"] = controls_ok
    report["failures"] = sorted(
        [
            f"{r} has {report['corpus_rules'][r]['violations']} corpus violations"
            for r, ok in corpus_clean.items()
            if not ok
        ]
        + [
            f"control {k} is not discriminating"
            for k, row in report["both_states"].items()
            if not row["discriminating"]
        ]
    )
    report["ok"] = not report["failures"]
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wfdsl.authz_census")
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    try:
        report = build_report(Path(args.catalog))
    except AuthzCensusError as exc:
        print(f"FAILED:d2-workunit-authz {exc}")
        return 1

    c = report["census"]
    print(f"catalog                          : {report['catalog']}")
    print(f"work units                       : {c['work_units']}")
    print(
        f"tool_policy declared             : {c['tool_policy_declared']} "
        f"(default={c['tool_policy_default']!r} allow={c['tool_policy_allow_entries']} "
        f"deny={c['tool_policy_deny_entries']} "
        f"require_approval={c['tool_policy_require_owner_approval_entries']})"
    )
    base = report["baseline_before"]
    print(
        f"baseline (BEFORE) {base['rev'][:8]}   : "
        + ("available" if base["available"] else base.get("reason", "NOT-CHECKED"))
    )
    print("--- census (BEFORE -> AFTER) -------------------------------------------")
    for key in (
        "owner_approval_required_true",
        "hold_Task",
        "hold_Task_unapproved",
        "hold_mcp_token",
        "hold_mcp_token_unapproved",
        "wildcard_token_any_position",
        "wildcard_in_token_identity",
        "wildcard_in_token_identity_unapproved",
        "wildcard_in_scope_only",
        "remote_substrate_holding_session_local_tool",
    ):
        was = base["census"][key] if base["available"] else "?"
        print(f"  {key:<46}{was:>6} ->{c[key]:>6}")
    print("--- rules: BEFORE violations -> AFTER violations -----------------------")
    if base["available"]:
        for rule in AUTHZ_RULES:
            print(
                f"  {rule} before checked={base['rules'][rule]['checked']:<6} "
                f"violations={base['rules'][rule]['violations']}"
            )
    print("--- rules on the real corpus -------------------------------------------")
    for rule in AUTHZ_RULES:
        row = report["corpus_rules"][rule]
        print(
            f"  {rule} {row['severity']:<9} checked={row['checked']:<6} "
            f"violations={row['violations']:<6} {row['description'][:60]}"
        )
        for s in row["sample"][:4]:
            print(f"      {s['subject']}: {s['detail'][:120]}")
    print("--- both-states controls -----------------------------------------------")
    for key, row in report["both_states"].items():
        print(
            f"  {key:<44} bad={row['violations_on_seeded_unit']:<4} "
            f"good={row['violations_on_clean_unit']:<4} "
            f"discriminating={row['discriminating']}"
        )
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"(artifact written: {args.json})")
    print(
        "SUCCESS:d2-workunit-authz"
        if report["ok"]
        else "FAILED:d2-workunit-authz " + "; ".join(report["failures"])
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
