#!/usr/bin/env python3
"""Probe 1: abandoned-work-salvage both-states.

Ancestry-only delete authorization is refused, including the regular-merge
case where a naive is-ancestor policy would authorize. The same candidate
is authorized when a byte-level content-equality proof is supplied.
A squash-merge AHEAD candidate is also authorized only via content equality
or PR-merged state, never via ancestry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from eng_blueprints_17_21.library import load_library, omission_gate  # noqa: E402
from eng_blueprints_17_21.salvage import (  # noqa: E402
    AUTHORIZE,
    REFUSE,
    ancestry_only_would_authorize,
    ancestry_proof,
    content_equality_proof,
    decide,
    pr_merged_proof,
)

RAW = HERE / "probe1-ancestry.raw.json"
DIGEST = "a" * 64
OTHER = "b" * 64


def main() -> int:
    library = load_library()
    expected = {
        "bp.benchmark-generation",
        "bp.reproducibility",
        "bp.performance",
        "bp.concurrency-load-soak",
        "bp.abandoned-work-salvage",
    }
    if set(library) != expected:
        print("FAILED:IMP-0242-probe1 library ids", sorted(library))
        return 1
    reasons = omission_gate()
    if len(reasons) != 6 or len(set(reasons.values())) != 6:
        print("FAILED:IMP-0242-probe1 omission gate", reasons)
        return 1

    regular = {"id": "wt-regular-merge", "git_ahead_state": "EQUAL"}
    squash = {"id": "wt-squash-ahead", "git_ahead_state": "AHEAD"}

    ancestry_only = [ancestry_proof(is_ancestor_of_main=True)]
    refused_regular = decide(regular, ancestry_only)
    if refused_regular["decision"] != REFUSE:
        print("FAILED:IMP-0242-probe1 ancestry-only was authorized", json.dumps(refused_regular))
        return 1
    if not ancestry_only_would_authorize(ancestry_only):
        print("FAILED:IMP-0242-probe1 naive ancestry control did not fire")
        return 1
    if refused_regular["naive_ancestry_would_authorize"] is not True:
        print("FAILED:IMP-0242-probe1 naive control not recorded")
        return 1
    if refused_regular["ancestry_sufficient"] is not False:
        print("FAILED:IMP-0242-probe1 ancestry marked sufficient")
        return 1
    if refused_regular["refused_because"] != "ancestry-only-insufficient":
        print("FAILED:IMP-0242-probe1 refuse reason", refused_regular)
        return 1

    content_proofs = [
        ancestry_proof(is_ancestor_of_main=True),
        content_equality_proof(local_sha256=DIGEST, preserved_sha256=DIGEST),
    ]
    accepted_content = decide(regular, content_proofs)
    if accepted_content["decision"] != AUTHORIZE:
        print("FAILED:IMP-0242-probe1 content equality not authorized", accepted_content)
        return 1
    if accepted_content["authorized_by"] != "content-equality":
        print("FAILED:IMP-0242-probe1 authorized_by not content-equality", accepted_content)
        return 1

    mismatch = decide(
        regular,
        [content_equality_proof(local_sha256=DIGEST, preserved_sha256=OTHER)],
    )
    if mismatch["decision"] != REFUSE:
        print("FAILED:IMP-0242-probe1 digest mismatch authorized", mismatch)
        return 1

    squash_ancestry = decide(
        squash, [ancestry_proof(is_ancestor_of_main=False)]
    )
    if squash_ancestry["decision"] != REFUSE:
        print("FAILED:IMP-0242-probe1 squash ancestry authorized", squash_ancestry)
        return 1

    squash_content = decide(
        squash,
        [
            ancestry_proof(is_ancestor_of_main=False),
            content_equality_proof(local_sha256=DIGEST, preserved_sha256=DIGEST),
        ],
    )
    if squash_content["decision"] != AUTHORIZE:
        print("FAILED:IMP-0242-probe1 squash content not authorized", squash_content)
        return 1

    pr_ok = decide(squash, [pr_merged_proof(merged=True)])
    if pr_ok["decision"] != AUTHORIZE or pr_ok["authorized_by"] != "pr-merged":
        print("FAILED:IMP-0242-probe1 PR-merged not authorized", pr_ok)
        return 1

    doc = {
        "ancestry_only_refused": True,
        "both_states": True,
        "content_equality_authorized": True,
        "digest_mismatch_refused": True,
        "naive_ancestry_would_authorize": True,
        "omission_reason_ids": reasons,
        "pass": True,
        "pr_merged_authorized": True,
        "squash_ahead_ancestry_refused": True,
        "squash_ahead_content_authorized": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "ancestry_only_refused=True content_equality_authorized=True "
        "naive_ancestry_would_authorize=True squash_ahead_content_authorized=True"
    )
    print("SUCCESS:IMP-0242-probe1 ancestry-only refused; content-proof accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
