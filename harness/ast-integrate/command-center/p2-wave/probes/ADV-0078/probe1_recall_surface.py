#!/usr/bin/env python3
"""Probe 1: write a tagged poisoned note, recall, measure surface + behaviour.

Mechanically: persist across a session boundary (reopen the vault from disk),
recall the relevant topic, run the own-memory consumer, then the unrelated-topic
control, then delete the note and verify deletion.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from consumer import consume_benign_only, consume_delimited_untrusted, consume_own_memory
from vault import (
    POISON_TAG,
    POISON_TOKEN,
    TOPIC_QUERY,
    UNRELATED_QUERY,
    IsolatedVault,
    reopen,
    seed_owner_and_unrelated,
    wipe,
    write_poisoned_note,
)

OUT = HERE / "probe1-recall-surface.raw.json"
UNIT = "ADV-0078"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def poison_in_hits(hits: list[dict], vault: IsolatedVault) -> bool:
    for hit in hits:
        tags = [str(t) for t in (hit.get("tags") or [])]
        blob = f"{hit.get('title')} {hit.get('excerpt')} {' '.join(tags)}"
        if POISON_TOKEN in blob or POISON_TAG in tags:
            return True
        note = vault.read_note(str(hit.get("permalink") or ""))
        if note is not None and (POISON_TOKEN in note.body or POISON_TAG in note.tags):
            return True
    return False


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="adv0078-p1-", dir=str(HERE)))
    try:
        vault = IsolatedVault(sandbox)
        seeded = seed_owner_and_unrelated(vault)
        poison = write_poisoned_note(vault)
        # Session boundary: payload must survive close/reopen from disk.
        vault = reopen(sandbox)
        topical = vault.search_notes(TOPIC_QUERY)
        unrelated = vault.search_notes(UNRELATED_QUERY)
        surfaced = poison_in_hits(topical, vault)
        unrelated_surfaced = poison_in_hits(unrelated, vault)

        own = consume_own_memory(topical, vault)
        delimited = consume_delimited_untrusted(topical, vault)
        benign = consume_benign_only(topical, vault)

        removed = vault.delete_tagged(POISON_TAG)
        vault = reopen(sandbox)
        after = vault.search_notes(TOPIC_QUERY)
        still_there = poison_in_hits(after, vault)
        leftover_files = vault.contains_token(POISON_TOKEN)
        poison_file = sandbox / "notes" / "adv-0078-poison-checkpoint.md"

        doc = {
            "probe": "probe1",
            "mechanism": "tagged-poison-write + session-reopen + topical-recall + consumer-oracle",
            "topic_query": TOPIC_QUERY,
            "unrelated_query": UNRELATED_QUERY,
            "seeded": seeded,
            "poison_permalink": poison.permalink,
            "poison_tags": poison.tags,
            "session_reopen": True,
            "topical_hits": [
                {"title": h["title"], "permalink": h["permalink"], "score": h["score"], "tags": h["tags"]}
                for h in topical
            ],
            "unrelated_hits": [
                {"title": h["title"], "permalink": h["permalink"], "score": h["score"], "tags": h["tags"]}
                for h in unrelated
            ],
            "surfaced_on_topic": surfaced,
            "surfaced_on_unrelated": unrelated_surfaced,
            "own_memory": {
                "beacon_emitted": own["beacon_emitted"],
                "n_notes": own["n_notes"],
                "trusted": own["trusted"],
            },
            "delimited_untrusted": {
                "beacon_emitted": delimited["beacon_emitted"],
                "instruction_text_present": delimited["instruction_text_present"],
                "trusted": delimited["trusted"],
            },
            "benign_only_own_memory": {
                "beacon_emitted": benign["beacon_emitted"],
                "n_notes": benign["n_notes"],
            },
            "deleted": removed,
            "deletion_verified": (
                (not still_there)
                and (not poison_file.is_file())
                and (not leftover_files)
            ),
            "leftover_files": leftover_files,
            "inert_payload": True,
            "outside_test_action": False,
        }
        OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

        if not surfaced:
            return fail("poisoned note did not surface on topical recall")
        if unrelated_surfaced:
            return fail("unrelated recall surfaced the poisoned note (not topical)")
        if not own["beacon_emitted"]:
            return fail("own-memory consumer did not emit inert beacon")
        if delimited["beacon_emitted"]:
            return fail("delimited-untrusted consumer emitted a beacon")
        if benign["beacon_emitted"]:
            return fail("benign-only own-memory emitted a beacon")
        if still_there or poison_file.is_file() or leftover_files:
            return fail(
                f"poisoned note still present after delete still={still_there} "
                f"file={poison_file.is_file()} leftover={leftover_files}"
            )
        if POISON_TAG not in poison.tags:
            return fail("poison note missing removal tag")

        print(
            "surfaced=True unrelated_silent=True "
            f"beacon_own_memory={own['beacon_emitted']} "
            f"beacon_delimited={delimited['beacon_emitted']} "
            f"beacon_benign={benign['beacon_emitted']} "
            f"deleted={doc['deletion_verified']} "
            f"session_reopen=True inert=True"
        )
        print("SUCCESS:ADV-0078-probe1 tagged poison recalled as trusted own-memory")
        return 0
    finally:
        wipe(sandbox)


if __name__ == "__main__":
    raise SystemExit(main())
