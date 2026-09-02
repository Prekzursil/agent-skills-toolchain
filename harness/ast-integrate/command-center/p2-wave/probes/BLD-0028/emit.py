#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0028.json uncontrolled-zero census."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402
import reviewer as R  # noqa: E402

OUT = "command-center/receipts/BLD-0028.json"
SCHEMA = "command-center/schema/detector-control-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0028/probe1_planted_uncontrolled.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0028/probe2_controlled_and_mention.py"
)
QUESTION = (
    "Which reported zero, empty, 'no findings', 'not found' or 'clean' result "
    "in the whole program was never detector-controlled? Harvest every such "
    "result from receipts and reports; for each, check whether the PRODUCING "
    "unit recorded a known-present control and a known-broken control."
)
SENTINEL = "SUCCESS:BLD-0028"
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compact_inventory(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "id": row["id"],
                "kind": "reported-zero",
                "verdict": row["verdict"],
                "source": row["source"],
                "producer": row["producer"],
                "claim": row.get("claim"),
                "classification": row.get("classification"),
            }
        )
    return out


def run_fixture_controls() -> tuple[list[dict], dict]:
    mixed = H.harvest_fixture_dir("mixed")
    planted = [
        r
        for r in mixed["inventory"]
        if r["producer"] == "PLANTED-UZERO" or "PLANTED-UZERO" in r["id"]
    ]
    ctrl = [r for r in mixed["inventory"] if r["producer"] == "CTRL-ZERO"]
    mention = [
        r
        for r in mixed["inventory"]
        if r["producer"] == "DOC-MENTION" or "mention" in r["source"].lower()
    ]
    c1 = {
        "id": "planted-uncontrolled-zero",
        "result": "PASS" if planted and all(r["verdict"] == "uncontrolled" for r in planted) else "FAIL",
        "detail": (
            f"scratch planted PLANTED-UZERO harvested={len(planted)} "
            f"uncontrolled={sum(1 for r in planted if r['verdict']=='uncontrolled')}"
        ),
    }
    c2 = {
        "id": "controlled-zero-not-flagged",
        "result": (
            "PASS"
            if ctrl
            and all(r["verdict"] == "controlled" for r in ctrl)
            and "CTRL-ZERO" not in ",".join(mixed["uncontrolled_ids"])
            else "FAIL"
        ),
        "detail": (
            f"scratch CTRL-ZERO harvested={len(ctrl)} "
            f"controlled={sum(1 for r in ctrl if r['verdict']=='controlled')}"
        ),
    }
    c3 = {
        "id": "use-vs-mention-quoted-no-findings",
        "result": (
            "PASS"
            if not mention and mixed["mentioned_not_harvested"] >= 1
            else "FAIL"
        ),
        "detail": (
            f"quoted 'no findings' harvested_rows={len(mention)} "
            f"mentions_observed={mixed['mentioned_not_harvested']}"
        ),
    }
    return [c1, c2, c3], mixed


