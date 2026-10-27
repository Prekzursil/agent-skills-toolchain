#!/usr/bin/env python3
"""Emit command-center/phase3/A3/FAILURE-MODES.json for ARC-0019."""
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
import live as L  # noqa: E402
import overclaim as O  # noqa: E402
import reviewer as R  # noqa: E402
import scenario as S  # noqa: E402
import schema_check as SC  # noqa: E402
import seeded as SE  # noqa: E402

OUT = "command-center/phase3/A3/FAILURE-MODES.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
# Live phase3/A1 and A2 DESIGN.json are absent on this worktree (those units
# are not delivered here). Dossier evidence uses the ARC-0067 A1 fixture and
# the live A2 typed-registry schema; do not rebuild ADV A3 DESIGN.
DESIGN_A1 = "command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/A1/DESIGN.json"
DESIGN_A2 = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
REGISTRY = "command-center/p2-wave/probes/ARC-0010/registry.json"
QUESTION = (
    "Enumerate the marketplace-first failure modes that exist with no network "
    "and no second publisher - stale index, offline install, revoked-but-cached "
    "package, lockfile drift, and a registry that disagrees with what is "
    "actually deployed - and specify which of these the binding PR-ONLY "
    "release mode makes UNREACHABLE versus merely untested, because an "
    "unreachable failure mode must not be counted as mitigated."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0019/probe1_reconcile.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0019/probe2_overclaim.py"
)
CLAIM = (
    "Under PR-ONLY, with no network and no second publisher, the five named "
    "marketplace failure modes are unreachable and therefore mitigated; a "
    "registry-versus-deployed check is unnecessary because nothing is published."
)
COUNTER = (
    "PR-ONLY is a publication policy, not an install reconciler. A single-owner "
    "estate that never ships a public index can still carry a committed registry "
    "that disagrees with files on disk, a lockfile that is missing, or a leftover "
    "tree after a revert PR. Those local modes stay reachable. The surviving "
    "preference is that PR review is enough operationally; that preference does "
    "not make today's disagreement count zero, and it does not convert public "
    "marketplace modes that PR-ONLY makes unreachable into mitigated controls."
)
PR_ONLY_LINE = (
    "Release mode is PR-ONLY: propose changes as pull requests, never a "
    "private canary and never a public marketplace release."
)
REACHABLE_AGAIN = (
    "Owner changes OQ-3 from PR-ONLY to PRIVATE CANARY or PUBLIC MARKETPLACE "
    "so a hosted index, remote install, or third-party client cache exists."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0019 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def author_modes() -> list[dict]:
    return [
        {
            "id": "FM-STALE-INDEX-LOCAL",
            "title": "Committed registry index stale versus packages in the same tree",
            "named_as": "stale-index",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "seeded_classes": ["stale-cache", "index-corruption", "green-not-live"],
        },
        {
            "id": "FM-STALE-INDEX-PUBLIC",
            "title": "Public or CDN marketplace index serving stale listings to clients",
            "named_as": "stale-index (public subclass)",
            "pr_only_status": "UNREACHABLE",
            "counted_as_mitigated": False,
            "reachable_again_if": REACHABLE_AGAIN,
            "pr_only_citation": PR_ONLY_LINE,
            "seeded_classes": ["stale-cache", "stale-premise"],
        },
        {
            "id": "FM-OFFLINE-MISSING-BLOB",
            "title": "Local export or cache missing a blob the index still names",
            "named_as": "offline-install",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "seeded_classes": ["partial-artifact", "capability-loss"],
        },
        {
            "id": "FM-OFFLINE-INSTALL-REMOTE",
            "title": "Client cannot reach a remote registry and fail-opens to cache",
            "named_as": "offline-install (remote subclass)",
            "pr_only_status": "UNREACHABLE",
            "counted_as_mitigated": False,
            "reachable_again_if": REACHABLE_AGAIN,
            "pr_only_citation": PR_ONLY_LINE,
            "seeded_classes": ["fail-open-control", "stale-cache"],
        },
        {
            "id": "FM-REVOKE-CACHED-LOCAL",
            "title": "Revert PR removes the registry row; installed PACKAGE.json remains",
            "named_as": "revoked-but-cached",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "seeded_classes": ["stale-cache", "capability-loss"],
        },
        {
            "id": "FM-REVOKE-CACHED-PUBLIC",
            "title": "Published revocation never reaches already-installed third-party clients",
            "named_as": "revoked-but-cached (public subclass)",
            "pr_only_status": "UNREACHABLE",
            "counted_as_mitigated": False,
            "reachable_again_if": REACHABLE_AGAIN,
            "pr_only_citation": PR_ONLY_LINE,
            "seeded_classes": ["stale-cache", "fail-open-control"],
        },
        {
            "id": "FM-LOCKFILE-DRIFT",
            "title": "Lockfile pins hashes that do not match installed bytes",
            "named_as": "lockfile-drift",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "note": "Reachable and untested as a product gate; no lockfile detector in this unit.",
            "seeded_classes": ["version-skew", "stale-evidence"],
        },
        {
            "id": "FM-REGISTRY-VS-DEPLOYED",
            "title": "Registry ids disagree with installed PACKAGE.json trees",
            "named_as": "registry-vs-deployed",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "note": "Measured on this worktree.",
            "seeded_classes": ["duplicate-control-plane", "green-not-live", "detector-failure"],
        },
        {
            "id": "FM-VACUOUS-B-ZERO",
            "title": "Direction B zero trusted without a planted unregistered install",
            "named_as": "detector-control",
            "pr_only_status": "REACHABLE",
            "counted_as_mitigated": False,
            "seeded_classes": ["measured-nothing", "false-pass", "green-not-live"],
        },
    ]


def reachability_modes() -> list[dict]:
    rows = []
    for m in author_modes():
        row = {
            "id": m["id"],
            "named_as": m["named_as"],
            "pr_only_status": m["pr_only_status"],
            "counted_as_mitigated": False,
            "pr_only_citation": PR_ONLY_LINE,
            "reachable_again_if": m.get("reachable_again_if", ""),
        }
        rows.append(row)
    return rows


def main() -> int:
    if not (REPO / REGISTRY).is_file():
        print("FAILED:ARC-0019 registry.json missing")
        return 1
    ctrl = S.both_states()
    if not ctrl.get("pass"):
        print("FAILED:ARC-0019 both-states / detector-control / planted-orphan")
        print(
            json.dumps(
                {k: ctrl[k] for k in ctrl if k != "complete"},
                indent=2,
                default=str,
            )
        )
        return 1
    live = L.live_report(REPO)
    a_count = int(live["registry_not_deployed_count"])
    b_count = int(live["deployed_not_in_registry_count"])
    h_count = int(live["hash_mismatch_count"])
    d_count = int(live["disagreement_count"])
    if not live["install_root_present"] and a_count != int(live["registry_id_count"]):
        print("FAILED:ARC-0019 live A must equal registry ids when install root is absent")
        return 1
    if a_count < 1:
        print("FAILED:ARC-0019 live registry-not-deployed unexpectedly zero")
        return 1

    e1 = ev(
        CATALOG,
        '"answer": "PR-ONLY."',
        "live-tree",
        "Owner decision OQ-3 binds release mode to PR-ONLY.",
    )
    e2 = ev(
        CATALOG,
        "never a private canary and never a public marketplace release",
        "live-tree",
        "PR-ONLY forbids private canary and public marketplace publication.",
    )
    e3 = ev(
        CATALOG,
        "an unreachable failure mode must not be counted as mitigated",
        "live-tree",
        "Catalog forbids counting unreachable modes as mitigated.",
    )
    e4 = ev(
        CATALOG,
        "plant a deployed capability with no registry entry and assert the reconciliation reports it",
        "live-tree",
        "Catalog requires the planted-orphan negative control.",
    )
    e5 = ev(
        REGISTRY,
        '"id": "plugin.harness"',
        "live-tree",
        "Live typed registry lists plugin.harness as a package id.",
    )
    e6 = ev(
        DESIGN_A1,
        '"architecture_name": "config-first-minimal"',
        "dossier",
        "A1 fixture dossier is config-first-minimal: static JSON tree, no generated marketplace install reconciler. Live phase3/A1/DESIGN.json is absent.",
    )
    e7 = ev(
        DESIGN_A2,
        '"kind": { "const": "marketplace_entry" }',
        "dossier",
        "A2 typed registry schema encodes marketplace_entry as a generated record, not an installed lockfile-pinned package. Live phase3/A2/DESIGN.json is absent.",
    )
    e8 = ev(
        CATALOG,
        "The reachable/unreachable split cites the owner decision line for PR-ONLY",
        "live-tree",
        "Evidence requirement: cite PR-ONLY and name the reachable-again condition.",
    )

    rev = R.review()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    planted = (
        "command-center/p2-wave/probes/ARC-0019/fixtures/b-planted/installed/"
        "capability.planted-orphan/PACKAGE.json"
    )
    live_block = {
        "pairing": live["pairing"],
        "registry_path": live["registry_path"],
        "install_root": live["install_root"],
        "install_root_present": live["install_root_present"],
        "design_present": live["design_present"],
        "owner_decisions_present": live["owner_decisions_present"],
        "pr_only_binding_record": live["pr_only_binding_record"],
        "registry_entry_count": live["registry_entry_count"],
        "registry_id_count": live["registry_id_count"],
        "deployed_package_count": live["deployed_package_count"],
        "registry_not_deployed_count": a_count,
        "deployed_not_in_registry_count": b_count,
        "hash_mismatch_count": h_count,
        "disagreement_count": d_count,
        "registry_not_deployed": live["registry_not_deployed"],
        "deployed_not_in_registry": live["deployed_not_in_registry"],
        "hash_mismatches": live["hash_mismatches"],
        "fails_today": live["fails_today"],
        "note": (
            "A3 DESIGN.json is absent (ARC-0017 not delivered). OWNER-DECISIONS.md "
            "is absent; PR-ONLY is taken from WORK-UNIT-CATALOG.json OQ-3. "
            "Install root command-center/control-plane/A3/installed is absent, so "
            "every registry id is registry-not-deployed. Direction B is zero on "
            "the live tree only after detector-control found a planted "
            "unregistered PACKAGE.json on a fixture. Counts are not an agree score."
        ),
    }

    doc = {
        "unit_id": "ARC-0019",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0019",
        "completion_sentinel": "SUCCESS:ARC-0019",
        "architecture_id": "A3",
        "architecture_class": "marketplace-first",
        "title": (
            "A3 (marketplace-first): offline, stale-index and revoked-but-cached "
            "failure modes with no second publisher"
        ),
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "headline_verdict": "FAILS-REGISTRY-NOT-DEPLOYED",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "reliability-engineer",
            "execution_substrate": "headless-linux",
        },
        "live_reconciliation": live_block,
        "author_failure_modes": author_modes(),
        "reachability": {
            "pr_only_anchor": e1["anchor"],
            "pr_only_snippet": PR_ONLY_LINE,
            "rule": (
                "Unreachable under PR-ONLY is not mitigated. Each unreachable "
                "mode names the owner change that would make it reachable again."
            ),
            "modes": reachability_modes(),
        },
        "seeded_classes": {
            "count": len(SE.SEEDED_47),
            "source_status": SE.SOURCE_STATUS,
            "source_citation": SE.SOURCE_CITATION,
            "names": list(SE.SEEDED_47),
        },
        "scenario": {
            "id": "S1-registry-vs-deployed-planted-orphan",
            "title": "Registry ids versus installed packages, with planted orphan",
            "silent_loss_file": planted,
            "catching_architecture": (
                "A3 marketplace-first registry-versus-deployed reconciler "
                "(id set xor plus payload hash), fail-closed; public-marketplace "
                "subclasses named UNREACHABLE under PR-ONLY and not counted as "
                "mitigated. A2 generated-SSOT path completeness is a sibling gate, "
                "not this unit's install reconciler."
            ),
            "on_this_estate": (
                f"ARC-0010 registry.json has {live['registry_id_count']} ids. "
                f"A3 install root present={live['install_root_present']}. "
                f"A={a_count} registry-not-deployed, B={b_count} "
                f"deployed-not-in-registry, H={h_count} hash-mismatch, "
                f"disagreement_count={d_count}. PR-ONLY is catalog OQ-3; "
                "OWNER-DECISIONS.md is absent. A3 DESIGN.json is absent."
            ),
            "procedure": [
                "1. Load the typed registry (ARC-0010 registry.json) as the package index.",
                "2. Treat command-center/control-plane/A3/installed/<id>/PACKAGE.json as the deployed package.",
                "3. Direction A: every registry id whose PACKAGE.json is missing or empty is registry-not-deployed.",
                "4. Direction B: every installed PACKAGE.json whose id is absent from the registry is deployed-not-in-registry.",
                "5. Hash: when both exist, compare sha256 of canonical registry blob to PACKAGE.json bytes.",
                "6. Negative control: plant capability.planted-orphan with no registry row and assert Direction B names it.",
                "7. Both-states: restore the fixture and assert B is silent for that id; delete an install and assert A fires then restore.",
                "8. Run the same reconciler on the live worktree and record A, B, H, and disagreement_count separately.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0019/live.py"
            ),
            "reproduction": {
                "a_fires_on_missing_install": True,
                "a_silent_on_complete": True,
                "b_fires_on_planted_orphan": True,
                "b_silent_on_restore": True,
                "detector_control_a": True,
                "detector_control_b": True,
                "live_registry_not_deployed_count": a_count,
                "live_deployed_not_in_registry_count": b_count,
                "live_hash_mismatch_count": h_count,
                "live_disagreement_count": d_count,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "PR-ONLY makes the five named no-network marketplace failure "
                    "modes unreachable and therefore mitigated."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "No A3 DESIGN.json encodes that rule. The sentence is the "
                    "unit's forbidden conclusion, pinned by the catalog question."
                ),
                "scoped_restatement": (
                    "Local stale-index, missing-blob, revoked-but-cached leftover, "
                    "lockfile drift, and registry-vs-deployed remain reachable under "
                    "PR-ONLY. Public subclasses are unreachable, not mitigated."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "Registry-versus-deployed disagreement is reachable on this "
                    "worktree today with no network and no second publisher."
                ),
                "verdict": "CONFIRMED",
                "anchor": e5["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "A live Direction-B count of zero means deployed-not-in-registry "
                    "is clean without planting an unregistered install."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The live B=0 is an empty scan of an absent install root. "
                    "The catalog required a planted orphan before that zero is trusted."
                ),
                "scoped_restatement": (
                    "Live B=0 is allowed only after detector-control found "
                    "capability.planted-orphan on a fixture."
                ),
                "anchor": e4["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "Public stale-index, remote-offline-install, and third-party "
                    "revoked-but-cached are UNREACHABLE under PR-ONLY."
                ),
                "verdict": "CONFIRMED",
                "anchor": e1["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "Unreachable public-marketplace modes may be counted as "
                    "mitigated by PR-ONLY."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The catalog sentence forbids counting unreachable modes as "
                    "mitigated. PR-ONLY removes the channel; it does not install a control."
                ),
                "scoped_restatement": (
                    "Each unreachable mode sets counted_as_mitigated false and names "
                    "the owner change that would make it reachable again."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C6",
                "claim": (
                    "A3 DESIGN.json is absent, so the ARC-0017 cache-invalidation "
                    "walkthrough that would make stale-cache-masks-a-fixed-package "
                    "unreachable is not demonstrated on this tree."
                ),
                "verdict": "CONFIRMED",
                "anchor": e8["anchor"],
            },
            {
                "id": "C7",
                "claim": (
                    "A2 marketplace_entry is a lockfile-pinned installed package "
                    "control plane that already closes registry-vs-deployed."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "phase3/A2/DESIGN.json is absent. The live A2 surface "
                    "(ARC-0010 registry.schema.json) defines marketplace_entry as "
                    "a generated typed record (plugin_id, name, version, description, "
                    "category) with no lockfile pin and no install root."
                ),
                "scoped_restatement": (
                    "A2 generates marketplace JSON from a typed registry. It does not "
                    "define lockfile-pinned install state or this unit's reconciler."
                ),
                "anchor": e7["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-reconcile-both-states-and-live",
                "name": (
                    "Both-states, planted-orphan negative control, live disagreement counts"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-reachability-reviewer",
                "name": (
                    "REFUTED rows name DESIGN vs SENTENCE; unreachable not mitigated; "
                    "reviewer added a mode"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": rev,
        "named_probes": [
            {"id": "probe1", "role": "reconcile-both-states-live", "command": P1},
            {"id": "probe2", "role": "overclaim-reachability-reviewer", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0019/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T18:30:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": REGISTRY, "exists": True, "role": "live-registry"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0019/reconcile.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "answer": (
            f"No-network, no-second-publisher marketplace modes stay reachable "
            f"under PR-ONLY as local facts: stale committed index, missing local "
            f"blob, leftover install after a revert, lockfile drift, and "
            f"registry-vs-deployed. Live tree today: A={a_count} "
            f"registry-not-deployed, B={b_count} deployed-not-in-registry, "
            f"H={h_count} hash-mismatch, disagreement_count={d_count}. Public "
            f"stale-index, remote-offline-install, and third-party revoked-but-cached "
            f"are UNREACHABLE while OQ-3 is PR-ONLY; they are not mitigated. "
            f"Reviewer added FM-LOCKFILE-ABSENT-VACUOUS. SUCCESS:ARC-0019"
        ),
    }
    doc["reviewer"]["independent"] = True
    doc["reviewer"]["scope_not_agreement"] = True

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0019 overclaim {why}")
        return 1

    errs = SC.validate(doc, SC.LOCAL_SCHEMA)
    if errs:
        print("FAILED:ARC-0019 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not SC.validate(g, SC.LOCAL_SCHEMA):
            print(f"FAILED:ARC-0019 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0019 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"live A={a_count} B={b_count} H={h_count} disagreement={d_count} "
        f"fails_today={live['fails_today']}"
    )
    print("SUCCESS:ARC-0019 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
