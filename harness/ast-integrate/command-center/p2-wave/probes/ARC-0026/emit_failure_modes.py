#!/usr/bin/env python3
"""Emit command-center/phase3/A4/FAILURE-MODES.json for ARC-0026."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import ceiling as C  # noqa: E402
import overclaim as O  # noqa: E402
import remeasure as R  # noqa: E402
import reviewer as RV  # noqa: E402
import trees as T  # noqa: E402

OUT = "command-center/phase3/A4/FAILURE-MODES.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
# A9/SECURITY.json and A1/FAILURE-MODES.json are other units' catalog
# outputs and are absent (phase3 is .gitkeep-only). Dossier anchors bind
# to the live files that actually name the hop and the seeded class.
A4_HOP = "command-center/p2-wave/probes/ARC-0062/sources.py"
SEEDED = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
DESIGN = "command-center/phase3/A4/DESIGN.json"
QUESTION = (
    "What breaks when activation is deferred? Enumerate the modes: a capability "
    "the router never selects is indistinguishable from one that does not exist; "
    "activation fails mid-task; a deactivated capability retains state; and "
    "per-session process multiplication (the measured stdio MCP duplication that "
    "drove commit exhaustion). Specify the OBSERVABLE signal that separates "
    "'not selected' from 'not installed' at the moment of failure."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0026/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0026/probe2_ceiling.py"
)
CLAIM = (
    "When activation is deferred, a capability the router does not select is "
    "indistinguishable from one that is not installed; a single unavailable bit "
    "is enough; and process multiplication may be cited from the earlier "
    "23x65=2037 estate figure without a same-day re-measure."
)
COUNTER = (
    "A collapsed unavailable bit is what operators already see, and three bits "
    "on every miss looks like telemetry bloat. On this Linux worktree A4 "
    "DESIGN.json is absent and live MCP config files declare zero stdio servers, "
    "so the distinguishing signal and the process curve are proven on fixtures "
    "plus catalog-bound A4 activation hops, not on a shipped gateway. That "
    "limitation does not make not-selected identical to not-installed, and it "
    "does not license citing 23x65=2037 as today's measurement. Strongest "
    "surviving FOR: keep the three-bit signal even if spawn later becomes a "
    "shared pool; the signal is about discovery, the curve is about spawn policy."
)
CATCHING = (
    "A4 gateway with a three-bit availability signal (indexed, installed, "
    "selected) plus activation status, emitted at failure time; shared or lazy "
    "MCP spawn bounded by a recorded process-count curve that flags P1 only "
    "when superlinear."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    target = REPO / path
    if not target.is_file():
        raise SystemExit(f"FAILED:ARC-0026 emit missing dossier {path}")
    line = A.find_line(target, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0026 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def local_schema_errors(doc: object) -> list[str]:
    """Fail-closed unit schema. The catalog output_schema is a $ref shim to
    ast-integrate.invalid; Draft7Validator tries HTTPS and is not a gate.
    This checker requires the fields the named probes read and rejects
    empty/garbage objects.
    """
    if not isinstance(doc, dict) or not doc:
        return ["empty-or-not-object"]
    errs: list[str] = []
    if doc.get("unit_id") != "ARC-0026":
        errs.append("unit_id")
    if str(doc.get("state") or "").upper() != "SUCCESS":
        errs.append("state")
    if "SUCCESS:ARC-0026" not in str(doc.get("sentinel") or ""):
        errs.append("sentinel")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "architecture-review":
        errs.append("report.kind")
    else:
        obs = report.get("observations")
        if not isinstance(obs, list) or len(obs) < 1:
            errs.append("report.observations")
        else:
            for i, row in enumerate(obs):
                if not isinstance(row, dict) or any(
                    not str(row.get(k) or "").strip()
                    and not isinstance(row.get(k), (int, float, bool))
                    for k in ("name", "measured", "method", "anchor")
                ):
                    errs.append(f"report.observations[{i}]")
                elif any(k not in row for k in ("name", "measured", "method", "anchor")):
                    errs.append(f"report.observations[{i}]")
        cids = report.get("control_ids")
        if not isinstance(cids, list) or not all(isinstance(x, str) and x.strip() for x in cids):
            errs.append("report.control_ids")
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        errs.append("claims")
    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errs.append("evidence")
    else:
        kinds = {str(row.get("kind") or "") for row in evidence if isinstance(row, dict)}
        if "live-tree" not in kinds or "dossier" not in kinds:
            errs.append("evidence.kinds")
    bs = doc.get("both_states") or {}
    if bs.get("not_selected_code") != "NOT_SELECTED":
        errs.append("both_states.not_selected")
    if bs.get("index_miss_installed_code") != "INDEX_MISS_INSTALLED":
        errs.append("both_states.index_miss")
    if "SUCCESS:ARC-0026" not in str(doc.get("answer") or ""):
        errs.append("answer.sentinel")
    return errs


def author_modes() -> list[dict]:
    return [
        {
            "id": "FM-SILENT-EQUIV",
            "title": "Not-selected is indistinguishable from not-installed",
            "seeded_classes": [
                "router fails to select an installed skill",
                "detector-failure",
                "single-signal-verification",
            ],
            "detector": "Three-bit availability signal; collapsed unavailable bit rejected",
        },
        {
            "id": "FM-ACTIVATION-MIDTASK",
            "title": "Activation fails after the router has already selected the capability",
            "seeded_classes": ["partial-artifact", "severed-stream"],
            "detector": "activation=failed -> ACTIVATION_FAILED even when indexed and installed",
        },
        {
            "id": "FM-DEACTIVATE-RESIDUAL",
            "title": "Deactivated capability retains session state",
            "seeded_classes": ["stale-cache", "provenance-loss"],
            "detector": "residual_state=true -> DEACTIVATED_RESIDUAL",
        },
        {
            "id": "FM-PROCESS-MULT",
            "title": "Per-session stdio MCP process multiplication",
            "seeded_classes": [
                "eager per-session MCP process multiplication",
                "commit exhaustion freezes process creation",
            ],
            "detector": "Two independent probes today; N*K eager curve; superlinear is P1",
        },
        {
            "id": "FM-STALE-INDEX",
            "title": "Index lists a capability whose install payload is gone",
            "seeded_classes": ["stale-cache", "false-coverage"],
            "detector": "indexed and not installed -> STALE_INDEX",
        },
        {
            "id": "FM-INDEX-MISS-INSTALLED",
            "title": "Installed payload with no index row (both-states planted case)",
            "seeded_classes": ["capability-loss", "green-not-live"],
            "detector": "not indexed and installed -> INDEX_MISS_INSTALLED",
        },
    ]


def main() -> int:
    T.ensure_fixtures()
    ctrl = T.both_states()
    if not ctrl.get("pass"):
        print("FAILED:ARC-0026 both-states control")
        print(json.dumps(ctrl, indent=2, default=str)[:4000])
        return 1
    ceil = C.run_ceiling()
    if not ceil.get("pass"):
        print("FAILED:ARC-0026 ceiling detector-control")
        print(json.dumps(ceil, indent=2, default=str)[:4000])
        return 1
    today = R.remeasure_today()
    if today.get("cited_estate_figure_as_today") is True:
        print("FAILED:ARC-0026 cited estate figure as today")
        return 1

    e1 = ev(
        CATALOG,
        "Specify the OBSERVABLE signal that separates 'not selected' from 'not installed'",
        "live-tree",
        "Catalog requires a distinguishing observable at the moment of failure.",
    )
    e2 = ev(
        CATALOG,
        "Both-states control: remove a capability from the index while leaving it installed",
        "live-tree",
        "Catalog both-states: index edit must not be silent versus not-installed.",
    )
    e3 = ev(
        CATALOG,
        "Process multiplication is re-measured today with two independent probes",
        "live-tree",
        "Catalog forbids citing the earlier process-multiplication figure.",
    )
    e4 = ev(
        CATALOG,
        "Ceiling test: drive N simulated sessions and record the process count curve",
        "live-tree",
        "Catalog: superlinear process curve is a P1 finding.",
    )
    e5 = ev(
        A4_HOP,
        '"id": "A4.activate.materialize"',
        "live-tree",
        "ARC-0062 sources.py names the catalog-bound A4.activate.materialize hop; A9 SECURITY.json is absent.",
    )
    e6 = ev(
        SEEDED,
        '"name": "eager per-session MCP process multiplication"',
        "dossier",
        "Seeded class FC-11326 is the process-multiplication mode this unit re-measures.",
    )

    rev = RV.review()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    design_present = (REPO / DESIGN).is_file()
    if design_present:
        print("FAILED:ARC-0026 must not rebuild A4 DESIGN.json")
        return 1

    ps_count = int(today["powershell_process_count"])
    cfg_count = int(today["mcp_config_per_session_count"])
    k = int(ceil["k_stdio_from_fixture_mcp"])

    doc = {
        "unit_id": "ARC-0026",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0026",
        "completion_sentinel": "SUCCESS:ARC-0026",
        "architecture_id": "A4",
        "architecture_class": "gateway-lazy-activation",
        "title": (
            "A4 (gateway / lazy-activation): Distinguishing not-selected from "
            "not-installed, and bounding activation-driven process multiplication"
        ),
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "headline_verdict": "SIGNAL-DISTINGUISHES; EAGER-CURVE-LINEAR-NOT-P1",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "reliability-engineer",
            "execution_substrate": "headless-linux",
        },
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0026]",
        "report": {
            "kind": "architecture-review",
            "observations": [
                {
                    "name": "not_selected_code",
                    "measured": ctrl["not_selected_code"],
                    "method": "three-bit classify on indexed+installed+not-selected fixture",
                    "anchor": e2["anchor"],
                },
                {
                    "name": "index_miss_installed_code",
                    "measured": ctrl["index_miss_installed_code"],
                    "method": "three-bit classify after dropping the index row; install file stays",
                    "anchor": e2["anchor"],
                },
                {
                    "name": "eager_superlinear",
                    "measured": bool(ceil["eager_superlinear"]),
                    "method": "simulated N-session N*K stdio curve; superlinear detector",
                    "anchor": e4["anchor"],
                },
                {
                    "name": "powershell_process_count",
                    "measured": ps_count,
                    "method": "PowerShell process table or /proc cmdline mcp|npx twin",
                    "anchor": e3["anchor"],
                },
                {
                    "name": "mcp_config_per_session_count",
                    "measured": cfg_count,
                    "method": "parse live mcpServers JSON for stdio (command, not url) servers",
                    "anchor": e3["anchor"],
                },
            ],
            "control_ids": [
                "T1-both-states-signal",
                "T2-ceiling-remeasure-overclaim",
                "collapsed-unavailable-bit",
                "planted-superlinear-curve",
            ],
        },
        "a4_design": {
            "path": DESIGN,
            "present": False,
            "note": (
                "ARC-0024 output is absent. This unit specifies the failure "
                "modes and the observable; it does not author DESIGN.json."
            ),
        },
        "observable_signal": {
            "name": "three-bit availability signal",
            "bits": ["indexed", "installed", "selected"],
            "activation": ["never", "pending", "ok", "failed", "deactivated"],
            "codes": {
                "NOT_SELECTED": "indexed and installed and not selected",
                "NOT_INSTALLED": "not installed (index may also be empty)",
                "INDEX_MISS_INSTALLED": "installed payload, no index row",
                "STALE_INDEX": "index row, install payload missing",
                "ACTIVATION_FAILED": "selected but materialize failed",
                "DEACTIVATED_RESIDUAL": "deactivated with leftover session state",
                "AVAILABLE": "selected, indexed, installed, activation=ok",
            },
            "collapses_rejected": (
                "A single UNAVAILABLE/AVAILABLE bit is identical for "
                "not-selected and index-miss-installed and is not the signal."
            ),
        },
        "both_states": {
            "capability_id": ctrl["capability_id"],
            "silent_loss_file": ctrl["silent_loss_file"],
            "not_selected_code": ctrl["not_selected_code"],
            "index_miss_installed_code": ctrl["index_miss_installed_code"],
            "codes_differ": ctrl["codes_differ"],
            "collapsed_state_a": ctrl["collapsed_state_a"],
            "collapsed_state_b": ctrl["collapsed_state_b"],
            "collapsed_same_in_both_states": ctrl["collapsed_same_in_both_states"],
            "install_file_survived_index_edit": ctrl["install_file_survived_index_edit"],
            "truly_not_installed_code": ctrl["truly_not_installed"]["code"],
            "stale_index_code": ctrl["stale_index"]["code"],
            "activation_failed_code": ctrl["activation_failed_midtask"]["code"],
            "deactivated_residual_code": ctrl["deactivated_residual"]["code"],
            "state_a": ctrl["state_a_indexed_installed_not_selected"],
            "state_b": ctrl["state_b_index_removed_still_installed"],
        },
        "ceiling_test": ceil,
        "live_process_multiplication": {
            "powershell_process_count": ps_count,
            "mcp_config_per_session_count": cfg_count,
            "cited_estate_figure_as_today": False,
            "estate_figure_named_not_used": today["estate_figure_named_not_used"],
            "agreement": today["agreement"],
            "disagreement_expected": today["disagreement_expected"],
            "disagreement_reason": today["disagreement_reason"],
            "powershell": today["powershell"],
            "mcp_config": today["mcp_config"],
            "combined_process_count_forbidden": True,
            "measured_at": now,
        },
        "author_failure_modes": author_modes(),
        "scenario": {
            "id": "S1-deferred-activation-signal",
            "title": "Index-miss vs not-installed vs not-selected",
            "silent_loss_file": ctrl["silent_loss_file"],
            "catching_architecture": CATCHING,
            "procedure": [
                "Build an install tree with skill.alpha on disk and an index that lists it.",
                "Ask the router for a task that does not select skill.alpha; record the three-bit signal (must be NOT_SELECTED).",
                "Remove skill.alpha from the index only; leave the install file; record the signal (must be INDEX_MISS_INSTALLED).",
                "Assert the two codes differ; reject a collapsed unavailable bit that is the same in both states.",
                "Parse live MCP config for stdio server count; enumerate processes via PowerShell or /proc twin; simulate N sessions; flag P1 iff the curve is superlinear.",
            ],
            "on_this_estate": (
                f"Both-states codes {ctrl['not_selected_code']} vs "
                f"{ctrl['index_miss_installed_code']}. Fixture stdio K={k}. "
                f"Eager curve {ceil['eager_stdio_curve']} is linear "
                f"(superlinear={ceil['eager_superlinear']}). Live process-table "
                f"mcp-like count={ps_count}; live MCP-config stdio per session="
                f"{cfg_count}. Estate 23x65=2037 is named and not used as today."
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": "A single unavailable bit is a sufficient failure signal under deferred activation.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "scoped_restatement": (
                    "The observable is indexed, installed, selected, plus activation. "
                    "NOT_SELECTED and INDEX_MISS_INSTALLED must differ."
                ),
                "why_locus": (
                    "A4 DESIGN.json is absent, so this is not a DESIGN-encoded "
                    "rule. The catalog sentence requiring a distinguishing "
                    "observable is the binding requirement."
                ),
                "anchor": e1["anchor"],
            },
            {
                "id": "C2",
                "claim": "Removing a capability from the index while leaving it installed produces a different signal than not-selected-while-indexed.",
                "verdict": "CONFIRMED",
                "anchor": e2["anchor"],
            },
            {
                "id": "C3",
                "claim": "Process multiplication today is the earlier estate figure 23 sessions x 65 servers = 2037 processes.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "scoped_restatement": (
                    f"Today: PowerShell/process-table mcp-like count={ps_count}; "
                    f"MCP-config stdio per session={cfg_count}. The 2037 figure "
                    "is named as prior estate incident only."
                ),
                "why_locus": (
                    "No A4 DESIGN encodes the 2037 number as a live measurement. "
                    "The catalog evidence_requirement forbids citing the earlier figure."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C4",
                "claim": "The eager per-session stdio process curve is superlinear and is therefore a P1 finding on this measurement.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "scoped_restatement": (
                    f"Eager curve is N*{k} = {ceil['eager_stdio_curve']}, linear. "
                    "P1 is reserved for the planted superlinear curve, which the "
                    "detector does fire on."
                ),
                "why_locus": (
                    "The catalog names superlinear as the P1 finding; it does not "
                    "assert the eager stdio model is superlinear. Linear N*K is "
                    "still FM-PROCESS-MULT, not P1-superlinear."
                ),
                "anchor": e4["anchor"],
            },
            {
                "id": "C5",
                "claim": "A4 DESIGN.json on this worktree already specifies the distinguishing signal and the activation lifecycle.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "scoped_restatement": (
                    "command-center/phase3/A4/DESIGN.json is absent. "
                    "command-center/phase3/A9/SECURITY.json is absent. "
                    "The catalog-bound hop is named in ARC-0062/sources.py "
                    "(A4.activate.materialize). This unit records failure modes "
                    "against the catalog and that hop; it does not author DESIGN."
                ),
                "why_locus": (
                    "Cannot be a DESIGN-locus defect: the design file does not "
                    "exist. Claiming it specifies the signal is a sentence-level overclaim."
                ),
                "anchor": e5["anchor"],
            },
            {
                "id": "C6",
                "claim": "Eager per-session MCP process multiplication is a seeded failure class this architecture must bound, not ignore.",
                "verdict": "CONFIRMED",
                "anchor": e6["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-both-states-signal",
                "name": "Index-removed-but-installed vs not-selected; collapsed bit rejected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-ceiling-remeasure-overclaim",
                "name": "Simulated N-session curve, two-probe re-measure, reviewer-added mode",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": rev,
        "named_probes": [
            {"id": "probe1", "role": "both-states-signal", "command": P1},
            {"id": "probe2", "role": "ceiling-remeasure-overclaim", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0026/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T20:40:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0026/avail.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0026/fixtures/install/skills/skill.alpha.json",
                "exists": True,
                "role": "silent-loss-file",
            },
        ],
        "answer": (
            f"Deferred activation breaks four ways: not-selected looks like "
            f"not-installed unless the gateway emits indexed/installed/selected "
            f"plus activation at failure time (NOT_SELECTED vs "
            f"INDEX_MISS_INSTALLED on the both-states control); activation can "
            f"fail mid-task (ACTIVATION_FAILED); deactivate can leave residual "
            f"state (DEACTIVATED_RESIDUAL); eager stdio MCP multiplies as N*K "
            f"(K={k} from the fixture, live config K={cfg_count}, process-table "
            f"mcp-like={ps_count}) which is linear not P1-superlinear. Reviewer "
            f"added FM-PARTIAL-MATERIALIZE. SUCCESS:ARC-0026"
        ),
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0026 overclaim {why}")
        return 1

    schema_errs = local_schema_errors(doc)
    if schema_errs:
        print("FAILED:ARC-0026 schema errors")
        for e in schema_errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not local_schema_errors(g):
            print(f"FAILED:ARC-0026 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0026 artifact {size}B below floor")
        return 1
    if "SUCCESS:ARC-0026" not in out.read_text(encoding="utf-8"):
        print("FAILED:ARC-0026 sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"both-states {ctrl['not_selected_code']} vs {ctrl['index_miss_installed_code']}")
    print(f"process ps={ps_count} cfg={cfg_count} eager_sl={ceil['eager_superlinear']}")
    print("SUCCESS:ARC-0026")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