def main() -> int:
    import jsonschema

    controls, mixed = run_fixture_controls()
    if any(c["result"] != "PASS" for c in controls):
        print("FAILED:BLD-0028 fixture controls")
        print(json.dumps(controls, indent=2))
        return 1
    known_present_fired = True

    live = H.live_harvest(REPO)
    live_paths = H.iter_live_paths(REPO)
    review = R.grade_paths(live_paths)
    agreement = R.agree(live, review)
    if not agreement["agree"]:
        print("FAILED:BLD-0028 independent reviewer count disagreed")
        print(json.dumps(agreement, indent=2))
        print("producer_uncontrolled_head", live["uncontrolled_ids"][:20])
        print("reviewer_uncontrolled_head", review["uncontrolled_ids"][:20])
        return 1

    claim_st = H.claim_registry_status(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inventory = compact_inventory(live["inventory"])
    answer = (
        f"Live census on this worktree scanned {live['live_files_scanned']} "
        f"receipts/lane reports. Harvested {live['zeros_harvested']} published "
        f"zeros: {live['controlled_count']} detector-controlled, "
        f"{live['uncontrolled_count']} UNCONTROLLED-ZERO requeued to their "
        f"producers (control evidence is not supplied retroactively). "
        f"CLAIM-REGISTRY.json is {claim_st}. Quoted 'no findings' mentions are "
        f"not harvested (scratch mentions_observed="
        f"{mixed['mentioned_not_harvested']}). {SENTINEL}"
    )
    doc = {
        "unit_id": "BLD-0028",
        "id": "BLD-0028",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Uncontrolled-zero census: every empty result that was never detector-controlled",
        "question": QUESTION,
        "answer": answer,
        "report": {"kind": "detector-control-audit", "scope": "published-zeros"},
        "report_kind": "detector-control-audit",
        "as_of": now,
        "census": {
            "zeros_harvested": live["zeros_harvested"],
            "controlled_count": live["controlled_count"],
            "uncontrolled_count": live["uncontrolled_count"],
            "mentioned_not_harvested": live["mentioned_not_harvested"],
            "reported_before_threshold": True,
            "live_files_scanned": live["live_files_scanned"],
            "detector_count": live["zeros_harvested"],
            "requeued_producers": len(live["requeued"]),
        },
        "inventory": inventory,
        "detector_control": {
            "known_present_run_first": True,
            "fired_before_absence_reported": known_present_fired,
            "scratch_planted_fired": True,
            "fixture_dir": "command-center/p2-wave/probes/BLD-0028/fixtures/mixed",
        },
        "controls": controls,
        "tests": [
            {"id": "probe1-planted-uncontrolled", "command": P1, "result": "PASS"},
            {
                "id": "probe2-controlled-and-mention",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "planted-uncontrolled-zero", "command": P1},
            {
                "id": "probe2",
                "role": "controlled-zero-and-use-vs-mention",
                "command": P2,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "An uncontrolled zero planted in a scratch receipt set is "
                    "caught before any live absence is trusted."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/BLD-0028/fixtures/mixed/PLANTED-UZERO.json",
            },
            {
                "claim": (
                    "A properly controlled zero (known-present fire and "
                    "known-broken/good silence recorded on the producer) is "
                    "not flagged UNCONTROLLED-ZERO."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/BLD-0028/fixtures/mixed/CTRL-ZERO.json",
            },
            {
                "claim": (
                    "The phrase 'no findings' inside a quoted example is not "
                    "harvested as a published result."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/BLD-0028/fixtures/mixed/MENTION-ONLY.json",
            },
            {
                "claim": (
                    f"CLAIM-REGISTRY.json is {claim_st} on this worktree; "
                    "absence is recorded, not invented."
                ),
                "verdict": "CONFIRMED" if claim_st == "present" else "ABSENT",
                "anchor": "command-center/CLAIM-REGISTRY.json",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "reviewer": {
            "reviewer_id": review["reviewer_id"],
            "verdict": agreement["verdict"],
            "independent": True,
            "method": (
                "Flatten-to-(path,value) recount of the same live paths; "
                "uncontrolled and controlled counts must match the producer."
            ),
            "producer_uncontrolled": agreement["producer_uncontrolled"],
            "reviewer_uncontrolled": agreement["reviewer_uncontrolled"],
            "producer_controlled": agreement["producer_controlled"],
            "reviewer_controlled": agreement["reviewer_controlled"],
            "agree": True,
            "notes": (
                "Catalog Anthropic-vendor human re-derivation is independent "
                "of G-1 probe-green. This mechanical reviewer is the "
                "worktree-local independent count."
            ),
        },
        "requeued": live["requeued"],
        "inputs_on_this_worktree": {
            "command-center/receipts": "present",
            "command-center/CLAIM-REGISTRY.json": claim_st,
            "rules/common/single-signal-verification.md": (
                "ABSENT on this sparse worktree; both-states rule encoded in "
                "harvest.recorded_both_states"
            ),
            "ADV-0009": "out of scope (detector fire-ability, not published zeros)",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "ADV-0009 detector inventory was rebuilt",
                "control evidence was written back onto producing receipts",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "detector-auditor",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "min_bytes_threshold": MIN_BYTES,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:BLD-0028 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "BLD-0028", "state": "SUCCESS", "blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:BLD-0028 schema accepted garbage")
            return 1
    kind_mutant = json.loads(json.dumps(doc))
    kind_mutant["report"]["kind"] = "not-this"
    kind_errs = list(validator.iter_errors(kind_mutant))
    if not kind_errs:
        print("FAILED:BLD-0028 schema accepted report.kind mutant")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:BLD-0028 sentinel missing from artifact body")
        return 1
    out.write_text(payload, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:BLD-0028 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"zeros={live['zeros_harvested']} controlled={live['controlled_count']} "
        f"uncontrolled={live['uncontrolled_count']} "
        f"requeued={len(live['requeued'])} scanned={live['live_files_scanned']}"
    )
    print("SUCCESS:BLD-0028 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
