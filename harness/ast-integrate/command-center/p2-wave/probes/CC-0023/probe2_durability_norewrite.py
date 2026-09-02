#!/usr/bin/env python3
"""Probe 2: OWNER-DECISIONS.md durability; no silent rewrite; mutant fires."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
import durable  # noqa: E402
import rewrite  # noqa: E402

ART = REPO / "command-center/receipts/CC-0023.json"
DECISIONS = REPO / "command-center/OWNER-DECISIONS.md"
PACKET = REPO / "command-center/OWNER-QUESTION-PACKET.md"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0023-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    if not DECISIONS.is_file() or not PACKET.is_file():
        return fail("durable owner files missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text1 = DECISIONS.read_text(encoding="utf-8")
    recs1 = durable.parse_decisions(text1)
    text2 = DECISIONS.read_text(encoding="utf-8")
    recs2 = durable.parse_decisions(text2)
    if recs1 != recs2:
        return fail("re-read OWNER-DECISIONS.md disagreed")
    want = {q["id"] for q in doc.get("questions") or []}
    got = {r.get("question_id") for r in recs1}
    if want != got:
        return fail(f"durability ids want={sorted(want)} got={sorted(got)}")
    if len(recs1) != 12:
        return fail(f"durability count={len(recs1)}")
    for rec in recs1:
        if rec.get("terminal_state") != "DEFERRED":
            return fail(f"{rec.get('question_id')} state={rec.get('terminal_state')}")
        if rec.get("default_applied") != "true":
            return fail(f"{rec.get('question_id')} default_applied")
        if not rec.get("recorded_at"):
            return fail(f"{rec.get('question_id')} missing recorded_at")
        if rec.get("owner_answer"):
            return fail(f"{rec.get('question_id')} inferred owner_answer")

    packet_text = PACKET.read_text(encoding="utf-8")
    for q in doc["questions"]:
        if q["id"] not in packet_text or q["question"] not in packet_text:
            return fail(f"packet missing {q['id']}")
        if q["recommendation"] not in packet_text:
            return fail(f"packet missing recommendation {q['id']}")

    written = corpus.write_fixtures(HERE / "fixtures")
    identity_hits = []
    for name in corpus.DOC_FILES:
        path = written[name]
        identity_hits.extend(rewrite.silent_rewrites_path(path, path))
    if identity_hits:
        return fail(f"identity rewrite fired {identity_hits}")

    recorded = {h["path"].split("/")[-1]: h["sha256"] for h in doc.get("corpus", {}).get("source_hashes") or []}
    for name in corpus.DOC_FILES:
        live = rewrite.digest_text(written[name].read_text(encoding="utf-8"))
        if recorded.get(name) and recorded[name] != live:
            return fail(f"source hash drift {name}")

    with tempfile.TemporaryDirectory(prefix="cc0023-p2-") as tmp:
        mutant = Path(tmp) / "mutant.md"
        original = written["16-GRILL-QUEUE.md"].read_text(encoding="utf-8")
        mutant.write_text(original.replace("M-16", "OPT-16"), encoding="utf-8")
        hits = rewrite.silent_rewrites(original, mutant.read_text(encoding="utf-8"))
        if not hits:
            return fail("silent rewrite detector silent on unattributed OPT-16 mutant")
        attributed = original.replace(
            "M-16", "OPT-16 <!-- CC-0023 owner-answer namespace rewrite -->", 1
        )
        attributed_hits = rewrite.silent_rewrites(original, attributed)
        # First replacement only; remaining M-16 may still vanish count-wise.
        # Require the detector to fire when ANY vanishing token lacks attribution.
        # The attributed sample still has other M-16 → OPT-16? replace(..., 1) only one.
        # Remaining M-16 unchanged, so vanished count for M-16 is 1, and attribution
        # marker is present → detector returns []. That is the currently-true attributed path.
        if attributed_hits:
            return fail("attributed rewrite treated as silent")

    # Independent reviewer: no reference resolved without an owner answer.
    for row in doc["references"]:
        if row.get("resolved_namespace") and not row.get("owner_answer"):
            return fail(f"resolved without owner {row['id']}")

    print(
        json.dumps(
            {
                "probe": "probe2-durability-norewrite",
                "records": len(recs1),
                "reread_equal": True,
                "identity_silent": True,
                "mutant_fired": True,
                "attributed_silent": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0023-probe2 durability no-rewrite reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
