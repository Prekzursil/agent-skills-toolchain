#!/usr/bin/env python3
"""Probe 2: independent shared-primitive collapse + local missing-column scan.

Mechanically different from probe 1: this probe does not re-parse packuments.
It regroups artifact.matrix.signals by shared_primitive_id and greps THIS
tree's marketplace fixture plus A2 DESIGN for publish-time trust fields.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from collapse import collapse_groups  # noqa: E402

ART = REPO / "command-center/research/RES-0047.json"
MARKET = (
    REPO
    / "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/marketplace/marketplace.harness.json"
)
DESIGN = REPO / "command-center/phase3/A2/DESIGN.json"
REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"
OIDC = "openssf-oidc-trusted-publishing"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:RES-0047-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    signals = list((doc.get("matrix") or {}).get("signals") or [])
    if len(signals) < 6:
        return fail(f"signals={len(signals)}")

    recomputed = collapse_groups(signals)
    stated = (doc.get("collapse") or {}).get("collapsed_shared_primitive_signals")
    if recomputed["collapsed_shared_primitive_signals"] != stated:
        return fail(
            f"collapse mismatch stated={stated} "
            f"recomputed={recomputed['collapsed_shared_primitive_signals']}"
        )
    if stated != 2:
        return fail(
            f"expected OIDC triple to collapse 2 extras, got {stated}"
        )

    oidc = [
        g
        for g in recomputed["groups"]
        if g["shared_primitive_id"] == OIDC
    ]
    if len(oidc) != 1:
        return fail(f"oidc groups={oidc}")
    regs = sorted(oidc[0]["member_registries"])
    if regs != ["crates.io", "npm", "pypi"]:
        return fail(f"oidc registries {regs}")
    if "homebrew" in json.dumps(doc.get("matrix")).lower():
        return fail("homebrew leaked into the six-registry matrix")
    home = ((doc.get("shared_primitive_rule") or {}).get("homebrew_out_of_scope") or {})
    if home.get("counted_in_six") is not False:
        return fail("homebrew must be recorded as out-of-scope")

    mutant = []
    for row in signals:
        copy = dict(row)
        if copy.get("shared_primitive_id") == OIDC:
            copy["shared_primitive_id"] = None
        mutant.append(copy)
    broken = collapse_groups(mutant)
    if broken["collapsed_shared_primitive_signals"] != 0:
        return fail(
            "both-states: stripping OIDC ids must drop collapse to 0, "
            f"got {broken['collapsed_shared_primitive_signals']}"
        )

    if not MARKET.is_file():
        return fail("marketplace fixture missing")
    market = _load_json(MARKET)
    gen = market.get("_generated") or {}
    if not gen.get("registry_id") or not gen.get("generator_version"):
        return fail("local marketplace missing generator provenance header")
    scanned: list[dict] = [market]
    if DESIGN.is_file():
        scanned.append(_load_json(DESIGN))
    elif not REGISTRY.is_file():
        return fail("A2 DESIGN.json and ARC-0010 registry.json both absent")
    else:
        scanned.append(_load_json(REGISTRY))
    blob = "".join(json.dumps(item) for item in scanned).lower()
    for token in ("oidc", "sigstore", "trusted-publish", "trusted_publish"):
        if token in blob:
            return fail(f"local trust token {token} present")
    if doc.get("program_missing_column") != "enforced_at_publish":
        return fail("program_missing_column drift")

    partitions = []
    for rev in (doc.get("reviewer") or {}).get("reviewers") or []:
        partitions.append(tuple(sorted(rev.get("source_partition") or [])))
    if len(partitions) < 2:
        return fail("need two partitioned reviewers")
    if partitions[0] == partitions[1]:
        return fail("reviewer partitions not disjoint")
    if set(partitions[0]) & set(partitions[1]):
        return fail(f"overlapping partitions {partitions}")

    print(
        json.dumps(
            {
                "probe": "probe2-collapse",
                "unit_id": "RES-0047",
                "stated_collapsed": stated,
                "recomputed_collapsed": recomputed[
                    "collapsed_shared_primitive_signals"
                ],
                "independent_after_collapse": recomputed[
                    "independent_signals_after_collapse"
                ],
                "oidc_member_registries": regs,
                "homebrew_in_six": False,
                "mutant_collapse_without_oidc_ids": broken[
                    "collapsed_shared_primitive_signals"
                ],
                "local_generator_header": True,
                "local_publish_gate_absent": True,
                "program_missing_column": "enforced_at_publish",
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:RES-0047-probe2 collapse "
        f"collapsed={stated} missing_column=enforced_at_publish"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
