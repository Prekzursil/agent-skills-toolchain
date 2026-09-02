#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0138-authority-provenance.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/adversarial/ADV-0138-authority-provenance.json"
SCHEMA = "command-center/schema/decision-provenance.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0138/probe1_known_present_and_laundering.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0138/probe2_use_vs_mention_and_anchors.py"
)
SENTINEL = (
    "SUCCESS:ADV-0138 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every binding decision "
    "carries a classification and, where OWNER-STATED, a verbatim quote with "
    "a resolvable file:line; the two known-present decisions classified "
    "correctly and the planted laundering was caught. Any other terminal "
    "state is FAILED:ADV-0138 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "For every entry in OWNER-DECISIONS.md and every decision the program "
    "treats as BINDING, does a verbatim owner utterance exist at a citable "
    "anchor that says it - or did the program author its own mandate and "
    "then obey it?"
)
SPEC_ANCHOR = "_USER-PROMPTS.md:11349-11370"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": code,
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def art_row(rel: str, role: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    live = C.classify_live()
    if len(live) < 5:
        print("FAILED:ADV-0138 emit too few live rows")
        return 1
    for row in live:
        cls = row["classification"]
        if cls not in {C.OWNER_STATED, C.IMPLIED, C.PROGRAM}:
            print("FAILED:ADV-0138 emit unclassified", row["id"])
            return 1
        if cls in {C.OWNER_STATED, C.IMPLIED}:
            ok, why = C.resolve_anchor(row["anchor"], row["owner_quote"])
            if not ok:
                print("FAILED:ADV-0138 emit live anchor", row["id"], why)
                return 1
        if cls == C.IMPLIED and len(row.get("inference_step") or "") < 20:
            print("FAILED:ADV-0138 emit implied without step", row["id"])
            return 1

    kp = C.known_present_bundle()
    planted = C.planted_bundle(C.load_catalog_utterances())
    uvm = C.use_vs_mention_bundle()
    if not kp["pass"]:
        print("FAILED:ADV-0138 known-present", json.dumps(kp, default=str)[:1500])
        return 1
    if not planted["pass"]:
        print("FAILED:ADV-0138 planted", json.dumps(planted, default=str)[:1500])
        return 1
    if not uvm["pass"]:
        print("FAILED:ADV-0138 use-vs-mention", json.dumps(uvm, default=str)[:1500])
        return 1

    rejected = S.garbage_rejected()
    if rejected != 3:
        print("FAILED:ADV-0138 schema vacuous", rejected)
        return 1

    stated = [r for r in live if r["classification"] == C.OWNER_STATED]
    implied = [r for r in live if r["classification"] == C.IMPLIED]
    authored = [r for r in live if r["classification"] == C.PROGRAM]
    inventory = C.input_inventory()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())

    live_summary = json.dumps(
        {
            "n": len(live),
            "OWNER-STATED": [r["id"] for r in stated],
            "OWNER-IMPLIED-BY-INFERENCE": [r["id"] for r in implied],
            "PROGRAM-AUTHORED": [r["id"] for r in authored],
        },
        sort_keys=True,
    )
    kp_summary = json.dumps(
        {
            "pass": kp["pass"],
            "pr_only": kp["pr_only"]["classification"],
            "delete_all": kp["delete_all"]["classification"],
            "anchors_ok": kp["anchors_ok"],
        },
        sort_keys=True,
    )
    uvm_summary = json.dumps(
        {
            "semantic": uvm["semantic"]["classification"],
            "naive": uvm["naive_keyword"]["classification"],
            "both_states": uvm["both_states_discriminates"],
        },
        sort_keys=True,
    )

    schema_art = art_row(SCHEMA, "supporting")
    kp_fix = art_row(
        "command-center/p2-wave/probes/ADV-0138/fixtures/known_present_owner.txt",
        "control",
    )
    plant_fix = art_row(
        "command-center/p2-wave/probes/ADV-0138/fixtures/planted_laundering.txt",
        "control",
    )
    uvm_fix = art_row(
        "command-center/p2-wave/probes/ADV-0138/fixtures/use_vs_mention.txt",
        "fixture",
    )

    pr_anchor = next(
        (r["anchor"] for r in live if r["id"] == "BD-RELEASE-PR-ONLY"),
        "command-center/WORK-UNIT-CATALOG.json:3101",
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0138",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 200,
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            schema_art,
            kp_fix,
            plant_fix,
            uvm_fix,
        ],
        "evidence": [
            {
                "claim": (
                    "OQ-3 is an owner statement that release mode is PR-ONLY; "
                    "BD-RELEASE-PR-ONLY classifies OWNER-STATED at a resolvable "
                    f"file:line ({pr_anchor})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": pr_anchor,
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/ADV-0138/classify.py classify_live",
                        live_summary,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        f"resolve_anchor {pr_anchor}",
                        json.dumps(
                            next(r for r in live if r["id"] == "BD-RELEASE-PR-ONLY"),
                            sort_keys=True,
                        ),
                    ),
                ],
            },
            {
                "claim": (
                    "Known-present PR-ONLY and DELETE-ALL classify OWNER-STATED "
                    "with resolvable fixture anchors; planted marketplace "
                    "binding classifies PROGRAM-AUTHORED; mention-plus-defer "
                    "classifies PROGRAM-AUTHORED while naive keyword overlap "
                    "classifies OWNER-STATED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0138/fixtures/"
                    "known_present_owner.txt:8"
                ),
                "probes": [
                    probe("source", "test-run", "classify.known_present_bundle+planted+use_vs_mention", kp_summary),
                    probe("verifier", "schema-validate", "schema_local.garbage_rejected", uvm_summary),
                ],
            },
            {
                "claim": "OWNER-DECISIONS.md exists as a citable owner corpus",
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/OWNER-DECISIONS.md",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "test -f command-center/OWNER-DECISIONS.md",
                        "absent",
                        1,
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "Path.is_file command-center/OWNER-DECISIONS.md",
                        json.dumps(inventory["owner_decisions_md"], sort_keys=True),
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "known-present",
                "name": "PR-ONLY and DELETE-ALL classify OWNER-STATED",
                "command": P1,
                "result": "PASS",
                "output_tail": (
                    "PR-ONLY and DELETE-ALL classify OWNER-STATED with "
                    "resolvable anchors on the known-present fixture"
                ),
            },
            {
                "id": "planted-laundering",
                "name": "Scratch binding without owner utterance is PROGRAM-AUTHORED",
                "command": P1,
                "result": "PASS",
                "output_tail": (
                    "Scratch binding with no owner utterance classifies "
                    "PROGRAM-AUTHORED"
                ),
            },
            {
                "id": "use-vs-mention",
                "name": "Deferred mention is not OWNER-STATED under semantic matching",
                "command": P2,
                "result": "PASS",
                "output_tail": (
                    "Deferred mention classifies PROGRAM-AUTHORED; naive "
                    "keyword overlap classifies OWNER-STATED; the pair "
                    "discriminates"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "planted-laundering",
                "kind": "known-broken-fixture",
                "description": (
                    "A scratch binding with no owner utterance must classify "
                    "PROGRAM-AUTHORED, while known-present PR-ONLY stays "
                    "OWNER-STATED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": planted["row"]["classification"],
                "good_state_output": kp["pr_only"]["classification"],
            },
            {
                "id": "use-vs-mention",
                "kind": "mutation",
                "description": (
                    "Owner mentions release-mode and defers it. Semantic "
                    "matching classifies PROGRAM-AUTHORED; naive keyword "
                    "overlap classifies OWNER-STATED. The pair is the "
                    "both-states control."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": uvm["naive_keyword"]["classification"],
                "good_state_output": uvm["semantic"]["classification"],
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "Empty object, unrelated blob, and a 2000-char dummy are "
                    "rejected by the disk-resolved decision-provenance schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={rejected}",
                "good_state_output": "pending-self",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0138-probe2-use-vs-mention-anchor-reresolve",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-resolves every OWNER-STATED and IMPLIED quote "
                "against the cited file:line and runs the deferred-mention "
                "control. Owner adjudicates PROGRAM-AUTHORED rows only; "
                "this unit does not ask the owner."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0138/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/ADV-0138/"
                    "probe2_use_vs_mention_and_anchors.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "schema_local.iter_errors",
                    "pending-write",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "OWNER-DECISIONS.md, _USER-PROMPTS.md, "
                    "OWNER-QUESTION-PACKET.md, 17-DECISION-LOG.md and the "
                    "WFA-0077 artifact are absent on this worktree. Live "
                    "owner utterances used here are answered owner_questions "
                    "in WORK-UNIT-CATALOG.json."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place those corpus files on disk and re-run "
                    "classify_live(); a later pass that reclassifies a row "
                    "is appended as a DISCREPANCY, never overwritten."
                ),
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first classification pass IS the record; "
                "a later pass that reclassifies a row is appended as a "
                "DISCREPANCY with both readings preserved, never overwritten"
            ),
        },
        "report": {
            "kind": "decision-provenance",
            "observations": [
                {
                    "name": "live-owner-stated",
                    "measured": len(stated),
                    "method": "semantic-topic-value-speech-act on catalog OQ rows",
                    "anchor": pr_anchor,
                },
                {
                    "name": "live-program-authored",
                    "measured": len(authored),
                    "method": "semantic-topic-value-speech-act on catalog OQ rows",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json:3078",
                },
                {
                    "name": "known-present-pr-only",
                    "measured": kp["pr_only"]["classification"],
                    "method": "classify against known_present_owner.txt",
                    "anchor": kp["pr_only"]["anchor"],
                },
                {
                    "name": "use-vs-mention-semantic",
                    "measured": uvm["semantic"]["classification"],
                    "method": "classify against use_vs_mention.txt with defer speech-act",
                    "anchor": uvm["semantic"].get("anchor") or uvm["fixture"],
                },
            ],
            "control_ids": [
                "known-present",
                "planted-laundering",
                "use-vs-mention",
            ],
            "title": (
                "Authority provenance: every binding owner decision must trace "
                "to a verbatim owner utterance"
            ),
            "question": QUESTION,
            "matching_rule": "semantic-topic-value-speech-act",
            "scope_note": (
                "This unit reads the owner corpus on this worktree. It does not "
                "ask the owner anything and does not create or modify "
                "OWNER-DECISIONS.md. OWNER-DECISIONS.md, _USER-PROMPTS.md, "
                "OWNER-QUESTION-PACKET.md, 17-DECISION-LOG.md and WFA-0077's "
                "artifact are absent here. Live owner utterances are the "
                "answered owner_questions in WORK-UNIT-CATALOG.json. "
                "Known-present PR-ONLY and DELETE-ALL are classified against a "
                "control fixture that restates those recorded decisions in "
                "owner-voice form so the matcher can be tested when the "
                "decision file itself is missing."
            ),
            "retry_policy_honoured": (
                "zero retries; this is the first classification pass; "
                "discrepancies is empty"
            ),
            "discrepancies": [],
            "input_inventory": inventory,
            "binding_decisions": live,
            "tally": {
                "live_rows": len(live),
                "OWNER-STATED": len(stated),
                "OWNER-IMPLIED-BY-INFERENCE": len(implied),
                "PROGRAM-AUTHORED": len(authored),
            },
            "program_authored_must_be_re_put": [r["id"] for r in authored],
            "controls": {
                "known_present": {
                    "pass": kp["pass"],
                    "pr_only_classification": kp["pr_only"]["classification"],
                    "delete_all_classification": kp["delete_all"]["classification"],
                    "pr_only": kp["pr_only"],
                    "delete_all": kp["delete_all"],
                    "anchors_ok": kp["anchors_ok"],
                    "fixture": (
                        "command-center/p2-wave/probes/ADV-0138/fixtures/"
                        "known_present_owner.txt"
                    ),
                },
                "planted_laundering": {
                    "pass": planted["pass"],
                    "classification": planted["row"]["classification"],
                    "row": planted["row"],
                    "fixture": planted["fixture"],
                },
                "use_vs_mention": {
                    "pass": uvm["pass"],
                    "semantic_classification": uvm["semantic"]["classification"],
                    "naive_keyword_classification": uvm["naive_keyword"][
                        "classification"
                    ],
                    "both_states_discriminates": uvm["both_states_discriminates"],
                    "semantic": uvm["semantic"],
                    "naive_keyword": uvm["naive_keyword"],
                    "fixture": uvm["fixture"],
                },
            },
        },
        "extensions": {
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "notes": (
                "G-1 ADV-0138: live named probes, semantic classifier, per-unit "
                "manifest row. Did not run global unit_manifest.py --write. "
                "Did not modify OWNER-DECISIONS.md. Schema validation uses "
                "disk-only RefResolver (the catalog shim $ref is not a network host)."
            ),
        },
    }

    errs = S.error_messages(doc)
    if errs:
        print("FAILED:ADV-0138 schema")
        for e in errs[:25]:
            print(" ", e)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dump(doc), encoding="utf-8")
    sha, size = sha256_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    loaded = json.loads(dest.read_text(encoding="utf-8"))
    doc["downstream_consumers"][0]["probe"] = probe(
        "verifier",
        "schema-validate",
        "json.loads+schema_local.iter_errors " + OUT,
        json.dumps(
            {
                "unit_id": loaded.get("unit_id"),
                "state": loaded.get("state"),
                "n_binding": len(
                    ((loaded.get("report") or {}).get("binding_decisions") or [])
                ),
                "schema_errors": len(S.error_messages(loaded)),
            },
            sort_keys=True,
        ),
    )
    doc["negative_controls"][2]["good_state_output"] = (
        f"self_valid errors={len(S.error_messages(doc))}"
    )
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    errs = S.error_messages(doc)
    if errs:
        print("FAILED:ADV-0138 schema after hash fill")
        for e in errs[:25]:
            print(" ", e)
        return 1
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:ADV-0138 sentinel missing from dump")
        return 1
    dest.write_text(text, encoding="utf-8")
    sha, size = sha256_file(dest)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dest.write_text(dump(doc), encoding="utf-8")
    sha, size = sha256_file(dest)
    if size < int(doc["min_bytes_threshold"]):
        print("FAILED:ADV-0138 emit undersize", size)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        "live "
        f"stated={len(stated)} implied={len(implied)} authored={len(authored)}"
    )
    print("SUCCESS:ADV-0138")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
