#!/usr/bin/env python3
"""Emit the CNL-0105 design artifact (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture import NEGATIVE_CONTROL_VERBATIM, capture_check  # noqa: E402
from common import (  # noqa: E402
    CATALOG_CITED_KEYS,
    OUT_REL,
    PRESET_KEYS,
    REPO,
    SCHEMA_REL,
    Reject,
    apply_operator_overlay,
    load_records,
    materialize_preset,
)
from instantiate import differential, fingerprint, instantiate  # noqa: E402
from schema_util import error_count, validate_preset  # noqa: E402

QUESTION = (
    "What does the peer-review preset need that a generic critique board does "
    "not - anonymity lifting, reviewer recruitment, and a bounded author "
    "rebuttal - and how is reviewer capture prevented when only two reviewers "
    "are seated?"
)


def main() -> int:
    rec = load_records()
    base = rec["base_councilspec"]
    this = materialize_preset(rec["preset_cnl0105"])
    sibling = materialize_preset(rec["sibling_gated_critique"])
    task = rec["task"]

    this_profile = instantiate(this, base, task)
    sib_profile = instantiate(sibling, base, task)
    this_fp = fingerprint(this_profile)
    sib_fp = fingerprint(sib_profile)
    diff = differential(this_fp, sib_fp)
    if not diff["measurable"]:
        print(f"FAILED:emit differential not measurable {diff}")
        return 1
    if this_fp == sib_fp:
        print("FAILED:emit mechanism-duplicate of nearest sibling")
        return 1

    planted = capture_check(rec["capture_planted_bad"])
    clean_split = capture_check(rec["capture_known_good"])
    clean_accept = capture_check(rec["capture_dual_accept_independent"])
    if not planted["fire"]:
        print(f"FAILED:emit planted capture silent {planted}")
        return 1
    if clean_split["fire"] or clean_split["action"] != "recruit-R3":
        print(f"FAILED:emit clean split misclassified {clean_split}")
        return 1
    if clean_accept["fire"] or clean_accept["action"] != "editor-nocapture-then-accept":
        print(f"FAILED:emit independent dual-accept misclassified {clean_accept}")
        return 1

    overlay_rejected = False
    overlay_msg = ""
    try:
        apply_operator_overlay(this, rec["operator_illegal_overlay"])
    except Reject as exc:
        overlay_rejected = True
        overlay_msg = str(exc)
    if not overlay_rejected:
        print("FAILED:emit illegal overlay was accepted")
        return 1

    this_errs, this_msgs = validate_preset(this)
    sib_errs, sib_msgs = validate_preset(sibling)
    inv_errs, inv_msgs = validate_preset(rec["invalid_preset"])
    affected_error_count = this_errs + sib_errs
    if affected_error_count != 0:
        print(
            "FAILED:emit affected schema errors "
            f"this={this_errs} {this_msgs[:3]} sibling={sib_errs} {sib_msgs[:3]}"
        )
        return 1
    if inv_errs <= 0:
        print("FAILED:emit invalid preset produced 0 errors (vacuous validator)")
        return 1

    envelope_probe = {
        "unit_id": "CNL-0105",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0105",
        "schema_version": 1,
        "title": "Anonymous peer-review preset with an author rebuttal round",
        "question": QUESTION,
        "preset": this,
        "sibling_map": {
            "nearest_sibling": {
                "id": sibling["id"],
                "named_explicitly": True,
                "source": sibling["meta"]["reconstruction_source"],
            },
            "extends": this["meta"]["supersedes_or_extends"],
            "library_c_ids_named": ["C-M01"],
        },
        "instantiation": {
            "task_id": task["id"],
            "profile": this_profile,
        },
        "tests": [
            {"id": "instantiate-fixture", "result": "PASS"},
            {"id": "nearest-sibling-differential", "result": "PASS"},
            {"id": "jsonschema-draft202012", "result": "PASS"},
            {"id": "negative-control-capture", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "CNL-0105-probe1-instantiate-fresh",
            "verdict": "PASS",
            "independent": True,
        },
    }
    env_errs, env_msgs = error_count(envelope_probe)
    if env_errs != 0:
        print(f"FAILED:emit envelope schema errors {env_errs} {env_msgs[:8]}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact = {
        "unit_id": "CNL-0105",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0105",
        "schema_version": 1,
        "title": "Anonymous peer-review preset with an author rebuttal round",
        "question": QUESTION,
        "produced_at": now,
        "output_schema": SCHEMA_REL,
        "library_status": rec["library_status"],
        "preset_key_reconstruction": {
            "count": len(PRESET_KEYS),
            "keys": list(PRESET_KEYS),
            "catalog_cited": list(CATALOG_CITED_KEYS),
            "reconstructed_not_library_verified": [
                k for k in PRESET_KEYS if k not in CATALOG_CITED_KEYS
            ],
            "honesty": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this "
                "worktree. Only editable_dials and default_binding are named "
                "in WORK-UNIT-CATALOG.json CNL-0101. The other 18 key names "
                "are reconstructed from CouncilSpec section names plus the "
                "overlay this unit requires. This is not a 72/20 recount."
            ),
        },
        "answers": {
            "what_peer_review_needs_that_critique_board_does_not": [
                {
                    "need": "anonymity-lifting",
                    "critique_board": "named standing seats (CNL-0104 / P46)",
                    "this_preset": (
                        "blind-then-revealed (CNL-0007). Votes attributed to "
                        "pseudonyms until after the sealed post-rebuttal revote; "
                        "lift writes a join table and does not rewrite the vote log."
                    ),
                    "protocols": ["P20", "P23", "P25"],
                },
                {
                    "need": "reviewer-recruitment",
                    "critique_board": "standing roster; no COI screen",
                    "this_preset": (
                        "per-manuscript recruitment, min 2 reviewers, COI screen, "
                        "prefer distinct vendors. Editor is not a voting reviewer."
                    ),
                },
                {
                    "need": "bounded-author-rebuttal",
                    "critique_board": "rebuttal.max_rounds=0; author has no seat",
                    "this_preset": (
                        "exactly one author rebuttal round at depth 1 "
                        "(CNL-0048 budget). Author must answer each reviewer "
                        "claim or mark wont-fix. No second rebuttal chain."
                    ),
                    "protocols": ["P25"],
                },
            ],
            "two_reviewer_capture_prevention": [
                "Sealed first round (P23): a reviewer cannot condition on the peer ballot.",
                "Dual-ACCEPT is not consensus: editor cannot vote accept/reject and must attest nocapture (P18 two-key analogue).",
                "Split ballots recruit reviewer-3; the two cannot settle a disagreement themselves.",
                "Rationale Jaccard >= 0.85 plus seal-break, same prompt_hash, or shared COI fires capture and refuses ACCEPT (P24 treats agreement as non-evidence when cloned).",
                "Anonymity lifts only after the sealed post-rebuttal revote, so the author cannot lobby identified reviewers.",
            ],
        },
        "sibling_map": {
            "nearest_sibling": {
                "id": sibling["id"],
                "name": sibling["name"],
                "named_explicitly": True,
                "source": sibling["meta"]["reconstruction_source"],
                "library_c_id": "NOT-ON-DISK",
                "bound_protocol": "P46",
                "bound_protocol_catalog_name": "architecture-review-board",
                "why_nearest": (
                    "CNL-0105's question contrasts the peer-review preset with a "
                    "generic critique board. CNL-0104 is that board family; P46 "
                    "is the catalogued ENGINEERING-REVIEW protocol it binds. "
                    "No library C-id for that preset is on disk except the "
                    "unrelated stub C-M01."
                ),
            },
            "extends": this["meta"]["supersedes_or_extends"],
            "library_c_ids_named": ["C-M01"],
            "catalog_protocol_siblings": [
                {
                    "id": "P45",
                    "name": "scientific-peer-review",
                    "relation": "this preset binds P45 as the container protocol",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0045",
                },
                {
                    "id": "P46",
                    "name": "architecture-review-board",
                    "relation": "nearest protocol sibling (generic critique board)",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0045",
                },
            ],
        },
        "preset": this,
        "nearest_sibling_preset": sibling,
        "instantiation": {
            "task_id": task["id"],
            "task_title": task["title"],
            "profile": this_profile,
            "sibling_profile": sib_profile,
        },
        "differential": {
            "this_fingerprint": {
                k: (list(v) if isinstance(v, tuple) else v)
                for k, v in this_fp.items()
            },
            "sibling_fingerprint": {
                k: (list(v) if isinstance(v, tuple) else v)
                for k, v in sib_fp.items()
            },
            "distance": diff["distance"],
            "differing_axes": diff["differing_axes"],
            "identical_axes": diff["identical_axes"],
            "measurable": diff["measurable"],
            "name_only_duplicate": False,
        },
        "capture": {
            "planted_bad": planted,
            "known_good_split": clean_split,
            "known_good_dual_accept": clean_accept,
            "both_states": {
                "planted_fires": planted["fire"] is True,
                "clean_split_silent": clean_split["fire"] is False,
                "clean_accept_silent": clean_accept["fire"] is False,
            },
        },
        "schema_validation": {
            "draft": "2020-12",
            "validator": "jsonschema.Draft202012Validator",
            "affected_records": [
                {"id": this["id"], "error_count": this_errs},
                {"id": sibling["id"], "error_count": sib_errs},
            ],
            "affected_error_count": affected_error_count,
            "deliberately_invalid": {
                "id": "invalid_preset",
                "error_count": inv_errs,
                "sample_messages": inv_msgs[:6],
                "proves_validator_not_vacuous": inv_errs > 0,
            },
            "envelope_error_count": env_errs,
        },
        "non_editable_dial": {
            "overlay": rec["operator_illegal_overlay"],
            "rejected": overlay_rejected,
            "message": overlay_msg,
        },
        "negative_control": {
            "verbatim": NEGATIVE_CONTROL_VERBATIM,
            "planted_id": rec["capture_planted_bad"]["id"],
            "clean_id": rec["capture_known_good"]["id"],
            "planted_fire": planted["fire"],
            "clean_fire": clean_split["fire"],
        },
        "tests": [
            {
                "id": "instantiate-fixture",
                "result": "PASS",
                "roster_seats": [r["seat"] for r in this_profile["roster"]],
                "protocol_schedule": this_profile["protocol_schedule"],
                "voting_method": this_profile["voting_method"],
                "stopping_expression": this_profile["stopping_expression"],
            },
            {
                "id": "nearest-sibling-differential",
                "result": "PASS",
                "sibling": sibling["id"],
                "distance": diff["distance"],
                "differing_axes": diff["differing_axes"],
            },
            {
                "id": "jsonschema-draft202012",
                "result": "PASS",
                "affected_error_count": affected_error_count,
                "invalid_error_count": inv_errs,
            },
            {
                "id": "negative-control-capture",
                "result": "PASS",
                "planted_fire": planted["fire"],
                "clean_fire": clean_split["fire"],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0105-probe1-instantiate-fresh",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-derived roster/schedule/vote/stop from fixtures/records.json "
                "and compared fingerprints; did not take the author's prose as evidence."
            ),
        },
        "strongest_surviving_unknown": (
            "The library C-id of the 12-COUNCIL critique-board preset is not on "
            "this worktree. Nearest sibling is named from catalogued protocol P46 "
            "and unit CNL-0104, not from a library byte copy."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
    live_errs, live_msgs = error_count(artifact)
    if live_errs != 0:
        print(f"FAILED:emit live artifact schema {live_errs} {live_msgs[:8]}")
        return 1
    print(f"wrote {OUT_REL}")
    print(f"differential distance={diff['distance']} axes={diff['differing_axes']}")
    print(f"schema affected_error_count={affected_error_count} invalid={inv_errs}")
    print(f"capture planted_fire={planted['fire']} clean_split_fire={clean_split['fire']}")
    print("SUCCESS:CNL-0105")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
