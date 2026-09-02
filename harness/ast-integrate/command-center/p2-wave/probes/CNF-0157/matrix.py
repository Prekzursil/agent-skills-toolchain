#!/usr/bin/env python3
"""Claim x client reproduction matrix, live + adapter-fixture surfaces."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Iterable

import adapters as A
import clients as C

SURFACES = ("live-client", "adapter-fixture")
DISABLE_CLIENT = "claude-code"
BOTH_STATES_CLAIM = "mcp-adapter"
LOUD_CLIENT = "mcp-generic"
LOUD_CAPABILITY = "plugin"


def _cell(
    *,
    client_id: str,
    claim_id: str,
    surface: str,
    verdict: str,
    observed_behaviour: str,
    artifact: str,
    client_version: str | None,
    version_source: str,
    prerequisite: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": f"{surface}:{client_id}:{claim_id}",
        "client_id": client_id,
        "claim_id": claim_id,
        "surface": surface,
        "verdict": verdict,
        "observed_behaviour": observed_behaviour,
        "artifact": artifact,
        "client_version": client_version,
        "version_source": version_source,
        "prerequisite": prerequisite,
    }
    if extra:
        row.update(extra)
    return row


def live_cells(discovery: dict[str, Any]) -> list[dict[str, Any]]:
    cells = []
    plugin = discovery["plugin_package"]
    for spec in C.DECLARED_CLIENTS:
        live = C.client_by_id(discovery, spec["id"])
        for claim_id, _title in C.CLAIMS:
            if not live["installed"]:
                cells.append(
                    _cell(
                        client_id=spec["id"],
                        claim_id=claim_id,
                        surface="live-client",
                        verdict="NOT-CHECKED",
                        observed_behaviour=(
                            "Declared client is not installed on this Linux worktree; "
                            "no in-client observation. Not folded into a pass."
                        ),
                        artifact="live-discovery:PATH",
                        client_version=None,
                        version_source="not-installed",
                        prerequisite=live["install_prerequisite"],
                        extra={"installed": False},
                    )
                )
                continue
            # Installed client is still NOT-CHECKED for plugin/hook/skill/mcp
            # claims unless we observed in-client load. A Python toolkit at
            # tools/plugin is not that observation. Version comes from the CLI.
            missing = plugin.get("production_paths_absent") or []
            prereq = (
                "In-client plugin load was not observed. "
                f"Loadable production markers absent: {'; '.join(missing[:3]) or 'n/a'}. "
                "Do not treat installer-exit, binary-presence, or tools/plugin "
                "Python-toolkit files as in-client proof."
            )
            cells.append(
                _cell(
                    client_id=spec["id"],
                    claim_id=claim_id,
                    surface="live-client",
                    verdict="NOT-CHECKED",
                    observed_behaviour=(
                        f"Client binary present ({live.get('executable')}); "
                        "in-client plugin/hook/skill/MCP-adapter behaviour was not "
                        "observed because the production package is absent."
                    ),
                    artifact=" ".join(live.get("version_command") or [])
                    or (live.get("executable") or "live-discovery"),
                    client_version=live.get("version"),
                    version_source=live["version_source"],
                    prerequisite=prereq,
                    extra={"installed": True},
                )
            )
    return cells


def fixture_cells(
    *,
    disabled: Iterable[str] = (),
    work: Path | None = None,
) -> list[dict[str, Any]]:
    cells = []
    own_tmp = None
    if work is None:
        own_tmp = tempfile.TemporaryDirectory(prefix="cnf0157-fix-")
        work = Path(own_tmp.name)
    try:
        for spec in C.DECLARED_CLIENTS:
            for claim_id, _title in C.CLAIMS:
                result = A.exercise_claim(
                    spec["id"],
                    claim_id,
                    disabled=disabled,
                    work=work,
                )
                cells.append(
                    _cell(
                        client_id=spec["id"],
                        claim_id=claim_id,
                        surface="adapter-fixture",
                        verdict=result["verdict"],
                        observed_behaviour=result["observed_behaviour"],
                        artifact=str(result.get("artifact") or A.plugin_root() / "plugin.json"),
                        client_version=f"adapter-fixture/{spec['id']}",
                        version_source="adapter-fixture",
                        prerequisite=None,
                        extra={
                            "hooks_run": result.get("hooks_run", 0),
                            "capability_named_in_error": result.get(
                                "capability_named_in_error", False
                            ),
                            "silent_degradation": bool(result.get("silent_degradation")),
                        },
                    )
                )
    finally:
        if own_tmp is not None:
            own_tmp.cleanup()
    return cells


def known_broken_control() -> dict[str, Any]:
    baseline = fixture_cells()
    broken = fixture_cells(disabled=(DISABLE_CLIENT,))
    base_by = {c["id"]: c for c in baseline}
    red_ids = [
        c["id"]
        for c in broken
        if c["verdict"] == A.VERDICT_RED
    ]
    unexpected_red = [
        c["id"]
        for c in broken
        if c["verdict"] == A.VERDICT_RED and not c["id"].startswith(
            f"adapter-fixture:{DISABLE_CLIENT}:"
        )
    ]
    expected_red = [
        f"adapter-fixture:{DISABLE_CLIENT}:{claim}" for claim, _ in C.CLAIMS
    ]
    others_unchanged = []
    for cell in broken:
        if cell["client_id"] == DISABLE_CLIENT:
            continue
        prev = base_by[cell["id"]]
        others_unchanged.append(
            {
                "id": cell["id"],
                "same_verdict": cell["verdict"] == prev["verdict"],
            }
        )
    ok = (
        set(red_ids) == set(expected_red)
        and not unexpected_red
        and all(row["same_verdict"] for row in others_unchanged)
    )
    return {
        "id": "known-broken-disable-one-adapter",
        "disabled_client": DISABLE_CLIENT,
        "pass": ok,
        "red_cell_ids": red_ids,
        "expected_red_cell_ids": expected_red,
        "unexpected_red_cell_ids": unexpected_red,
        "others_unchanged": all(row["same_verdict"] for row in others_unchanged),
        "note": (
            "Disabling the claude-code adapter turns exactly that client's "
            "fixture cells RED; other clients keep their baseline verdicts."
        ),
    }


def loud_degradation_test() -> dict[str, Any]:
    forced = A.force_unsupported(LOUD_CLIENT, LOUD_CAPABILITY)
    exercised = A.exercise_claim(LOUD_CLIENT, LOUD_CAPABILITY, work=Path("."))
    ok = (
        forced["verdict"] == A.VERDICT_LOUD
        and forced["capability_named_in_error"] is True
        and LOUD_CAPABILITY in (forced["error"] or "")
        and LOUD_CLIENT in (forced["error"] or "")
        and exercised["verdict"] == A.VERDICT_LOUD
        and exercised["capability_named_in_error"] is True
    )
    return {
        "id": "loud-degradation-unsupported-capability",
        "client_id": LOUD_CLIENT,
        "capability": LOUD_CAPABILITY,
        "pass": ok,
        "forced_verdict": forced["verdict"],
        "forced_error": forced["error"],
        "exercised_verdict": exercised["verdict"],
        "capability_named_in_error": forced["capability_named_in_error"],
        "note": (
            "Unsupported plugin capability on mcp-generic must fail explicitly "
            "and name the capability; silence is the defect."
        ),
    }


def both_states_test() -> dict[str, Any]:
    enabled = fixture_cells()
    disabled = fixture_cells(disabled=(DISABLE_CLIENT,))
    claim = BOTH_STATES_CLAIM
    green_enabled = [
        c
        for c in enabled
        if c["claim_id"] == claim and c["verdict"] == A.VERDICT_REPRODUCES
    ]
    all_clients = [spec["id"] for spec in C.DECLARED_CLIENTS]
    green_ids = {c["client_id"] for c in green_enabled}
    disabled_red = [
        c
        for c in disabled
        if c["claim_id"] == claim
        and c["client_id"] == DISABLE_CLIENT
        and c["verdict"] == A.VERDICT_RED
    ]
    ok = green_ids == set(all_clients) and len(disabled_red) == 1
    return {
        "id": "both-states-mcp-adapter",
        "capability": claim,
        "pass": ok,
        "enabled_green_clients": sorted(green_ids),
        "expected_clients": all_clients,
        "disabled_client_turns_red": len(disabled_red) == 1,
        "note": (
            "mcp-adapter is fully supported on every fixture adapter: all four "
            "green when enabled; claude-code turns RED when that adapter is disabled."
        ),
    }


def version_capture_test(discovery: dict[str, Any], cells: list[dict[str, Any]]) -> dict[str, Any]:
    live = [c for c in cells if c["surface"] == "live-client"]
    doc_leak = [
        c["id"]
        for c in live
        if c["version_source"] in C.FORBIDDEN_VERSION_SOURCES
    ]
    uninstalled_with_version = [
        c["id"]
        for c in live
        if c["version_source"] == "not-installed" and c.get("client_version")
    ]
    installed_ok = True
    for row in discovery["clients"]:
        if row["installed"] and row["version_source"] not in {
            "client-cli",
            "client-cli-unreadable",
        }:
            installed_ok = False
        if (not row["installed"]) and row["version_source"] != "not-installed":
            installed_ok = False
        if (not row["installed"]) and row.get("version"):
            installed_ok = False
    fixture_ok = all(
        c["version_source"] == "adapter-fixture"
        and str(c.get("client_version") or "").startswith("adapter-fixture/")
        for c in cells
        if c["surface"] == "adapter-fixture"
    )
    ok = (
        not doc_leak
        and not uninstalled_with_version
        and installed_ok
        and fixture_ok
        and discovery["catalog"]["tokens_present"]
    )
    return {
        "id": "version-capture-from-client",
        "pass": ok,
        "documentation_leak_cell_ids": doc_leak,
        "uninstalled_with_version_cell_ids": uninstalled_with_version,
        "installed_declared": discovery["installed_declared"],
        "missing_declared": discovery["missing_declared"],
        "note": (
            "Each live version is read from the client binary or recorded "
            "not-installed. Adapter-fixture versions are labelled adapter-fixture/ "
            "and are never presented as a live CLI string."
        ),
    }


def skill_router_control() -> dict[str, Any]:
    rows = [A.skill_router_plant(spec["id"]) for spec in C.DECLARED_CLIENTS]
    # Claude routes the plant (proves detector can see selection). Codex/agy
    # fail-silent on the plant (spec 11330). mcp-generic loud-unsupports skill
    # so the plant is not a skill-router observation there.
    claude = next(r for r in rows if r["client_id"] == "claude-code")
    codex = next(r for r in rows if r["client_id"] == "codex-cli")
    ok = (
        claude["verdict"] == A.VERDICT_REPRODUCES
        and claude["selected"] is True
        and codex["verdict"] == A.VERDICT_SILENT
        and codex["on_disk"] is True
        and codex["selected"] is False
    )
    return {
        "id": "skill-router-11330",
        "pass": ok,
        "rows": rows,
        "note": (
            "Both-states for spec:11330: Claude Code fixture selects the planted "
            "installed skill; Codex fixture leaves it unselected with no error."
        ),
    }


def interchangeability_verdict(cells: list[dict[str, Any]]) -> dict[str, Any]:
    fixture = [c for c in cells if c["surface"] == "adapter-fixture"]
    silent = [c["id"] for c in fixture if c["verdict"] == A.VERDICT_SILENT]
    loud = [c["id"] for c in fixture if c["verdict"] == A.VERDICT_LOUD]
    return {
        "verdict": "REFUTED",
        "reason": (
            "Full interchangeability is REFUTED. Codex×hook fails silently "
            "(empty success — the defect named by spec:10983). mcp-generic "
            "loudly refuses plugin/hook/skill. Live declared clients are "
            "NOT-CHECKED, not inferred green."
        ),
        "fail_silent_cell_ids": silent,
        "loud_degrade_cell_ids": loud,
    }


def run_matrix() -> dict[str, Any]:
    discovery = C.discover()
    live = live_cells(discovery)
    fixture = fixture_cells()
    cells = live + fixture
    tests = {
        "known_broken": known_broken_control(),
        "loud_degradation": loud_degradation_test(),
        "both_states": both_states_test(),
        "version_capture": version_capture_test(discovery, cells),
        "skill_router_11330": skill_router_control(),
    }
    return {
        "discovery": discovery,
        "cells": cells,
        "tests": tests,
        "interchangeability": interchangeability_verdict(cells),
        "cell_count": len(cells),
        "live_cell_count": len(live),
        "fixture_cell_count": len(fixture),
    }
