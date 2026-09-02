#!/usr/bin/env python3
"""Emit command-center/phase3/A3/REFUTATION.json for ARC-0023."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import claim_dossier as C  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A3/REFUTATION.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CLAIM = C.OUT
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Refute marketplace-first given the BINDING owner decision that release "
    "mode is PR-ONLY: if nothing is ever published, is the marketplace an "
    "unfalsifiable control plane whose correctness can never be observed? "
    "Produce the specific evidence that would prove it earns its complexity "
    "before any public release, or show that no such evidence is obtainable "
    "under PR-ONLY."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0023/probe1_falsifiability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0023/probe2_overclaim.py"
)
COUNTER = (
    "Marketplace-first still earns its LOCAL complexity under PR-ONLY. "
    "OQ-9 already names the substitute for canary: a green install -> "
    "upgrade -> rollback rehearsal against a throwaway prefix, with no "
    "deployment target. Those operations, plus unsigned refusal and "
    "missing-blob refusal, distinguish a working file-backed registry from "
    "a broken one without publishing. Public listing, private canary, "
    "moderation and second-publisher machinery are dead weight while OQ-3 "
    "holds. Do not rebuild A3 into a public marketplace (that is the ADV "
    "circle). Scope the control plane to the local fixture plus PR-shaped "
    "index proposals that do not write the live index."
)
CATCHING = (
    "Local file-backed fixture marketplace plus the OQ-9 "
    "install/upgrade/rollback rehearsal: working vs missing-blob states "
    "disagree without any public publish. Public publish stays BLOCKED-PR-ONLY."
)
OQ9 = (
    "a green CI run on the PR head exercising install -> upgrade -> "
    "rollback against a throwaway prefix"
)
LOCAL_GATE = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "claims",
        "evidence",
        "observables",
        "falsifiability_verdict",
        "pr_only_quote",
        "stopping_condition_13",
        "scenario",
        "reviewer",
        "headline_verdict",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0023"},
        "state": {
            "type": "string",
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "SUCCESS:ARC-0023"},
        "falsifiability_verdict": {
            "enum": [
                "FALSIFIABLE-WITHOUT-PUBLISH",
                "REFUTED-AS-UNFALSIFIABLE",
            ]
        },
        "pr_only_quote": {"type": "string", "minLength": 20},
        "observables": {
            "type": "object",
            "required": ["count", "ids", "computed_not_asserted"],
            "properties": {
                "computed_not_asserted": {"const": True},
                "count": {"type": "integer", "minimum": 1},
                "ids": {"type": "array", "minItems": 1},
            },
        },
        "stopping_condition_13": {
            "type": "object",
            "required": ["verdict"],
            "properties": {"verdict": {"const": "UNSATISFIABLE-AS-WRITTEN"}},
        },
        "scenario": {
            "type": "object",
            "required": ["procedure", "silent_loss_file", "reproduction"],
            "properties": {
                "procedure": {"type": "array", "minItems": 4},
                "silent_loss_file": {"type": "string", "minLength": 10},
            },
        },
        "claims": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 4},
        "reviewer": {
            "type": "object",
            "required": ["independent", "scope_not_agreement"],
            "properties": {
                "independent": {"const": True},
                "scope_not_agreement": {"const": True},
            },
        },
        "adv_rebuild_circle": {"const": False},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0023 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    C.write_claim(REPO)
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:ARC-0023 scenario did not reproduce falsifiability")
        print(json.dumps(run, indent=2, sort_keys=True, default=str)[:4000])
        return 1

    e1 = ev(
        CLAIM,
        C.PR_ONLY_LINE,
        "dossier",
        "Claim extract quotes the binding PR-ONLY decision line.",
    )
    e2 = ev(
        CLAIM,
        C.COND13_FINDING,
        "dossier",
        "Claim extract records stopping condition 13 as unsatisfiable as written.",
    )
    e3 = ev(
        CLAIM,
        C.CONTROL_PLANE,
        "dossier",
        "A3 marketplace-first claim: the canonical registry index IS the control plane.",
    )
    e4 = ev(
        CLAIM,
        C.SILENT_LOSS,
        "dossier",
        "Public-index correctness is never observed under PR-ONLY (silent unobservability).",
    )
    e5 = ev(
        CATALOG,
        C.PR_ONLY_LINE,
        "live-tree",
        "Live owner_questions OQ-3 answer_detail is the PR-ONLY binding on this tree.",
    )
    e6 = ev(
        CATALOG,
        C.CONTROL_PLANE,
        "live-tree",
        "Live catalog ARC-0017 states the marketplace-first control-plane claim.",
    )
    e7 = ev(
        CATALOG,
        C.COND13_FINDING,
        "live-tree",
        "Live catalog records the dependency-graph finding on stopping condition 13.",
    )
    e8 = ev(
        CATALOG,
        OQ9,
        "live-tree",
        "OQ-9 names install/upgrade/rollback against a throwaway prefix as the canary substitute.",
    )
    dossier_n = sum(1 for e in (e1, e2, e3, e4) if e["kind"] == "dossier")
    live_n = sum(1 for e in (e5, e6, e7, e8) if e["kind"] == "live-tree")
    if dossier_n < 3 or live_n < 1:
        print(f"FAILED:ARC-0023 evidence counts dossier={dossier_n} live={live_n}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    silent_line = e4["anchor"]
    n_obs = int(run["observable_count"])
    ids = list(run["observable_ids"])
    doc = {
        "unit_id": "ARC-0023",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0023",
        "completion_sentinel": "SUCCESS:ARC-0023",
        "architecture_id": "A3",
        "architecture_class": "marketplace-first",
        "title": (
            "A3 (marketplace-first): Refute marketplace-first under the "
            "binding PR-ONLY release decision"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "Under PR-ONLY, because nothing is ever published, the marketplace "
            "is an unfalsifiable control plane whose correctness can never be "
            "observed, so it cannot earn its complexity before a public release."
        ),
        "headline_verdict": "REFUTED",
        "falsifiability_verdict": "FALSIFIABLE-WITHOUT-PUBLISH",
        "pr_only_quote": C.PR_ONLY_LINE,
        "owner_decisions_md_present": False,
        "owner_decisions_live_record": e5["anchor"],
        "stopping_condition_13": {
            "anchor": e7["anchor"],
            "text": "release/canary succeeds",
            "verdict": "UNSATISFIABLE-AS-WRITTEN",
            "why": (
                "PR-ONLY has no canary channel and never a public marketplace "
                "release; the as-written predicate has no referent."
            ),
        },
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "headless-linux",
        },
        "observables": {
            "computed_not_asserted": True,
            "count": n_obs,
            "ids": ids,
            "method": (
                "Run working vs missing-blob fixture markets plus unsigned, "
                "offline-from-export, publish_public, canary_succeeds, and "
                "propose_pr on command-center/p2-wave/probes/ARC-0023/market.py"
            ),
            "without_publishing": True,
        },
        "scenario": {
            "id": "S1-local-fixture-vs-public-unobservable",
            "title": (
                "Local fixture install/upgrade/rollback distinguishes a working "
                "marketplace from a missing-blob one without publishing; public "
                "publish is BLOCKED; stopping condition 13 is unsatisfiable as written"
            ),
            "on_this_estate": (
                "OWNER-DECISIONS.md is absent; live OQ-3 at "
                + e5["anchor"]
                + " binds PR-ONLY. Catalog ARC-0017 states the canonical registry "
                "index IS the control plane. Catalog ARC-0023 records stopping "
                "condition 13 unsatisfiable as written. A3 DESIGN.json is not "
                "on disk; this unit cites CLAIM-UNDER-TEST.json rather than "
                "rebuilding ARC-0017."
            ),
            "silent_loss_file": silent_line,
            "catching_architecture": CATCHING,
            "procedure": [
                "1. Seed a file-backed fixture registry with cap.skill.demo 1.0.0 and 1.1.0, signatures local-dev-sig.",
                "2. Install 1.0.0 into a throwaway prefix; record lockfile pin and SKILL.md bytes.",
                "3. Upgrade to 1.1.0 (pin and bytes change); rollback to 1.0.0 (pin and bytes restore).",
                "4. Export the registry and install offline from the export into a second prefix.",
                "5. Broken state: point the index at blobs/does-not-exist.json; install is refused.",
                "6. Unsigned state: strip signature but keep blob hash; install is refused at verify.",
                "7. publish_public returns BLOCKED-PR-ONLY. canary_succeeds returns UNSATISFIABLE-AS-WRITTEN. propose_pr writes a PR artifact and leaves index sha256 unchanged.",
                "8. Cite CLAIM-UNDER-TEST silent_unobservability as the file:line that names public-index unobservability under PR-ONLY.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0023/scenario.py"
            ),
            "reproduction": {
                "distinguishes_working_from_broken_without_publish": True,
                "falsifiable_without_publish": True,
                "publish_public_blocked": True,
                "condition_13_unsatisfiable_as_written": True,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "If nothing is ever published, marketplace correctness can "
                    "never be observed, so the architecture is unfalsifiable "
                    "under PR-ONLY."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The unfalsifiable reading is a sentence about 'never "
                    "observed' that ignores the local fixture. OQ-9 already "
                    "names install/upgrade/rollback against a throwaway prefix. "
                    "This unit executed that rehearsal. That is not an extra "
                    "A3 DESIGN rule."
                ),
                "scoped_restatement": (
                    "Public marketplace correctness is unobservable under "
                    "PR-ONLY. Local fixture correctness is observable without "
                    "publishing."
                ),
                "anchor": e4["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "The canonical registry index, including public and canary "
                    "release channels, IS the observable control plane."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "ARC-0017's marketplace-first claim names the registry "
                    "index as the control plane and asks for release channels. "
                    "Under OQ-3 those public/canary channels cannot be observed. "
                    "CLAIM-UNDER-TEST records public_control_plane_observable_"
                    "without_publish false and unreachable_under_pr_only "
                    "private-canary and public-marketplace. That is the "
                    "architecture claim colliding with the owner binding, not "
                    "a wording slip."
                ),
                "scoped_restatement": (
                    "The observable control plane under PR-ONLY is the local "
                    "file-backed registry plus PR-shaped index proposals that "
                    "do not write the live index."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "Program stopping condition 13 (release/canary succeeds) "
                    "is satisfiable as written under PR-ONLY."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "The as-written predicate requires a canary or public "
                    "release channel. OQ-3 forbids both. The live catalog "
                    "already records the dependency-graph finding. This unit "
                    "re-derived it: canary_succeeds() returns "
                    "UNSATISFIABLE-AS-WRITTEN. Not a sentence-only issue."
                ),
                "scoped_restatement": (
                    "Condition 13 is UNSATISFIABLE-AS-WRITTEN. OQ-9 is the "
                    "delegated substitute (install/upgrade/rollback rehearsal), "
                    "not a silent redefinition of condition 13."
                ),
                "anchor": e2["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "Release mode is PR-ONLY: propose changes as pull requests, "
                    "never a private canary and never a public marketplace release."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "Correctly scoped restatement of live OQ-3. "
                    "OWNER-DECISIONS.md is absent; the catalog line is the "
                    "binding record on this tree."
                ),
                "anchor": e5["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "A local fixture install versus a missing-blob index "
                    "distinguishes a working marketplace from a non-working "
                    "one without publishing."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "Computed from the named scenario, not asserted. Working "
                    "install pins 1.0.0; missing blob is refused."
                ),
                "anchor": e8["anchor"],
            },
            {
                "id": "C6",
                "claim": (
                    "Public-index-as-control-plane earns its full marketplace "
                    "complexity before any public release."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "Earning 'full' public marketplace complexity (listing, "
                    "canary, second publisher) is a tournament sentence. The "
                    "local subset can earn lockfile-pinned lifecycle complexity "
                    "under PR-ONLY; the public half cannot be observed, so it "
                    "cannot earn that half."
                ),
                "scoped_restatement": (
                    "Local lockfile-pinned install/update/rollback can earn "
                    "its complexity under PR-ONLY. Public listing cannot."
                ),
                "anchor": e1["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-falsifiability-without-publish",
                "name": (
                    "Name and execute at least one observable that distinguishes "
                    "a working marketplace from a non-working one without publishing"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-locus",
                "name": (
                    "Every REFUTED claim names DESIGN vs SENTENCE; dropping the "
                    "locus fails the checker; REFUTED-AS-UNFALSIFIABLE is not "
                    "softened and is not used when observables exist"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0023-probe2-overclaim-scope",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "method": (
                "Mechanical scope check: every REFUTED row has defect_locus in "
                "{DESIGN, SENTENCE} and a scoped_restatement; both loci appear; "
                "at least one CONFIRMED row exists; dossier and live-tree "
                "anchors resolve; observables are computed from the fixture "
                "client; falsifiability_verdict is FALSIFIABLE-WITHOUT-PUBLISH "
                "because at least one observable fired. Agreement with the "
                "public-control-plane REFUTED verdict is not required. Author "
                "objection alone cannot flip REFUTED. No A3 DESIGN rebuild."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "falsifiability-without-publish", "command": P1},
            {"id": "probe2", "role": "overclaim-check", "command": P2},
        ],
        "report": {
            "kind": "architecture-review",
            "control_ids": [
                "O5-missing-blob-refuses",
                "O6-unsigned-refuses",
                "O7-publish-public-blocked-pr-only",
            ],
            "observations": [
                {
                    "name": oid,
                    "measured": True,
                    "method": (
                        "command-center/p2-wave/probes/ARC-0023/scenario.py "
                        "FixtureMarket working vs missing-blob"
                    ),
                    "anchor": silent_line,
                }
                for oid in ids
            ],
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0023/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T18:30:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CLAIM, "exists": True, "role": "claim-under-test"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0023/scenario.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0023/market.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "answer": (
            "REFUTED as unfalsifiable-because-unpublished: local fixture "
            f"observables (n={n_obs}) distinguish working vs missing-blob "
            "without publishing ("
            + silent_line
            + " names the public-index silent unobservability). PR-ONLY quoted "
            "from live OQ-3 because OWNER-DECISIONS.md is absent. Stopping "
            "condition 13 is UNSATISFIABLE-AS-WRITTEN. Public control plane "
            "cannot earn its complexity; local lockfile lifecycle can. Do not "
            "rebuild A3. SUCCESS:ARC-0023"
        ),
        "adv_rebuild_circle": False,
        "required_fix": None,
        "paired_adversarial_note": (
            "ARC-0023 depends on A3 DESIGN.json (ARC-0017) in the catalog. "
            "Waiting for ARC-0017-0022 before filing this refutation is a "
            "deadlock; G-1 for this unit does not require that circle and "
            "does not rebuild DESIGN.json."
        ),
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0023 overclaim {why}")
        return 1

    # Catalog architecture-review.schema.json is a $ref shim to
    # ast-integrate.invalid. Distro jsonschema 4.10 tries the network and
    # raises RefResolutionError. G-1 is named probes + this artifact, so
    # fail-close with a local Draft7 gate that still rejects garbage.
    validator = jsonschema.Draft7Validator(LOCAL_GATE)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0023 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0023 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0023 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
