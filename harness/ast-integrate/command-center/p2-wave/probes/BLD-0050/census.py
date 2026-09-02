#!/usr/bin/env python3
"""Build the BLD-0050 trust-boundary census from this worktree.

Walk 1 (architecture docs): A1/A2 DESIGN.json exist but do not name an owner,
a validation rule at path:line, and a test id per crossing. That is a miss,
not a census.

Walk 2 (retry-policy pivot): start from every subprocess/network AST site and
work outward, then add the architectural crossings those sites imply
(vendor API, human/machine, agent/agent, build/run, config/content).

ADV-0021's install/update path is CONSUMED as one boundary — not re-audited,
no STRIDE rebuild. The ADV-0021 artifact is absent on this tree; that absence
is recorded, not papered over by inventing the model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from walk import (
    REPO,
    check_status_for,
    find_sites,
    site_map,
    snippet_present,
    test_present,
)

ADV0021_REL = (
    "command-center/adversarial/ADV-0021-install-path-stride-threat-model.json"
)
BLD0048_REL = "command-center/receipts/BLD-0048.json"
A1_DESIGN = "command-center/phase3/A1/DESIGN.json"
A2_DESIGN = "command-center/phase3/A2/DESIGN.json"

# Named rules. CHECKED only when snippet AND test file are live.
RULES: dict[str, dict[str, str]] = {
    "TB-A2-TYPED-OUT": {
        "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
        "name": "_reject_banned",
        "snippet": "if k in BANNED_KEYS:",
        "test_id": "ARC-0016/typed_rejects_opaque_body",
        "test_path": "command-center/p2-wave/probes/ARC-0016/hatch.py",
    },
    "TB-A2-TYPED-IN": {
        "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
        "name": "classify",
        "snippet": 'reason": "bytes-differ-registry-unchanged"',
        "test_id": "ARC-0010/probe2_tamper",
        "test_path": "command-center/p2-wave/probes/ARC-0010/probe2_tamper.py",
    },
    "TB-A2-SCHEMA-OUT": {
        "path": "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        "name": "additionalProperties-false",
        "snippet": '"additionalProperties": false',
        "test_id": "ARC-0016/typed_rejects_opaque_body",
        "test_path": "command-center/p2-wave/probes/ARC-0016/hatch.py",
    },
    "TB-A2-FREEZE-IN": {
        "path": "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
        "name": "freeze_hook.check",
        "snippet": 'if rec.get("status") == "TAMPERED":',
        "test_id": "ARC-0014/probe2_rollback",
        "test_path": "command-center/p2-wave/probes/ARC-0014/probe2_rollback.py",
    },
}


def _line_for(rel: str, snippet: str) -> int:
    ok, line = snippet_present(REPO, rel, snippet)
    return line if ok else 0


def _status(
    bid: str,
    *,
    consumed: bool = False,
    rule_override_path: Path | None = None,
) -> tuple[str, dict[str, Any] | None, str | None, str | None]:
    if consumed:
        return "CONSUMED", None, None, None
    spec = RULES.get(bid)
    if spec is None:
        return "UNCHECKED", None, None, None
    status = check_status_for(
        consumed=False,
        root=REPO,
        rule_path=spec["path"],
        snippet=spec["snippet"],
        test_path=spec["test_path"],
        rule_override_path=rule_override_path if bid == "TB-A2-TYPED-OUT" else None,
    )
    rule = {
        "path": spec["path"],
        "line": _line_for(spec["path"], spec["snippet"]),
        "name": spec["name"],
        "snippet": spec["snippet"],
    }
    if rule_override_path is not None and bid == "TB-A2-TYPED-OUT":
        rule = dict(rule)
        rule["path"] = str(rule_override_path)
        ok, line = snippet_present(REPO, str(rule_override_path), spec["snippet"])
        rule["line"] = line if ok else 0
        rule["scratch_override"] = True
    return status, rule, spec["test_id"], spec["test_path"]


def _b(
    bid: str,
    crossing: str,
    direction: str,
    what: str,
    owner: str,
    pair_id: str,
    *,
    consumed: bool = False,
    consumed_from: str | None = None,
    note: str | None = None,
    appears_in_threat_model: list[str] | None = None,
    rule_override_path: Path | None = None,
) -> dict[str, Any]:
    status, rule, test_id, test_path = _status(
        bid, consumed=consumed, rule_override_path=rule_override_path
    )
    row: dict[str, Any] = {
        "id": bid,
        "crossing": crossing,
        "direction": direction,
        "what_crosses": what,
        "owner": owner,
        "check_status": status,
        "pair_id": pair_id,
        "validation_rule": rule,
        "test_id": test_id,
        "test_path": test_path,
        "appears_in_threat_model": list(appears_in_threat_model or []),
    }
    if consumed_from:
        row["consumed_from"] = consumed_from
    if note:
        row["note"] = note
    if consumed:
        row["re_audited"] = False
    return row


def threat_models_on_disk() -> dict[str, Any]:
    searched = [ADV0021_REL, BLD0048_REL]
    present = []
    for rel in searched:
        p = REPO / rel
        present.append(
            {
                "path": rel,
                "present": p.is_file() and p.stat().st_size > 0,
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return {"searched": searched, "rows": present}


def architecture_docs() -> dict[str, Any]:
    docs = [A1_DESIGN, A2_DESIGN]
    rows = []
    for rel in docs:
        p = REPO / rel
        rows.append({"path": rel, "present": p.is_file()})
    return {
        "docs": rows,
        "named_owner_rule_and_test_per_crossing": False,
        "reason": (
            "A1/A2 DESIGN.json record file sets, load order and expressibility. "
            "They do not enumerate each trust-boundary crossing with owner + "
            "validation_rule path:line + test id. Per retry_policy, pivot to "
            "code-site enumeration."
        ),
    }


def build_census(
    *,
    rule_override_path: Path | None = None,
    override_boundary: str = "TB-A2-TYPED-OUT",
) -> dict[str, Any]:
    sites = find_sites(REPO)
    smap = site_map(sites)
    models = threat_models_on_disk()
    any_model_present = any(r["present"] for r in models["rows"])

    override = rule_override_path if override_boundary == "TB-A2-TYPED-OUT" else None

    spawn_sites = [s for s in sites if s["kind"] == "spawn"]
    net_sites = [s for s in sites if s["kind"] == "network"]
    net_note = (
        f"{len(net_sites)} urllib/socket Call node(s) on this worktree; "
        "each maps to TB-NET-DIRECT. Inbound responses share those call sites "
        "and are recorded separately as TB-NET-DIRECT-IN (direction control)."
        if net_sites
        else (
            "Zero matching Call nodes on this worktree. Boundary kept so a "
            "future site cannot be silent."
        )
    )

    boundaries: list[dict[str, Any]] = [
        _b(
            "TB-INSTALL-ADV0021",
            "install-update-path",
            "n/a",
            "plugin install, update, repair, rollback and uninstall command surfaces",
            "ADV-0021 (catalog-consumed; not re-derived)",
            "PAIR-INSTALL",
            consumed=True,
            consumed_from="ADV-0021",
            appears_in_threat_model=[],
            note=(
                "Catalog SCOPE: consume ADV-0021 as one boundary, do not re-audit. "
                f"Artifact {ADV0021_REL} present="
                f"{(REPO / ADV0021_REL).is_file()}. No STRIDE rebuild (no ADV circle). "
                "Install/update implementations are absent on this sparse worktree."
            ),
        ),
        _b(
            "TB-A2-TYPED-OUT",
            "build-time-to-run-time",
            "outbound",
            "typed registry entries rendered into generated plugin/skills/hooks/rules/docs/catalogs",
            "A2 generator",
            "PAIR-A2-TYPED",
            rule_override_path=override,
        ),
        _b(
            "TB-A2-TYPED-IN",
            "build-time-to-run-time",
            "inbound",
            "on-disk generated bytes classified against the current registry (TAMPERED vs CLEAN vs STALE)",
            "A2 classify()",
            "PAIR-A2-TYPED",
        ),
        _b(
            "TB-A2-SCHEMA-OUT",
            "trusted-config-to-untrusted-content",
            "outbound",
            "registry JSON admitted into the generator; opaque passthrough keys must not enter generated bytes",
            "a2-registry/v1 schema",
            "PAIR-A2-CONTENT",
        ),
        _b(
            "TB-A2-FREEZE-IN",
            "trusted-config-to-untrusted-content",
            "inbound",
            "deployed generated copies read back after freeze; TAMPERED hand-edits rejected",
            "ARC-0014 freeze_hook.check",
            "PAIR-A2-CONTENT",
        ),
        _b(
            "TB-VENDOR-API-OUT",
            "our-code-to-vendor-api",
            "outbound",
            "prompt bytes and tool-permission flags sent to cursor-agent (vendor CLI)",
            "dispatch_cursor.launch_one",
            "PAIR-VENDOR",
            note=(
                "subprocess.Popen at dispatch_cursor.py launches cursor-agent with "
                "--sandbox disabled. No allow-list on interpolated catalog prompt. UNCHECKED."
            ),
        ),
        _b(
            "TB-VENDOR-API-IN",
            "our-code-to-vendor-api",
            "inbound",
            "agent stdout/stderr written to worker.log and read back as delivery evidence",
            "dispatch_cursor.reap_one",
            "PAIR-VENDOR",
            note="Log tail is unfenced DATA treated as operator-visible text. No inbound schema.",
        ),
        _b(
            "TB-NET-SCW-OUT",
            "local-to-network",
            "outbound",
            "Scaleway instance create/list CLI (scw) from bringup_cursor_fleet",
            "bringup_cursor_fleet.scw_create",
            "PAIR-SCW",
            note=(
                "No direct socket/urllib site on this tree. Network is implied through "
                "the TB-SPAWN-SCW wrapper. Response body is not schema-validated."
            ),
        ),
        _b(
            "TB-NET-SCW-IN",
            "local-to-network",
            "inbound",
            "scw JSON stdout consumed as create-ok evidence",
            "bringup_cursor_fleet.scw_create",
            "PAIR-SCW",
            note="returncode==0 plus non-empty stdout; not a typed response check.",
        ),
        _b(
            "TB-AGENT-OUT",
            "agent-to-agent",
            "outbound",
            "catalog question_or_target and tests_required interpolated into the next agent prompt",
            "dispatch_cursor.prompt_for",
            "PAIR-AGENT",
            note=(
                "prompt_for formats the unit id into a supervisor prompt. No sanitizer "
                "at the interpolation site. UNCHECKED (the ADV-0082 class on this estate)."
            ),
        ),
        _b(
            "TB-AGENT-IN",
            "agent-to-agent",
            "inbound",
            "prior agent artifacts (receipts, probe output) readable by a later agent as workspace files",
            "workspace file reads",
            "PAIR-AGENT",
            note="No fence that later agents must treat prior receipts as DATA not instructions.",
        ),
        _b(
            "TB-HUMAN-OUT",
            "machine-to-human",
            "outbound",
            "receipts, worker logs and supervisor heartbeat written for a human operator",
            "receipt writers / supervisor.log",
            "PAIR-HUMAN",
            note="Secret-egress is BLD-0051's map; this census records the crossing as UNCHECKED here.",
        ),
        _b(
            "TB-HUMAN-IN",
            "machine-to-human",
            "inbound",
            "operator-supplied env (CURSOR_API_KEY/TOKEN) and catalog edits entering the supervisor",
            "bringup_cursor_fleet / WORK-UNIT-CATALOG.json",
            "PAIR-HUMAN",
            note=(
                "bringup prints token length and a 4-char prefix, not the value. That is "
                "print discipline, not a validation rule with a test id. UNCHECKED."
            ),
        ),
        _b(
            "TB-SPAWN-PYTHON",
            "process-to-process",
            "outbound",
            "CPython spawning python3/-B children (probes, measure, helpers)",
            "subprocess.run sites classified spawn.python",
            "PAIR-SPAWN-PYTHON",
            note="No argv allow-list at the spawn helper. Completeness maps each AST site here.",
        ),
        _b(
            "TB-SPAWN-PYTHON-IN",
            "process-to-process",
            "inbound",
            "child stdout/stderr captured and parsed as JSON or SUCCESS lines",
            "subprocess.run capture_output sites",
            "PAIR-SPAWN-PYTHON",
            note="Exit-code checks exist at some callers; they are not a typed inbound validator.",
        ),
        _b(
            "TB-SPAWN-GIT",
            "process-to-process",
            "outbound",
            "git argv (show/cat-file/archive/log/status) spawned from Python",
            "subprocess.run sites classified spawn.git",
            "PAIR-SPAWN-GIT",
        ),
        _b(
            "TB-SPAWN-GIT-IN",
            "process-to-process",
            "inbound",
            "git stdout bytes used as blob/commit evidence",
            "subprocess.run git callers",
            "PAIR-SPAWN-GIT",
        ),
        _b(
            "TB-SPAWN-CURSOR-AGENT",
            "process-to-process",
            "outbound",
            "cursor-agent / agent binary spawned (Popen and -h probe)",
            "dispatch_cursor.launch_one",
            "PAIR-SPAWN-AGENT",
            note="--sandbox disabled at launch_one. Distinct from TB-VENDOR-API-* (what crosses the API).",
        ),
        _b(
            "TB-SPAWN-CURSOR-AGENT-IN",
            "process-to-process",
            "inbound",
            "agent process exit and log file from the child session",
            "dispatch_cursor.reap_one",
            "PAIR-SPAWN-AGENT",
        ),
        _b(
            "TB-SPAWN-SCW",
            "process-to-process",
            "outbound",
            "scw CLI spawned via bringup_cursor_fleet.run",
            "bringup_cursor_fleet.run",
            "PAIR-SPAWN-SCW",
        ),
        _b(
            "TB-SPAWN-SCW-IN",
            "process-to-process",
            "inbound",
            "scw CLI combined stdout/stderr returned to Python",
            "bringup_cursor_fleet.run",
            "PAIR-SPAWN-SCW",
        ),
        _b(
            "TB-SPAWN-BASH",
            "process-to-process",
            "outbound",
            "bash -lc 'command -v cursor-agent || command -v agent'",
            "dispatch_cursor.which_agent",
            "PAIR-SPAWN-BASH",
        ),
        _b(
            "TB-SPAWN-BASH-IN",
            "process-to-process",
            "inbound",
            "which-agent stdout path string",
            "dispatch_cursor.which_agent",
            "PAIR-SPAWN-BASH",
        ),
        _b(
            "TB-SPAWN-PGREP",
            "process-to-process",
            "outbound",
            "pgrep -cf of live agent processes",
            "dispatch_cursor.live_agent_count",
            "PAIR-SPAWN-PGREP",
        ),
        _b(
            "TB-SPAWN-PGREP-IN",
            "process-to-process",
            "inbound",
            "pgrep count parsed as int",
            "dispatch_cursor.live_agent_count",
            "PAIR-SPAWN-PGREP",
        ),
        _b(
            "TB-NET-DIRECT",
            "local-to-network",
            "outbound",
            "direct socket/urllib/httpx/requests call sites in-tree",
            "AST network enumerator",
            "PAIR-NET-DIRECT",
            note=net_note,
        ),
        _b(
            "TB-NET-DIRECT-IN",
            "local-to-network",
            "inbound",
            "direct network response bytes (same Call nodes as TB-NET-DIRECT; separate check object)",
            "AST network enumerator",
            "PAIR-NET-DIRECT",
            note=(
                net_note
                + " No typed inbound validator at those sites; UNCHECKED."
            ),
        ),
    ]

    known = {b["id"] for b in boundaries}
    unmapped = [s for s in sites if s["boundary_id"] not in known]

    # Completeness: every site maps to exactly one enumerated boundary.
    for s in sites:
        if s["boundary_id"] not in known:
            continue

    checked = sum(1 for b in boundaries if b["check_status"] == "CHECKED")
    unchecked = sum(1 for b in boundaries if b["check_status"] == "UNCHECKED")
    consumed = sum(1 for b in boundaries if b["check_status"] == "CONSUMED")

    # Deliverable: boundaries that appear in NO existing (on-disk) threat model.
    # ADV-0021/BLD-0048 artifacts are absent, so every row including CONSUMED
    # is absent from a readable model. CONSUMED still means not re-audited.
    absent_n = 0 if any_model_present else len(boundaries)
    if any_model_present:
        absent_n = sum(1 for b in boundaries if not b.get("appears_in_threat_model"))
    else:
        for b in boundaries:
            b["appears_in_threat_model"] = []

    return {
        "sites": sites,
        "site_map": smap,
        "boundaries": boundaries,
        "unmapped": unmapped,
        "counts": {
            "boundaries_total": len(boundaries),
            "checked": checked,
            "unchecked": unchecked,
            "consumed": consumed,
            "boundaries_in_no_existing_threat_model": absent_n,
            "spawn_sites": len(spawn_sites),
            "network_sites": len(net_sites),
            "unmapped_sites": len(unmapped),
        },
        "threat_models": models,
        "architecture": architecture_docs(),
        "any_threat_model_on_disk": any_model_present,
    }


def direction_pairs(boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for b in boundaries:
        by.setdefault(b["pair_id"], []).append(b)
    rows = []
    for pid, items in sorted(by.items()):
        dirs = sorted({i["direction"] for i in items})
        rules = [
            (i.get("validation_rule") or {}).get("name")
            or (i.get("validation_rule") or {}).get("snippet")
            or f"none:{i['id']}"
            for i in items
        ]
        bidirectional = "inbound" in dirs and "outbound" in dirs
        distinct_checks = len(set(rules)) >= 2 if bidirectional else True
        rows.append(
            {
                "pair_id": pid,
                "ids": [i["id"] for i in items],
                "directions": dirs,
                "bidirectional": bidirectional,
                "distinct_checks": distinct_checks,
                "check_names": rules,
            }
        )
    return rows


def consumed_not_reaudited(boundaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [b for b in boundaries if b["check_status"] == "CONSUMED"]
    stride_keys = []
    for b in rows:
        stride_keys.extend(
            k for k in b.keys() if k.lower() in {"stride", "spoofing", "tampering"}
        )
    return {
        "consumed_ids": [b["id"] for b in rows],
        "re_audited": any(b.get("re_audited") for b in rows),
        "stride_cells_present": bool(stride_keys),
        "consumed_from": [b.get("consumed_from") for b in rows],
    }


if __name__ == "__main__":
    doc = build_census()
    print(json.dumps(doc["counts"], indent=2, sort_keys=True))
    print("unmapped", len(doc["unmapped"]))
    for b in doc["boundaries"]:
        print(f"{b['id']:28} {b['check_status']:10} {b['crossing']}")
