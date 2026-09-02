"""Four downstream consumers of a council record.

Production simulate/synthesis (tools/council/simulate.py, CNL-0070/0097/0120)
is absent on this worktree. tools/council/vote/tally.py records outcome
arithmetic only and does not carry dissent text. The live object under test
is this pipeline, disclosed in the ADV-0097 artifact. It does not rebuild
ADV-0109.

Policies
  husk     — default. Majority copied in full. Dissent reduced to the unique
             token with no claim/counterexample. Minority report is not a
             first-class manifest entry.
  omit     — majority only; dissent token and claim both stripped at synthesis.
  preserve — majority and full minority (claim + counterexample + token)
             copied into every text stage and registered on the manifest.
  drop_majority — control mutant: majority stripped; dissent preserved.
"""
from __future__ import annotations

import json
from typing import Any

from fixture import (
    COUNTEREXAMPLE_ID,
    DISSENT_CLAIM,
    DISSENT_COUNTEREXAMPLE,
    DISSENT_TOKEN,
    MAJORITY_CLAIM,
    MAJORITY_TOKEN,
    STAGES,
    council as load_council,
)

POLICIES = ("husk", "omit", "preserve", "drop_majority")


def _blob(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, ensure_ascii=True)


def _majority_block() -> dict:
    return {
        "recommendation": MAJORITY_CLAIM,
        "majority_token": MAJORITY_TOKEN,
        "body": f"{MAJORITY_CLAIM} {MAJORITY_TOKEN}",
    }


def _full_minority_block() -> dict:
    return {
        "dissent_token": DISSENT_TOKEN,
        "claim": DISSENT_CLAIM,
        "counterexample": DISSENT_COUNTEREXAMPLE,
        "counterexample_id": COUNTEREXAMPLE_ID,
        "body": (
            f"{DISSENT_CLAIM} {DISSENT_COUNTEREXAMPLE} {DISSENT_TOKEN}"
        ),
    }


def _husk_minority_block() -> dict:
    return {
        "dissent_token": DISSENT_TOKEN,
        "claim": "",
        "counterexample": "",
        "note": (
            f"Minority noted ({DISSENT_TOKEN}). Dissent was recorded."
        ),
        "body": f"Minority noted ({DISSENT_TOKEN}). Dissent was recorded.",
    }


def synthesize(src: dict, policy: str) -> dict:
    include_majority = policy != "drop_majority"
    if policy == "preserve" or policy == "drop_majority":
        minority = _full_minority_block()
    elif policy == "husk":
        minority = _husk_minority_block()
    elif policy == "omit":
        minority = None
    else:
        raise ValueError(f"unknown policy {policy!r}")
    doc: dict[str, Any] = {
        "stage": "synthesis",
        "policy": policy,
        "council_id": src["council_id"],
        "outcome": src["tally"]["outcome"],
        "majority": _majority_block() if include_majority else None,
        "minority": minority,
    }
    return doc


def digest(synthesis: dict) -> dict:
    maj = synthesis.get("majority") or {}
    mino = synthesis.get("minority") or {}
    parts = [p for p in (maj.get("body"), mino.get("body")) if p]
    return {
        "stage": "digest",
        "policy": synthesis["policy"],
        "summary": " ".join(parts),
        "majority_excerpt": maj.get("body", ""),
        "minority_excerpt": mino.get("body", ""),
    }


def artifact_manifest(synthesis: dict, digest_doc: dict) -> dict:
    policy = synthesis["policy"]
    entries = [
        {"role": "synthesis", "path": "synthesis.json"},
        {"role": "digest", "path": "digest.json"},
        {"role": "final_report", "path": "final_report.json"},
    ]
    mino = synthesis.get("minority")
    full = bool(mino and mino.get("claim") and mino.get("counterexample"))
    if policy in {"preserve", "drop_majority"} and full:
        entries.append(
            {
                "role": "minority_report",
                "path": "minority_report.json",
                "body": mino.get("body", ""),
            }
        )
    maj = synthesis.get("majority") or {}
    doc: dict = {
        "stage": "artifact_manifest",
        "policy": policy,
        "entries": entries,
        "digest_path": "digest.json",
        "synthesis_path": "synthesis.json",
    }
    if maj:
        # Majority remains a first-class registered recommendation. Dissent
        # is registered only when a minority_report entry exists.
        doc["majority_token"] = maj.get("majority_token", "")
        doc["majority_claim"] = maj.get("recommendation", "")
        doc["majority_body"] = maj.get("body", "")
    return doc


def final_report(synthesis: dict, digest_doc: dict) -> dict:
    maj = synthesis.get("majority") or {}
    mino = synthesis.get("minority") or {}
    return {
        "stage": "final_report",
        "policy": synthesis["policy"],
        "owner_packet": {
            "recommendation": maj.get("recommendation", ""),
            "majority_body": maj.get("body", ""),
            "minority_body": mino.get("body", ""),
            "digest": digest_doc.get("summary", ""),
        },
    }


def run_pipeline(policy: str, src: dict | None = None) -> dict:
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    src = src or load_council()
    syn = synthesize(src, policy)
    dig = digest(syn)
    man = artifact_manifest(syn, dig)
    fin = final_report(syn, dig)
    stages = {
        "transcript": src,
        "synthesis": syn,
        "digest": dig,
        "artifact_manifest": man,
        "final_report": fin,
    }
    return {
        "policy": policy,
        "stages": stages,
        "blobs": {name: _blob(doc) for name, doc in stages.items()},
    }


def stage_order() -> tuple[str, ...]:
    return STAGES
