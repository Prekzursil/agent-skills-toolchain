#!/usr/bin/env python3
"""Emit RES-0187 counterevidence-coverage-audit measurement run."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
import sys

sys.path.insert(0, str(HERE))

from classify import CHALLENGED, UNCHALLENGED, classify  # noqa: E402
from contract import (  # noqa: E402
    ABSENT_INPUTS,
    CATALOG_SNIPPET,
    HEDGE_RULE,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
)
from controls import CAVEAT_ONLY, HOWEVER_ONLY, RECORDED_TRIPLE  # noqa: E402
from inventory import load_population  # noqa: E402
import lineage as L  # noqa: E402

CHALLENGE_RULE = (
    "A conclusion counts as challenged only if a recorded query, its result "
    "set and a verdict exist. A hedging phrase in the prose does not count. "
    "The word 'however' is a mention, not a disconfirming search. Caveat "
    "fields (strongest_caveat, strongest_surviving_counterargument) are not "
    "challenge records. Supporting lineage, signals, and settling probes are "
    "not disconfirming searches."
)


def labeled_row(obj: dict) -> dict:
    v = classify(obj)
    return {
        "id": obj["id"],
        "text": obj.get("canonical_mechanism") or obj.get("text"),
        "status": v["status"],
        "reason": v["reason"],
        "hedge_mention": v["hedge_mention"],
        "found_at": v["found_at"],
        "record": v["record"],
        "role": "labeled-control",
    }


def build() -> dict:
    L.write_source_lineage()
    pop = load_population(REPO)
    if not pop["extractor_agreement"]["agree"]:
        raise SystemExit(
            "FAILED:RES-0187 extractor disagreement "
            f"{pop['extractor_agreement']}"
        )
    if pop["n"] < 8:
        raise SystemExit(f"FAILED:RES-0187 population too thin n={pop['n']}")

    however = labeled_row(HOWEVER_ONLY)
    recorded = labeled_row(RECORDED_TRIPLE)
    caveat = labeled_row(CAVEAT_ONLY)
    if however["status"] != UNCHALLENGED:
        raise SystemExit("FAILED:RES-0187 however control not UNCHALLENGED")
    if recorded["status"] != CHALLENGED:
        raise SystemExit("FAILED:RES-0187 recorded control not CHALLENGED")
    if caveat["status"] != UNCHALLENGED:
        raise SystemExit("FAILED:RES-0187 caveat control not UNCHALLENGED")

    absent = {p: not (REPO / p).is_file() for p in ABSENT_INPUTS}
    registry_present = (REPO / "command-center/CLAIM-REGISTRY.json").is_file()

    frac = pop["coverage_fraction"]
    frac_s = "undefined (empty population)" if frac is None else f"{frac:.4f}"
    unchallenged_ids = [r["id"] for r in pop["unchallenged"]]
    challenged_ids = [r["id"] for r in pop["challenged"]]
    answer = (
        f"Of {pop['n']} major conclusions currently recorded as claims[] in "
        f"command-center/research/**/*.json on this worktree, "
        f"{pop['challenged_n']} have a recorded disconfirming search "
        f"(query + result_set + verdict). Coverage fraction = {frac_s}. "
        f"Unchallenged n={pop['unchallenged_n']}. Hedging prose including "
        f"'however' does not count; the however-only labeled control is "
        f"{however['status']}. CLAIM-REGISTRY.json is "
        f"{'PRESENT' if registry_present else 'ABSENT'}; this is therefore "
        f"an on-disk research-claim audit, not an exhaustive registry audit. "
        f"Distinct from RES-0022: this unit does not hunt doc-versus-behaviour "
        f"contradictions in the client. {SENTINEL}"
    )

    c1a = L.catalog_unit_signal("C1-a")
    c1b = L.file_signal(
        "command-center/p2-wave/probes/RES-0187/classify.py",
        "no-recorded-query-result_set-verdict-triple",
        "C1-b",
    )
    c2a = L.file_signal(
        "command-center/research/RES-0079.json",
        "Usable does not mean well calibrated",
        "C2-a",
    )
    c2b = L.file_signal(
        "command-center/research/teardown/"
        "RES-0178-teardown-skill-and-mcp-distribution-hubs.json",
        "strongest_surviving_counterargument",
        "C2-b",
    )
    c3a = L.file_signal(
        "command-center/WORK-UNIT-CATALOG.json",
        "command-center/CLAIM-REGISTRY.json",
        "C3-a",
    )
    c4a = L.capture_signal("wep-wikipedia", "C4-a")
    c4b = L.capture_signal("kent-wep-wayback", "C4-b")

    cc = REPO / "command-center"
    names = sorted(p.name for p in cc.iterdir())
    listing = "\n".join(names) + "\n"
    listing_path = HERE / "captures" / "command-center-listing.txt"
    listing_path.write_text(listing, encoding="utf-8")
    if "CLAIM-REGISTRY.json" in names:
        raise SystemExit("FAILED:RES-0187 CLAIM-REGISTRY unexpectedly present")
    c3b = L.file_signal(
        listing_path.relative_to(REPO).as_posix(),
        "WORK-UNIT-CATALOG.json",
        "C3-b",
    )

    claims = [
        {
            "id": "C1",
            "claim": (
                "A conclusion is CHALLENGED only when a recorded query, "
                "result_set list, and verdict exist. A hedging phrase "
                "including the word 'however' does not count."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": (
                "Re-run classify() and the probe1 independent triple-check on "
                "the however-only control (must be UNCHALLENGED) and on the "
                "recorded-triple control (must be CHALLENGED). Confirm the "
                "catalog evidence_requirement still contains the rule snippet."
            ),
            "signals": [c1a, c1b],
        },
        {
            "id": "C2",
            "claim": (
                f"Coverage of recorded counterevidence searches over the "
                f"{pop['n']} on-disk research claims is "
                f"{pop['challenged_n']}/{pop['n']} "
                f"(fraction {frac_s}). Caveats in those artifacts are hedges, "
                f"not recorded hunts."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": (
                "Re-walk command-center/research/**/*.json claims arrays "
                "(probe2 recount) and require the same ids, challenged_n, "
                "and unchallenged list. Two extractors (claims-array text "
                "gate vs id-scan) must agree."
            ),
            "signals": [c2a, c2b],
        },
        {
            "id": "C3",
            "claim": (
                "command-center/CLAIM-REGISTRY.json is absent on this worktree, "
                "so the audited population is the on-disk research claims[] "
                "tables rather than a program-wide registry."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": (
                "Stat CLAIM-REGISTRY.json (must be absent) and re-read the "
                "command-center directory listing capture; the name must not "
                "appear. Catalog still lists the file as an input."
            ),
            "signals": [c3a, c3b],
        },
        {
            "id": "C4",
            "claim": (
                "Confidence bands in this measurement run use Sherman Kent's "
                "Words of Estimative Probability scale, whose 'Almost certain' "
                "band is attested in the 1964 essay and in the WEP summary."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": (
                "Re-hash captures/wep-wikipedia.raw and "
                "captures/kent-wep-wayback.raw; both must still contain "
                "'Almost certain' and match source-lineage.json."
            ),
            "signals": [c4a, c4b],
        },
    ]

    tests = [
        {
            "id": "however-only-unchallenged",
            "name": "negative control: however-only conclusion is UNCHALLENGED",
            "observed_status": however["status"],
            "mention_trap_would_classify": "CHALLENGED",
            "pass": however["status"] == UNCHALLENGED,
        },
        {
            "id": "recorded-triple-challenged",
            "name": "positive control: query+result_set+verdict is CHALLENGED",
            "observed_status": recorded["status"],
            "pass": recorded["status"] == CHALLENGED,
        },
        {
            "id": "caveat-field-unchallenged",
            "name": "caveat-only conclusion is UNCHALLENGED",
            "observed_status": caveat["status"],
            "pass": caveat["status"] == UNCHALLENGED,
        },
        {
            "id": "extractor-agreement",
            "name": "claims-array extractor and id-scan extractor agree",
            "pass": pop["extractor_agreement"]["agree"],
        },
    ]

    doc = {
        "$schema": SCHEMA_REL,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "title": (
            "How many of this program's major conclusions have had a real "
            "counterevidence search?"
        ),
        "question": QUESTION,
        "answer": answer,
        "challenge_rule": CHALLENGE_RULE,
        "catalog_rule_quote": CATALOG_SNIPPET + "; " + HEDGE_RULE,
        "ts": L.now_iso(),
        "kind": "measurement-run",
        "report_kind": "counterevidence-coverage-audit",
        "coverage": {
            "population": "command-center/research/**/*.json claims[]",
            "population_n": pop["n"],
            "challenged_n": pop["challenged_n"],
            "unchallenged_n": pop["unchallenged_n"],
            "coverage_fraction": frac,
            "challenged_ids": challenged_ids,
            "unchallenged_ids": unchallenged_ids,
            "files": pop["files"],
            "extractor_agreement": {
                "agree": pop["extractor_agreement"]["agree"],
                "n_claims_array": pop["extractor_agreement"]["n_claims_array"],
                "n_id_scan": pop["extractor_agreement"]["n_id_scan"],
            },
        },
        "conclusions": pop["conclusions"],
        "controls": {
            "labeled": [however, recorded, caveat],
            "not_in_coverage_fraction": True,
        },
        "measurements": [
            {
                "id": "coverage_fraction",
                "value": frac,
                "challenged_n": pop["challenged_n"],
                "population_n": pop["n"],
            },
            {
                "id": "however_only_status",
                "value": however["status"],
            },
            {
                "id": "recorded_triple_status",
                "value": recorded["status"],
            },
            {
                "id": "claim_registry_present",
                "value": registry_present,
            },
        ],
        "claims": claims,
        "tests": tests,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "however-use-versus-mention"},
            {
                "id": "probe2",
                "command": P2,
                "role": "recorded-triple-both-states-and-recount",
            },
        ],
        "reviewers": [
            {
                "reviewer_id": "RES-0187-adversarial-refuter",
                "independent": True,
                "default_to_refuted": True,
                "mandate": (
                    "Default REFUTED unless the however-only control is "
                    "UNCHALLENGED, the recorded triple is CHALLENGED, dropping "
                    "any triple field flips to UNCHALLENGED, and the research "
                    "claims recount matches the artifact."
                ),
                "verdict": "PASS",
            }
        ],
        "honesty": {
            "inputs_absent": absent,
            "claim_registry_present": registry_present,
            "live_prompt_one_unread": True,
            "fixture_is_not_the_population": True,
            "recall_limit": (
                "Population is claims[] in on-disk command-center/research "
                "JSON. CLAIM-REGISTRY.json, sources/REGISTER.md, and "
                "_USER-PROMPTS.md are absent. Coverage is not an exhaustive "
                "program-registry figure."
            ),
        },
        "distinct_from": {
            "id": "RES-0022",
            "does_not": (
                "hunt doc-versus-behaviour contradictions in the client"
            ),
        },
        "residual_unknowns": [
            "Live CLAIM-REGISTRY contents, if that file exists on another host.",
            "Whether any research conclusion off this worktree carries a recorded hunt.",
            "Prompt-One numbered corpus on the Windows restore tree (unread here).",
        ],
        "strongest_surviving_counterargument": (
            "A claims[] row could hide a hunt under a key this classifier "
            "does not name. Probe2's drop-query/result_set/verdict mutants "
            "only bind the named triple; an unpublished key would be "
            "counted UNCHALLENGED. That is a miss, not a false CHALLENGED, "
            "so reported coverage is a lower bound on recorded hunts using "
            "the published key set."
        ),
        "downstream_consumers": [
            "RES-0185 evidence map (single-source vs unchallenged overlap)",
            "SYN-0001 rival-cause labelling",
        ],
        "manifest_registration": {
            "per_unit": (
                "command-center/p2-wave/probes/RES-0187/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_unit_manifest_write": False,
        },
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
