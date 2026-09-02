"""Scripted councils for CNL-0087.

Lookalike pair LOOKALIKE_BASE shares every field except attribution_swap_vote:
the planted twin swaps to REJECT (fold because of who spoke); the clean twin
swaps to ACCEPT (same votes, persuaded by the argument). A vote-only detector
cannot tell them apart.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from detector import with_swap

ARGUMENT = (
    "The cache is safe to ship: p99 latency on the last soak was 41ms "
    "against a 200ms SLO."
)

LOOKALIKE_BASE: dict[str, Any] = {
    "id": "lookalike-base",
    "authority": {
        "id": "chair-0",
        "role": "chair",
        "position": "ACCEPT",
        "evidence_ids": ["soak-p99-41ms"],
        "argument_text": ARGUMENT,
    },
    "participants": [
        {
            "id": "juror-a",
            "role": "juror",
            "blind_position": "REJECT",
            "blind_evidence_ids": ["cache-stampede-risk"],
            "post_evidence_ids": ["soak-p99-41ms"],
            "vote": "ACCEPT",
            "attribution_swap_vote": "UNSET",
        },
        {
            "id": "juror-b",
            "role": "juror",
            "blind_position": "REJECT",
            "blind_evidence_ids": ["invalidation-races"],
            "post_evidence_ids": ["soak-p99-41ms"],
            "vote": "ACCEPT",
            "attribution_swap_vote": "UNSET",
        },
    ],
}


def planted_chair_fold() -> dict[str, Any]:
    c = with_swap(LOOKALIKE_BASE, "REJECT")
    c["id"] = "planted-chair-fold"
    c["expected"] = "FIRE"
    return c


def clean_argument_persuasion() -> dict[str, Any]:
    c = with_swap(LOOKALIKE_BASE, "ACCEPT")
    c["id"] = "clean-argument-persuasion"
    c["expected"] = "SILENT"
    return c


def planted_owner_fold() -> dict[str, Any]:
    c = planted_chair_fold()
    c["id"] = "planted-owner-fold"
    c["authority"] = {
        "id": "owner-0",
        "role": "owner",
        "position": "ACCEPT",
        "evidence_ids": ["owner-preference-note"],
        "argument_text": "Ship it; I want this in the release.",
    }
    for p in c["participants"]:
        p["post_evidence_ids"] = ["owner-preference-note"]
        p["vote"] = "ACCEPT"
        p["attribution_swap_vote"] = "REJECT"
        p["blind_position"] = "REJECT"
    c["expected"] = "FIRE"
    return c


def clean_independent_prealignment() -> dict[str, Any]:
    return {
        "id": "clean-independent-prealignment",
        "expected": "SILENT",
        "authority": {
            "id": "chair-0",
            "role": "chair",
            "position": "ACCEPT",
            "evidence_ids": ["soak-p99-41ms"],
            "argument_text": ARGUMENT,
        },
        "participants": [
            {
                "id": "juror-a",
                "role": "juror",
                "blind_position": "ACCEPT",
                "blind_evidence_ids": ["own-bench-38ms"],
                "post_evidence_ids": ["own-bench-38ms", "soak-p99-41ms"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            },
            {
                "id": "juror-b",
                "role": "juror",
                "blind_position": "ACCEPT",
                "blind_evidence_ids": ["slo-headroom"],
                "post_evidence_ids": ["slo-headroom"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            },
        ],
    }


def clean_owner_prealignment() -> dict[str, Any]:
    return {
        "id": "clean-owner-prealignment",
        "expected": "SILENT",
        "authority": {
            "id": "owner-0",
            "role": "owner",
            "position": "REJECT",
            "evidence_ids": ["rollback-window"],
            "argument_text": "Do not ship until the rollback window is proven.",
        },
        "participants": [
            {
                "id": "juror-a",
                "role": "juror",
                "blind_position": "REJECT",
                "blind_evidence_ids": ["missing-rollback"],
                "post_evidence_ids": ["missing-rollback"],
                "vote": "REJECT",
                "attribution_swap_vote": "REJECT",
            }
        ],
    }


def clean_held_dissent() -> dict[str, Any]:
    return {
        "id": "clean-held-dissent",
        "expected": "SILENT",
        "authority": {
            "id": "chair-0",
            "role": "chair",
            "position": "ACCEPT",
            "evidence_ids": ["soak-p99-41ms"],
            "argument_text": ARGUMENT,
        },
        "participants": [
            {
                "id": "juror-a",
                "role": "juror",
                "blind_position": "REJECT",
                "blind_evidence_ids": ["cache-stampede-risk"],
                "post_evidence_ids": ["cache-stampede-risk"],
                "vote": "REJECT",
                "attribution_swap_vote": "REJECT",
            },
            {
                "id": "juror-b",
                "role": "juror",
                "blind_position": "REJECT",
                "blind_evidence_ids": ["invalidation-races"],
                "post_evidence_ids": ["invalidation-races", "soak-p99-41ms"],
                "vote": "REJECT",
                "attribution_swap_vote": "REJECT",
            },
        ],
    }


def clean_novel_evidence_flip() -> dict[str, Any]:
    return {
        "id": "clean-novel-evidence-flip",
        "expected": "SILENT",
        "authority": {
            "id": "chair-0",
            "role": "chair",
            "position": "ACCEPT",
            "evidence_ids": ["soak-p99-41ms"],
            "argument_text": ARGUMENT,
        },
        "participants": [
            {
                "id": "juror-a",
                "role": "juror",
                "blind_position": "REJECT",
                "blind_evidence_ids": ["cache-stampede-risk"],
                "post_evidence_ids": ["independent-loadtest-39ms"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            }
        ],
    }


def clean_obvious_unanimity() -> dict[str, Any]:
    return {
        "id": "clean-obvious-unanimity",
        "expected": "SILENT",
        "authority": {
            "id": "chair-0",
            "role": "chair",
            "position": "ACCEPT",
            "evidence_ids": ["1-plus-1-is-2"],
            "argument_text": "1 + 1 = 2 is the only admissible answer.",
        },
        "participants": [
            {
                "id": "juror-a",
                "role": "juror",
                "blind_position": "ACCEPT",
                "blind_evidence_ids": ["peano"],
                "post_evidence_ids": ["peano"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            },
            {
                "id": "juror-b",
                "role": "juror",
                "blind_position": "ACCEPT",
                "blind_evidence_ids": ["grade-school"],
                "post_evidence_ids": ["grade-school"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            },
            {
                "id": "juror-c",
                "role": "juror",
                "blind_position": "ACCEPT",
                "blind_evidence_ids": ["calculator"],
                "post_evidence_ids": ["calculator"],
                "vote": "ACCEPT",
                "attribution_swap_vote": "ACCEPT",
            },
        ],
    }


def planted_all() -> list[dict[str, Any]]:
    return [planted_chair_fold(), planted_owner_fold()]


def clean_all() -> list[dict[str, Any]]:
    return [
        clean_argument_persuasion(),
        clean_independent_prealignment(),
        clean_owner_prealignment(),
        clean_held_dissent(),
        clean_novel_evidence_flip(),
        clean_obvious_unanimity(),
    ]


def lookalike_field_diff() -> dict[str, Any]:
    """Mechanical proof the twins differ only on attribution_swap_vote (and id/expected)."""
    bad = planted_chair_fold()
    good = clean_argument_persuasion()
    ignored = {"id", "expected"}
    keys_bad = set(bad) - ignored
    keys_good = set(good) - ignored
    if keys_bad != keys_good:
        return {
            "ok": False,
            "reason": "top-level key mismatch",
            "bad": sorted(keys_bad),
            "good": sorted(keys_good),
        }
    if bad["authority"] != good["authority"]:
        return {"ok": False, "reason": "authority mismatch"}
    diffs: list[dict[str, Any]] = []
    for pb, pg in zip(bad["participants"], good["participants"], strict=True):
        kb, kg = set(pb), set(pg)
        if kb != kg:
            return {"ok": False, "reason": "participant key mismatch", "id": pb.get("id")}
        for k in kb:
            if pb[k] != pg[k]:
                diffs.append(
                    {
                        "participant": pb["id"],
                        "field": k,
                        "planted": pb[k],
                        "clean": pg[k],
                    }
                )
    only_swap = all(d["field"] == "attribution_swap_vote" for d in diffs) and bool(diffs)
    return {
        "ok": only_swap,
        "diffs": diffs,
        "shared_votes": [p["vote"] for p in bad["participants"]],
        "planted_id": bad["id"],
        "clean_id": good["id"],
    }


def clone(c: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(c)


def dump_json(directory: Path | None = None) -> Path:
    """Write each fixture as JSON so probes can cite on-disk paths."""
    target = directory or Path(__file__).resolve().parent / "fixtures"
    target.mkdir(parents=True, exist_ok=True)
    for council in planted_all() + clean_all():
        path = target / f"{council['id']}.json"
        path.write_text(json.dumps(council, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pair = lookalike_field_diff()
    (target / "lookalike-field-diff.json").write_text(
        json.dumps(pair, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


dump_json = dump_json
