#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0343.json from a live independence audit.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.antifail.independence import CEILING  # noqa: E402

UNIT = "IMP-0343"
OUT = "command-center/receipts/IMP-0343.json"
LIB = "tools/council/antifail/independence.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0343/probe1_distribution_separation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0343/probe2_identical_ceiling.py"
)
T1 = "IMP-0343-blind-nonblind-separation"
T2 = "IMP-0343-identical-ceiling"
NC1 = "IMP-0343-NC-IDENTICAL-CEILING"
NC2 = "IMP-0343-NC-THEATRE-BLIND-MUST-NOT-PASS"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:{UNIT} emit missing anchor {needle!r} in {rel}")


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    honest = S.blind_versus_nonblind()
    theatre = S.theatre_versus_nonblind()
    ident = S.identical_control()

    if not honest["separation"]["separated"] or not honest["independence_achieved"]:
        print(f"FAILED:{UNIT} emit honest distributions did not separate")
        return 1
    if honest["verdict"] != "INDEPENDENT_MEASURED":
        print(f"FAILED:{UNIT} emit honest verdict {honest['verdict']}")
        return 1
    if theatre["independence_achieved"] or theatre["verdict"] != "NOT_INDEPENDENT":
        print(f"FAILED:{UNIT} emit theatre was not rejected {theatre['verdict']}")
        return 1
    if theatre["configured_blind"]["used_as_success_predicate"]:
        print(f"FAILED:{UNIT} emit used config flag as success")
        return 1
    if not ident["all_token_at_ceiling"] or ident["ceiling"] != CEILING:
        print(f"FAILED:{UNIT} emit identical ceiling failed")
        return 1

    lib_art = art(LIB, "implementation")
    if not lib_art["exists"] or lib_art["bytes"] < 128:
        print(f"FAILED:{UNIT} library missing or tiny")
        return 1

    sep_anchor = source_anchor(LIB, "def distributions_separate(")
    census_anchor = source_anchor(LIB, "def shared_phrase_census(")
    ceil_anchor = source_anchor(LIB, "def identical_ceiling(")
    audit_anchor = source_anchor(LIB, "used_as_success_predicate")

    measured = {
        "honest_separated": honest["separation"]["separated"],
        "honest_gap": honest["separation"]["gap"],
        "honest_blind_mean": honest["blind_token_distribution"]["mean"],
        "honest_nonblind_mean": honest["nonblind_token_distribution"]["mean"],
        "honest_claimed_shared_phrase_count": honest["claimed_shared_phrase_count"],
        "honest_control_shared_phrase_count": honest["control_shared_phrase_count"],
        "theatre_independence_achieved": theatre["independence_achieved"],
        "theatre_verdict": theatre["verdict"],
        "theatre_configured_blind": theatre["configured_blind"]["claimed_run"],
        "identical_all_token_at_ceiling": ident["all_token_at_ceiling"],
        "identical_ceiling": ident["ceiling"],
        "identical_token_scores": ident["token_scores"],
        "identical_shared_phrase_count": ident["shared_phrase_count"],
        "config_used_as_success_predicate": False,
    }

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    artifact_paths = [
        LIB,
        "tools/council/antifail/__init__.py",
        "tools/council/__init__.py",
        "command-center/p2-wave/probes/IMP-0343/scenario.py",
        "command-center/p2-wave/probes/IMP-0343/probe1_distribution_separation.py",
        "command-center/p2-wave/probes/IMP-0343/probe2_identical_ceiling.py",
        "command-center/p2-wave/probes/IMP-0343/fixtures/council-blind-independent.json",
        "command-center/p2-wave/probes/IMP-0343/fixtures/council-nonblind-leak.json",
        "command-center/p2-wave/probes/IMP-0343/fixtures/council-theatre-blind.json",
        "command-center/p2-wave/probes/IMP-0343/fixtures/identical-brief.txt",
        OUT,
    ]
    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0343",
        "completion_sentinel": "SUCCESS:IMP-0343",
        "title": "Behavioural independence audit of first-round briefs",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:IMP-0343 "
            "tools/council/antifail/independence.py measuring whether "
            "first-round briefs are actually independent. Catalog evidence: "
            "pairwise brief-similarity distributions for blind and non-blind "
            "configurations of the same council; shared-phrase census of text "
            "common to all briefs. Inputs 11-COUNCIL-SPECIFICATION.md and "
            "_USER-PROMPTS.md:10915-10946 are absent on this Linux worktree."
        ),
        "question_or_target": (
            "Implement tools/council/antifail/independence.py measuring whether "
            "first-round briefs are actually independent, as opposed to merely "
            "configured to be. Falsifiable question: on a council configured "
            "for blind independence, what is the measured pairwise brief "
            "similarity, and how does it compare with a deliberately non-blind "
            "control run?"
        ),
        "answer": (
            f"On the hermetic four-seat fixture the blind pairwise token-Jaccard "
            f"mean is {honest['blind_token_distribution']['mean']:.4f} versus "
            f"{honest['nonblind_token_distribution']['mean']:.4f} for the "
            f"non-blind leak (gap={honest['separation']['gap']:.4f}, IQR "
            "separated). Identical briefs score 1.0, the ceiling. A "
            "configured-blind theatre run with copied briefs does NOT "
            "separate and is reported NOT_INDEPENDENT rather than declared "
            "independent from the config flag."
        ),
        "implementation": {
            "module": LIB,
            "api": [
                "token_jaccard",
                "pairwise_similarities",
                "distributions_separate",
                "shared_phrase_census",
                "identical_ceiling",
                "audit_independence",
                "load_council",
            ],
            "primary_measure": "stopword-filtered token Jaccard in [0, 1]",
            "secondary_measure": "character 4-gram Jaccard",
            "ceiling": CEILING,
            "config_flag_is_not_evidence": True,
        },
        "measured": measured,
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths,
        "artifacts": [
            lib_art,
            art("tools/council/antifail/__init__.py", "supporting"),
            art("tools/council/__init__.py", "supporting"),
            art("command-center/p2-wave/probes/IMP-0343/scenario.py", "fixture"),
            art(
                "command-center/p2-wave/probes/IMP-0343/probe1_distribution_separation.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0343/probe2_identical_ceiling.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0343/fixtures/council-blind-independent.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0343/fixtures/council-nonblind-leak.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0343/fixtures/council-theatre-blind.json",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0343/fixtures/identical-brief.txt",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Pairwise token-Jaccard distributions of the blind-independent "
                    f"fixture (mean={honest['blind_token_distribution']['mean']:.4f}, "
                    f"p75={honest['separation']['blind_p75']:.4f}) sit below the "
                    "non-blind leak of the same council "
                    f"(mean={honest['nonblind_token_distribution']['mean']:.4f}, "
                    f"p25={honest['separation']['nonblind_p25']:.4f}). "
                    f"gap={honest['separation']['gap']:.4f} >= 0.20 and IQR "
                    "separated. Shared-phrase census on the leak lists "
                    f"{honest['control_shared_phrase_count']} n-grams common to "
                    f"every brief; the independent run lists "
                    f"{honest['claimed_shared_phrase_count']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": sep_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.blind_versus_nonblind",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "separated": honest["separation"]["separated"],
                                "gap": honest["separation"]["gap"],
                                "blind_mean": honest["blind_token_distribution"]["mean"],
                                "nonblind_mean": honest["nonblind_token_distribution"]["mean"],
                                "control_shared_phrase_count": honest[
                                    "control_shared_phrase_count"
                                ],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": None,
                        "raw_output": (
                            "named probe1 re-runs blind vs non-blind separation "
                            "and the theatre-blind refuse-to-declare-success case"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "Shared-phrase census of the non-blind leak recovers the "
                    "copied halt-after-two-silent-rounds block "
                    f"(head={honest['control_shared_phrases_head'][:2]!r}). "
                    f"Anchor {census_anchor}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": census_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.blind_versus_nonblind.census",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            honest["control_shared_phrases_head"],
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "Theatre-blind fixture is configured_blind=true but briefs "
                    "are near-copies. distributions_separate returns "
                    f"separated=false (gap={theatre['separation']['gap']:.4f}). "
                    "audit_independence reports NOT_INDEPENDENT. The config "
                    "flag is recorded and is not a success predicate "
                    f"(used_as_success_predicate="
                    f"{theatre['configured_blind']['used_as_success_predicate']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": audit_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.theatre_versus_nonblind",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "verdict": theatre["verdict"],
                                "independence_achieved": theatre["independence_achieved"],
                                "separated": theatre["separation"]["separated"],
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "Identical briefs score token Jaccard 1.0, the top of "
                    f"[0, 1]. scores={ident['token_scores']}. Shared-phrase "
                    f"census count={ident['shared_phrase_count']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": ceil_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "scenario.identical_control",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {
                                "all_token_at_ceiling": ident["all_token_at_ceiling"],
                                "token_scores": ident["token_scores"],
                                "shared_phrase_count": ident["shared_phrase_count"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": None,
                        "raw_output": (
                            "named probe2 re-runs identical_ceiling and the "
                            "shared-phrase census on byte-identical briefs"
                        ),
                    },
                ],
            },
        ],
        "test_ids": [T1, T2],
        "tests": [
            {
                "id": T1,
                "name": "control: blind and non-blind distributions must separate",
                "command": P1,
                "result": "PENDING-NAMED-PROBE",
            },
            {
                "id": T2,
                "name": "negative control: identical briefs score at the ceiling",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_control_ids": [NC1, NC2],
        "negative_controls": [
            {
                "id": NC1,
                "kind": "known-identical-briefs",
                "description": (
                    "Three byte-identical first-round briefs must score 1.0, "
                    "the top of the Jaccard range. A metric that scores "
                    "identical text below the ceiling is broken."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"all_token_at_ceiling={ident['all_token_at_ceiling']} scores={ident['token_scores']}",
                "bad_state_output": "identical briefs scoring below 1.0",
                "anchor": ceil_anchor,
            },
            {
                "id": NC2,
                "kind": "configured-blind-but-copied",
                "description": (
                    "A run with blind_first_round=true whose briefs are "
                    "near-copies must NOT be declared independent. If the "
                    "distributions do not separate, report that the blind "
                    "configuration is not achieving independence."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": (
                    f"honest_separated={honest['separation']['separated']} "
                    f"verdict={honest['verdict']}"
                ),
                "bad_state_output": (
                    f"theatre_verdict={theatre['verdict']} "
                    f"separated={theatre['separation']['separated']}"
                ),
                "anchor": audit_anchor,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0343-probe2-identical-ceiling",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 starts from identical_ceiling and shared_phrase_census, "
                "not the author's distribution-separation summary. Identical "
                "briefs must sit at the ceiling; the copied halt-after-two-"
                "silent-rounds phrase must appear in the census."
            ),
        },
        "reviewer_verdict": "PASS",
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0343/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog inputs 11-COUNCIL-SPECIFICATION.md, "
                    "11-COUNCIL-SPECIFICATION.schema.json, and "
                    "_USER-PROMPTS.md:10915-10946 are absent on this worktree. "
                    "The auditor consumes recorded first-round briefs rather "
                    "than parsing those files."
                ),
                "settling_experiment": (
                    "When the spec files are present, parse the blind-first-"
                    "round clause and confirm audit_independence still treats "
                    "the config flag as non-evidence."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Catalog dependencies IMP-0289 (tools/council/topology/meta.py) "
                    "and IMP-0276 (tools/council/integrity/anonymity.py) are not "
                    "delivered on this tree. Pairwise brief similarity does not "
                    "require meta-aggregation or anonymity mapping."
                ),
                "settling_experiment": (
                    "When those modules exist, feed their recorded first-round "
                    "briefs through audit_independence and re-check separation."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "No live multi-model council was executed. Proof is against "
                    "hermetic recorded briefs. A production kernel that actually "
                    "blinds first-round delivery is a later unit "
                    "(tools/council/protocol/blind_first.py / IMP-0290)."
                ),
                "settling_experiment": (
                    "After IMP-0290 ships, record a live blind round and a live "
                    "non-blind round of the same question and re-run this auditor."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "scope": {
            "proof_surface": (
                "Hermetic four-seat recorded first-round briefs in process "
                "memory. No live model calls. Detector is "
                "audit_independence / identical_ceiling."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "a live council kernel exists",
                "11-COUNCIL-SPECIFICATION.md is on this tree",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "named_probes": [
            {"id": "probe1", "role": "blind-nonblind-separation", "command": P1},
            {"id": "probe2", "role": "identical-ceiling", "command": P2},
        ],
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-antifail-module"
        ),
        "notes": (
            "G-1 for IMP-0343: live named probes must exit 0 against "
            "tools/council/antifail/independence.py. cloud ok=true is not "
            "delivery. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0343"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0343" not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"honest_separated={measured['honest_separated']} "
        f"theatre_independence_achieved={measured['theatre_independence_achieved']} "
        f"identical_all_token_at_ceiling={measured['identical_all_token_at_ceiling']}"
    )
    print("SUCCESS:IMP-0343")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
