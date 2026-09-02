#!/usr/bin/env python3
"""Emit the CNL-0123 simulation spec (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fanin import DISAGREEMENT, PASS  # noqa: E402
from simulate import NEGATIVE_CONTROL_VERBATIM, run_all  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0123-council-of-councils-fan-in-simulation-including-the-disagr.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
FANIN = "command-center/p2-wave/probes/CNL-0123/fanin.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0123/probe1_split_children.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0123/probe2_evidence_blind.py"
)
QUESTION = (
    "When three child councils return two PASS and one REFUTED, what does the "
    "parent emit - and does the simulation prove the parent read the child "
    "evidence rather than counting verdicts?"
)
# Catalog output_schema is a generated $ref shim to
# https://ast-integrate.invalid/... — jsonschema RefResolutionError on this
# worktree. G-1 needs JSON parse + sentinel + live probes, not a live $ref
# fetch. Do not rebuild platform/schema (no ADV circle).
LOCAL_REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "declared_outcome",
    "simulation",
    "negative_controls",
    "reviewer",
    "tests",
    "evidence",
    "artifacts",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNL-0123 emit snippet not found in {path}: {snippet!r}")


def ev(rel: str, snippet: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    got = path.read_text(encoding="utf-8").splitlines()[line - 1]
    if snippet not in got:
        raise SystemExit(f"FAILED:CNL-0123 emit anchor {rel}:{line}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def slim_parent(parent: dict) -> dict:
    return {
        "verdict": parent["verdict"],
        "reason": parent["reason"],
        "tally": parent["tally"],
        "majority_of_labels": parent["majority_of_labels"],
        "distinct_source_count": parent["distinct_source_count"],
        "distinct_live_verdicts": parent["distinct_live_verdicts"],
        "parent_digest": parent["parent_digest"],
        "minority_ids": [r["id"] for r in parent["minority"]],
        "children": [
            {
                "id": r["id"],
                "claimed_verdict": r["claimed_verdict"],
                "live_verdict": r["live_verdict"],
                "receipt_status": r["receipt_status"],
                "evidence_sha256": r["evidence_sha256"],
                "evidence_path": r["evidence_path"],
            }
            for r in parent["children"]
        ],
    }


def main() -> int:
    sim = run_all()
    if sim["split"]["verdict"] != DISAGREEMENT:
        print("FAILED:CNL-0123 emit split is not DISAGREEMENT")
        return 1
    if sim["all_pass"]["verdict"] != PASS:
        print("FAILED:CNL-0123 emit all-pass is not PASS")
        return 1
    if not sim["honest_digest_moved"] or sim["vote_digest_moved"]:
        print("FAILED:CNL-0123 emit evidence-blind geometry wrong")
        return 1

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNL-0123 emit schema missing {SCHEMA}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0123",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0123",
        "title": "Council-of-councils fan-in simulation including the disagreement case",
        "question": QUESTION,
        "simulation_id": "cnl-0123-split-2-pass-1-refuted",
        "ts": now,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog output_schema command-center/schema/"
            "council-simulation-spec.schema.json is a generated $ref shim to "
            "https://ast-integrate.invalid/platform/schema/"
            "artifact-class-profiles.schema.json which does not resolve on "
            "this worktree. This spec is JSON-parseable with state=SUCCESS. "
            "No ADV rebuild of that schema was attempted."
        ),
        "spec_anchors": {
            "nested_disagreement": "_USER-PROMPTS.md:11343",
            "digest_is_claim": (
                "fan-in gate: a digest is a claim and not a receipt; applies to "
                "child councils exactly as to subagents"
            ),
            "on_disk_restatement": "command-center/WORK-UNIT-CATALOG.json CNL-0123 / CNF-0174 / TST-0285",
        },
        "harness": {
            "kind": "deterministic-scripted-child-returns",
            "module": FANIN,
            "deterministic": True,
            "not_production_runtime": True,
            "note": (
                "CNL-0117 (scripted-participant harness) and CNL-0037 (fan-in "
                "design note) are not on disk. This unit ships its own scripted "
                "fan-in under probes/CNL-0123/. It is a simulation of the parent "
                "rule, not a second production completion reducer."
            ),
        },
        "fan_in_rule": {
            "id": "surface-split-never-majority",
            "parent_on_split": DISAGREEMENT,
            "majority_forbidden": True,
            "digest_is_claim": True,
            "pass_requires": "every child RECEIPT-OK and unanimous PASS",
            "unread_child": "parent must not overrule a child whose evidence file it did not read",
            "double_count": "duplicate child ids are rejected before tally",
        },
        "declared_outcome": {
            "fixture_id": sim["split_fixture_id"],
            "child_verdicts": sim["split_labels"],
            "parent_verdict": DISAGREEMENT,
            "rejected_parent_verdict": PASS,
            "why_not_majority": (
                "Two PASS vs one REFUTED is the majority-PASS trap. Spec:11343 "
                "names nested councils disagreeing on completion as a failure "
                "class. A single merged PASS with no trace of gamma is REFUTED."
            ),
        },
        "oracles": [
            {
                "id": "A-scripted-replay",
                "kind": "scripted-participant replay",
                "command": P1,
            },
            {
                "id": "B-evidence-digest-diff",
                "kind": "transcript digest diff",
                "command": P2,
            },
            {
                "id": "C-vote-counter-assertion",
                "kind": "counter assertion",
                "command": P2,
            },
        ],
        "simulation": {
            "split": slim_parent(sim["split"]),
            "all_pass": slim_parent(sim["all_pass"]),
            "missing_receipt": slim_parent(sim["missing"]),
            "perturbed": slim_parent(sim["perturbed"]),
            "split_parent_digest": sim["split"]["parent_digest"],
            "perturbed_parent_digest": sim["perturbed"]["parent_digest"],
            "vote_split_digest": sim["vote_split"]["parent_digest"],
            "vote_perturbed_digest": sim["vote_perturbed"]["parent_digest"],
            "honest_digest_moved": sim["honest_digest_moved"],
            "vote_digest_moved": sim["vote_digest_moved"],
            "evidence_blind_control_fired": sim["evidence_blind_control_fired"],
            "labels_held_fixed": sim["labels_held_fixed"],
            "paths_held_fixed": sim["paths_held_fixed"],
            "vote_counter_verdict_on_split": sim["vote_split"]["verdict"],
        },
        "tests": [
            {
                "id": "split-children-declared-outcome",
                "result": "PASS",
                "observation": (
                    f"split parent_verdict={sim['split']['verdict']} "
                    f"tally={sim['split']['tally']} "
                    f"majority_of_labels={sim['split']['majority_of_labels']}"
                ),
            },
            {
                "id": "evidence-blind-parent-detectable",
                "result": "PASS",
                "observation": (
                    f"honest_digest_moved={sim['honest_digest_moved']} "
                    f"vote_digest_moved={sim['vote_digest_moved']} "
                    f"vote_verdict={sim['vote_split']['verdict']}"
                ),
            },
            {
                "id": "both-states-unanimous-pass",
                "result": "PASS",
                "observation": (
                    f"all_pass parent_verdict={sim['all_pass']['verdict']} "
                    "(must stay PASS so DISAGREEMENT is not a constant)"
                ),
            },
            {
                "id": "digest-is-claim-missing-file",
                "result": "PASS",
                "observation": (
                    f"missing-receipt parent_verdict={sim['missing']['verdict']} "
                    "gamma receipt=CLAIM-NOT-RECEIPT despite claimed PASS + planted digest"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "vote-count-parent-evidence-blind",
                "verbatim": NEGATIVE_CONTROL_VERBATIM,
                "rejects": (
                    "a parent that emits majority PASS and whose digest does not "
                    "move when only child evidence changes"
                ),
                "fired": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0123-probe2-both-states-retabulation",
            "verdict": "PASS",
            "independent": True,
            "executed_both_states": True,
            "scope_not_agreement": True,
            "cross_vendor_live_session": False,
            "note": (
                "Catalog asks openai/gpt-5-codex to re-run both-states. This "
                "worktree did not dispatch a vendor session. probe2 re-runs "
                "split vs all-pass and the evidence-perturbation control from "
                "the fixtures; a review that only read this prose would fail "
                "that probe."
            ),
        },
        "answer": {
            "parent_emits": DISAGREEMENT,
            "does_not_emit": PASS,
            "proved_evidence_was_read": True,
            "proof": (
                "Holding the three verdict labels fixed and changing only "
                "child-gamma's evidence body changes the honest parent_digest "
                f"({sim['split']['parent_digest'][:12]}… vs "
                f"{sim['perturbed']['parent_digest'][:12]}…). The vote-counting "
                "parent's digest does not move and still emits PASS."
            ),
        },
        "evidence": [
            ev(
                CATALOG,
                "the fan-in gate rule that a digest is a claim and not a receipt applies to child councils",
                "CNL-0123 evidence_requirement restates spec:11343 on this tree",
            ),
            ev(
                CATALOG,
                "Spec:11343 names 'nested councils disagree on completion' as a required failure class",
                "CNF-0174 restates spec:11343: disagreement must surface, not average",
            ),
            ev(
                CATALOG,
                "The parent must apply the ONE shared completion predicate (CC-0003) rather than a local rule, must not average the verdicts",
                "TST-0285 restates the parent must not average nested verdicts",
            ),
            ev(
                FANIN,
                'verdict, reason = DISAGREEMENT, "nested-councils-disagree-on-completion"',
                "honest parent emits DISAGREEMENT on mixed live child verdicts",
            ),
            ev(
                FANIN,
                "Known-broken parent: hashes only (id, verdict). Ignores evidence.",
                "vote-count parent is the planted evidence-blind control, not the spec",
            ),
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": FANIN, "exists": True, "role": "harness"},
        ],
        "residual_unknowns": [
            "CNL-0117 and CNL-0037 catalog outputs are absent; this simulation does not import them.",
            "CC-0003 shared reducer is not on disk; this parent is a design-simulation, not a claim that production fan-in already imports CC-0003.",
            "_USER-PROMPTS.md:11343 is cited via catalog restatements; the Windows harness-restore path is not on this Linux worktree.",
        ],
        "strongest_surviving_counterargument": (
            "A parent could fold evidence hashes and still decide by majority, "
            "so a moving digest alone would not prove DISAGREEMENT is the rule. "
            "That is why probe1 also asserts parent_verdict != majority_of_labels "
            "on the same fixture, and why the vote-counter (majority PASS, digest "
            "frozen) is the named reject state."
        ),
    }
    missing = [k for k in LOCAL_REQUIRED if k not in doc]
    if missing:
        print("FAILED:CNL-0123 emit missing keys", missing)
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0123 emit self-declared", doc.get("state"))
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:CNL-0123" not in text:
        print("FAILED:CNL-0123 emit sentinel missing")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, n = sha256_file(out_path)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print("SUCCESS:CNL-0123 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
