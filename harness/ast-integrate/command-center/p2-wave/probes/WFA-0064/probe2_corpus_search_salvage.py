#!/usr/bin/env python3
"""Probe 2: independent corpus search, canary, extraction-miss, salvage bar.

The direct search must find canary.known-present in surviving corpus
before silence is trusted. A matrix orphan that the search still finds
is an extraction miss, not a salvage. Salvage is vocabulary + blueprint
stages on disk; a note-only record is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402

ART = REPO / S.PRIMARY_OUT
CANARY = "canary.known-present"
MISS = "false.orphan.extraction-miss"
SALVAGE_REQUIRED = (
    "orphan.hook-pre-tool",
    "orphan.reject-quorum",
    "orphan.not-worth.stub",
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0064-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0064" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    estate = S.load_estate()
    live = S.analyze(estate)
    canary = live["canary"]
    print(
        f"canary id={canary['mechanism_id']} found={canary['found']} "
        f"expected_file={canary['expected_file']} "
        f"found_in_expected={canary['found_in_expected_file']} "
        f"silence_trusted={canary['silence_trusted']}"
    )
    if not canary["found"] or not canary["silence_trusted"]:
        return fail("canary-not-found-silence-untrusted")
    if canary["expected_file"] not in {h["file"] for h in canary["hits"]}:
        return fail("canary-not-in-expected-surviving-file")

    # Independent re-search, not a copy of the artifact list.
    files = S.surviving_files(estate, S.CORPUS)
    hook_hits = S.search_mechanism(files, "orphan.hook-pre-tool")
    miss_hits = S.search_mechanism(files, MISS)
    canary_hits = S.search_mechanism(files, CANARY)
    print(f"independent_search hook_hits={len(hook_hits)} miss_hits={len(miss_hits)} canary_hits={len(canary_hits)}")
    if hook_hits:
        return fail("hook-found-in-surviving-corpus")
    if not miss_hits:
        return fail("extraction-miss-not-found-by-search")
    if not canary_hits:
        return fail("independent-canary-miss")

    if MISS not in live["extraction_misses"]:
        return fail("extraction-miss-not-classified")
    if MISS in live["salvage_necessary"]:
        return fail("extraction-miss-claimed-as-salvage")
    if MISS in live["salvaged_ids"]:
        return fail("extraction-miss-extracted")

    for mid in SALVAGE_REQUIRED:
        if mid not in live["salvage_necessary"]:
            return fail(f"salvage-necessary-missing {mid}")
        if mid not in live["salvaged_ids"]:
            return fail(f"salvage-not-extracted {mid}")

    note = S.note_only_record("orphan.hook-pre-tool")
    if S.is_extracted_salvage(note):
        return fail("note-only-accepted-as-salvage")
    if not live.get("note_only_rejected"):
        return fail("artifact-did-not-reject-note-only")

    vocab_path = REPO / S.VOCAB_OUT
    bp_path = REPO / S.BLUEPRINT_OUT
    if not vocab_path.is_file() or not bp_path.is_file():
        return fail("extract-files-missing")
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    bps = json.loads(bp_path.read_text(encoding="utf-8"))
    vocab_ids = {r.get("id") for r in vocab.get("records") or []}
    bp_mechs = {r.get("mechanism_id") for r in bps.get("records") or []}
    for mid in SALVAGE_REQUIRED:
        if mid not in vocab_ids:
            return fail(f"vocab-missing {mid}")
        if mid not in bp_mechs:
            return fail(f"blueprint-missing {mid}")
        rec = next(r for r in live["salvaged"] if r["id"] == mid)
        if not S.is_extracted_salvage(rec):
            return fail(f"salvage-bar-failed {mid}")
        definition = rec["vocabulary"]["definition"]
        if len(definition) < 40:
            return fail(f"definition-too-short {mid}")
        if not rec["target_blueprint"]["stages"]:
            return fail(f"blueprint-no-stages {mid}")
        print(
            f"salvaged {mid} worth={rec['worth_extracting']} "
            f"vocab_chars={len(definition)} stages={len(rec['target_blueprint']['stages'])} "
            f"bp={rec['target_blueprint']['id']}"
        )

    stub = next(r for r in live["salvaged"] if r["id"] == "orphan.not-worth.stub")
    if stub.get("worth_extracting") is not False:
        return fail("stub-marked-worth")
    hook = next(r for r in live["salvaged"] if r["id"] == "orphan.hook-pre-tool")
    if hook.get("worth_extracting") is not True:
        return fail("hook-not-marked-worth")

    if list(doc.get("salvage_necessary") or []) != live["salvage_necessary"]:
        return fail("artifact-salvage-necessary-drift")
    if list(doc.get("extraction_misses") or []) != live["extraction_misses"]:
        return fail("artifact-extraction-miss-drift")

    recall = doc.get("recall_limit") or {}
    if recall.get("implied_exhaustiveness") is True:
        return fail("implied-exhaustiveness")
    if recall.get("live_284_estate_scanned") is True and not (doc.get("live_inputs") or {}).get(
        "workflow_candidate_registry", {}
    ).get("present"):
        return fail("claimed-284-scan-without-registry")
    unread = recall.get("unread") or []
    if not unread:
        return fail("recall-unread-empty")

    owner = doc.get("owner_signoff") or {}
    if owner.get("present") is True:
        return fail("self-certified-owner-signoff")
    if owner.get("required") is not True:
        return fail("owner-signoff-not-required")

    extracts = doc.get("extracts") or {}
    if extracts.get("vocabulary_path") != S.VOCAB_OUT:
        return fail("vocab-path-not-recorded")
    if extracts.get("blueprint_path") != S.BLUEPRINT_OUT:
        return fail("blueprint-path-not-recorded")

    print(
        json.dumps(
            {
                "probe": "probe2-corpus-search-salvage",
                "unit_id": "WFA-0064",
                "canary_found": True,
                "extraction_misses": live["extraction_misses"],
                "salvage_necessary": live["salvage_necessary"],
                "note_only_rejected": True,
                "extracts_on_disk": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0064-probe2 corpus-search canary extraction-miss salvage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
