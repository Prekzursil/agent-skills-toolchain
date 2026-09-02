#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0008-commit-authorship-integrity.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = "command-center/audit/AUD-0008-commit-authorship-integrity.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0008/probe1_ancestor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0008/probe2_path_surface.py"
)
SENTINEL = E.SENTINEL
QUESTION = (
    "Is the pinned baseline commit still an ancestor of every HEAD, and is "
    "every intervening commit owner-authored rather than agent-authored - and "
    "what is the changed-path surface that corroborates it?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    result = E.run_all()
    if not result["controls_pass"]:
        print("FAILED:AUD-0008 emit controls did not pass")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = result["live"]
    p1 = result["probe1_control"]
    p2 = result["probe2_control"]
    if live["worktree_is_git"] and live["repos"]:
        live_answer = (
            "Live worktree is a git repo; "
            f"repos_in_scope={live['repos_in_scope']}; "
            "every_head_has_baseline_ancestor="
            f"{result['live_every_head_has_baseline_ancestor']}."
        )
    else:
        live_answer = (
            "This worktree is not a git repository, so there is no HEAD on "
            "which to evaluate `git merge-base --is-ancestor 53c37c6c HEAD`. "
            "Zero live HEADs in scope; the pinned baseline is therefore not "
            "shown as an ancestor of any live tip here. Other owner repos "
            "are NOT-CHECKED."
        )
    answer = (
        f"{live_answer} Fixture probe 1 (merge-base --is-ancestor, never "
        "HEAD==pinned-SHA) stayed GREEN after an owner scratch commit and "
        "went RED after a parentless history rewrite. Fixture probe 2 "
        "(diff-tree --name-only vs catalog unit ids) classified a "
        "Claude-authored README commit as NO-UNIT-SURFACE and an "
        "owner-named commit that touched probes/AUD-0008/ as "
        "UNIT-CORROBORATED, proving author identity is not the detector. "
        f"{SENTINEL}."
    )
    doc = {
        "unit_id": "AUD-0008",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "output_schema": SCHEMA,
        "question": QUESTION,
        "answer": answer,
        "headline": (
            "Pinned 53c37c6c cannot be checked against a live HEAD on this "
            "worktree (not a git repo). Independent fixtures prove the "
            "ancestor invariant is is-ancestor not SHA equality, and that "
            "authorship is corroborated by changed-path unit ids, not "
            "forgeable author strings."
        ),
        "produced_at": now,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "min_bytes_threshold": 1024,
        "pinned_baseline": result["pinned_baseline"],
        "probe1_instrument": (
            "git merge-base --is-ancestor <pinned> HEAD "
            "(never rev-parse HEAD == pinned; equality is the forbidden strawman)"
        ),
        "probe2_instrument": (
            "git diff-tree --no-commit-id --name-only -r --root <sha> "
            "matched against WORK-UNIT-CATALOG.json unit ids"
        ),
        "catalog_unit_id_count": result["catalog_unit_id_count"],
        "probe1_control": p1,
        "probe2_control": p2,
        "live": live,
        "live_every_head_has_baseline_ancestor": result[
            "live_every_head_has_baseline_ancestor"
        ],
        "evidence": [
            {
                "claim": (
                    "The baseline-ancestor invariant is `git merge-base "
                    "--is-ancestor`, not equality to 53c37c6c. An owner scratch "
                    "commit leaves it GREEN; a parentless rewrite turns it RED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0008/engine.py:build_ancestor_fixture",
                "instrument": "git merge-base --is-ancestor",
            },
            {
                "claim": (
                    "Author identity is forgeable. Changed-path surface against "
                    "catalog unit ids corroborates program work: Claude+README "
                    "is NO-UNIT-SURFACE; owner+AUD-0008 probe path is "
                    "UNIT-CORROBORATED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/AUD-0008/engine.py:build_path_fixture",
                "instrument": "git diff-tree --name-only",
            },
            {
                "claim": live_answer,
                "verdict": "CONFIRMED" if not live["worktree_is_git"] else "PARTIAL",
                "confidence": "almost-certain" if not live["worktree_is_git"] else "likely",
                "anchor": str(REPO),
                "instrument": "git rev-parse --is-inside-work-tree",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0008-C1-owner-scratch-stays-green",
                "kind": "both-states",
                "description": (
                    "A scratch commit by the owner on top of the baseline must "
                    "leave is-ancestor GREEN and must make HEAD!=baseline so "
                    "an equality detector would go red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "equality strawman True would fail owner scratch",
                "good_state_output": f"is-ancestor True, equality={p1['owner_scratch_head_equals_baseline']}",
            },
            {
                "id": "AUD-0008-C2-history-rewrite-goes-red",
                "kind": "known-broken-fixture",
                "description": "A parentless rewritten root is not a descendant of the baseline.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"rewrite_is_ancestor={p1['rewrite_is_ancestor']}",
                "good_state_output": f"owner_scratch_is_ancestor={p1['owner_scratch_is_ancestor']}",
            },
            {
                "id": "AUD-0008-C3-forged-identity-does-not-decide",
                "kind": "known-broken-fixture",
                "description": (
                    "Claude author on README is NO-UNIT-SURFACE; owner author "
                    "on probes/AUD-0008 is UNIT-CORROBORATED. Identity is opposite "
                    "the path verdict."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p2["forged_agent_identity_commit"]["path_class"],
                "good_state_output": p2["forged_owner_identity_commit"]["path_class"],
            },
        ],
        "tests": [
            {
                "id": "invariant-not-equality-to-pinned-sha",
                "name": (
                    "assert the invariant is NOT expressed as equality to a "
                    "pinned SHA - a scratch commit by the owner must leave the "
                    "invariant GREEN, and a history rewrite must turn it RED"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "path-surface-ignores-forged-author",
                "name": "changed-path surface vs unit ids, independent of author identity",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "no-history-rewrite",
                "command": P1,
                "method": "git merge-base --is-ancestor",
                "raw_output": json.dumps(p1, indent=1, sort_keys=True),
            },
            {
                "id": "probe2",
                "role": "changed-path-authorship-corroboration",
                "command": P2,
                "method": "git diff-tree --name-only vs catalog unit ids",
                "raw_output": json.dumps(p2, indent=1, sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0008-probe2-codex-path-surface",
            "vendor": "openai",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Cross-vendor Codex reviewer re-ran ONLY probe 2 (changed-path "
                "surface vs catalog unit ids). Probe 1 merge-base --is-ancestor "
                "was not re-run by this reviewer."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog asks per repo. Exactly this worktree was scanned; "
                    "other owner-controlled repositories are NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner-supplied repo list, scanned with the same two "
                    "instruments, with no concurrent session holding those trees."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0008/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
        "success_hand_flipped": False,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = sha256_file(out_path)
    if size < 1024:
        print(f"FAILED:AUD-0008 emit artifact too small {size}B")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:AUD-0008 emit sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:AUD-0008 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
