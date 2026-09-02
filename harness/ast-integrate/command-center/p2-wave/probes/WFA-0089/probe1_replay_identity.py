#!/usr/bin/env python3
"""Probe 1: three-run replay identity after the nondeterminism repair.

Catalog evidence A: identical inputs yield byte-identical stage sequences and
artifact hashes, excluding fields declared as timestamps up front.

Catalog tests:
  * declared-nondeterministic fields enumerated before any diff
  * replay at least three times (two-run match can be low-entropy coincidence)
  * both-states: the unrepaired interpreter must diverge
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.wfa.nondeterminism import (  # noqa: E402
    DECLARED_NONDETERMINISTIC_FIELDS,
    execute_repaired,
    leaky_diverges,
    leaky_ir,
    repair_ir,
    replay_hashes,
    sha256_hex,
    canonical_bytes,
)

UNIT = "WFA-0089"
ART = REPO / "command-center/wfa/WFA-0089-repair-nondeterminism.json"
SEED_A = 20260824
SEED_B = 87451203
RUN_ROOT = "/fixed/wfa-0089/run-root"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0089-probe1 {msg}")
    return 1


def main() -> int:
    declared = sorted(DECLARED_NONDETERMINISTIC_FIELDS)
    print(f"declared_nondeterministic_fields_before_replay={declared}")
    if not declared:
        return fail("declared-nondeterministic set is empty (must be enumerated up front)")
    if "recorded_at" not in DECLARED_NONDETERMINISTIC_FIELDS:
        return fail("recorded_at must be declared before replay, not discovered after a diff")

    leaky = leaky_ir()
    leaky_ctl = leaky_diverges(leaky, attempts=8)
    print(
        f"leaky_diverges={leaky_ctl['diverges']} "
        f"distinct={leaky_ctl['distinct_stage_hashes']}"
    )
    if not leaky_ctl["diverges"]:
        return fail("unrepaired interpreter produced identical stage hashes (vacuous repair)")

    repaired = repair_ir(leaky)
    replay = replay_hashes(repaired, seed=SEED_A, run_root=RUN_ROOT, n=3)
    print(json.dumps({k: replay[k] for k in (
        "n",
        "stage_sequences_identical",
        "comparable_identical",
        "declared_fields",
        "varying_artifact_keys",
        "undeclared_varying_keys",
        "stage_sequence_sha256",
        "comparable_sha256",
    )}, sort_keys=True))
    if replay["n"] < 3:
        return fail("replay ran fewer than three times")
    if not replay["stage_sequences_identical"]:
        return fail(f"stage sequences diverged: {replay['stage_sequence_sha256']}")
    if not replay["comparable_identical"]:
        return fail(f"comparable artifacts diverged: {replay['comparable_sha256']}")
    if replay["undeclared_varying_keys"]:
        return fail(
            "undeclared fields varied across runs "
            f"{replay['undeclared_varying_keys']}; do not enlarge the exclusion set after the fact"
        )
    extra = set(replay["varying_artifact_keys"]) - DECLARED_NONDETERMINISTIC_FIELDS
    if extra:
        return fail(f"varying keys not in the pre-declared set: {sorted(extra)}")

    other = execute_repaired(
        repaired, seed=SEED_B, run_root=RUN_ROOT, include_receipt_timestamp=False
    )
    same = execute_repaired(
        repaired, seed=SEED_A, run_root=RUN_ROOT, include_receipt_timestamp=False
    )
    h_same = sha256_hex(canonical_bytes(same.comparable()))
    h_other = sha256_hex(canonical_bytes(other.comparable()))
    print(f"seed_a_comparable={h_same} seed_b_comparable={h_other}")
    if h_same == h_other:
        return fail("different seeds produced identical comparable artifacts (frozen sampler)")
    if h_same != replay["comparable_sha256"][0]:
        return fail("independent seed-A run did not match the three-run comparable hash")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0089" not in text:
        return fail("sentinel SUCCESS:WFA-0089 absent")
    declared_in_art = doc.get("declared_nondeterministic_fields") or []
    if set(declared_in_art) != set(declared):
        return fail(f"artifact declared fields {declared_in_art} != library {declared}")

    print("SUCCESS:WFA-0089-probe1 three-run replay identity after repair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
